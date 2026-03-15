# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Docker (primary workflow)
```bash
# Desarrollo con hot-reload (usa docker-compose.override.yml automáticamente)
docker compose up -d
docker compose logs -f api

# Producción (sin override)
docker compose -f docker-compose.yml up -d

# Rebuild tras cambios en Dockerfile o requirements.txt
docker compose build api
docker compose build frontend
```

### Frontend (desarrollo local sin Docker)
```bash
cd frontend
npm install
npm run dev        # Vite en http://localhost:5173
npm run build      # vue-tsc + vite build (lo que corre en Docker)
npm run type-check # vue-tsc sin emitir
```

### Backend (fuera de Docker, con Qdrant ya corriendo)
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Tests
```bash
# Backend
cd backend && pytest tests/ -v
pytest tests/test_api.py::test_health -v  # test individual

# Frontend
cd frontend && npx vitest run
npx vitest run src/tests/useRag.test.ts   # test individual
```

## Architecture

### Services (Docker Compose)
- **qdrant** — Vector database. Datos persistidos en `./qdrant_storage/` (volumen local).
- **api** — FastAPI en puerto 8000. Documentos en `./backend/data/`, índice LlamaIndex en `./backend/storage/`.
- **frontend** — Nginx en puerto 80. Sirve el build de Vue y hace proxy `/api/` → `api:8000`.

En desarrollo, `docker-compose.override.yml` monta `./backend:/app` para hot-reload con `uvicorn --reload`.

### Backend (`backend/`)

**Flujo de datos:**
1. `config.py` — `Settings` (pydantic-settings) lee `.env`. Es la única fuente de verdad para configuración. Todas las features flags están aquí (`enable_hybrid`, `enable_reranker`, `enable_hyde`, `enable_semantic_chunking`).
2. `main.py` — App FastAPI con todos los endpoints. Mantiene estado en memoria: `INDEX_CACHE` (TTLCache), `_CHAT_ENGINES` (TTLCache), `INGEST_STATUS`, `EVAL_JOBS`, `FEEDBACK_FILE`.
3. `rag/ingest.py` — Pipeline de ingestión. Datos por colección en `./data/{collection}/`. LlamaIndex settings son globales (singleton con lock) — se inicializan una sola vez en `_init_llama_settings()`.
4. `rag/query.py` — Query single-turn y chat multi-turn. El `_HyDERetriever` es un wrapper `BaseRetriever` que aplica `HyDEQueryTransform` antes de recuperar, necesario porque `CondensePlusContextChatEngine` no expone un hook de query transform directamente. Los chat engines se cachean en `_CHAT_ENGINES` keyed por `f"{session_id}:{top_k}:{apply_hyde}"`.
5. `rag/eval.py` — Evaluación RAGAS-style usando `Settings.llm.complete()` como juez (sin dependencia de la librería RAGAS).
6. `rag/models.py` — Schemas Pydantic para todos los requests/responses.

**Multi-colección:** Cada colección tiene su propio directorio `./data/{name}/`, `./storage/{name}/` y colección en Qdrant. La colección activa se pasa en los requests; si no se especifica, usa `COLLECTION_NAME` del `.env`.

**Búsqueda híbrida:** Dense (Gemini embeddings 3072d) + sparse (BM25 vía fastembed). Si la colección existe sin sparse vectors y `ENABLE_HYBRID=true`, `get_vector_store()` con `allow_recreate=True` la elimina y recrea al ingestar. Con `allow_recreate=False` (startup) degrada silenciosamente a dense-only.

**Imágenes:** `_embed_images_natively()` en `ingest.py` genera `ImageNode` con embeddings nativos multimodal (base64 → Gemini) en lugar de OCR. `SimpleDirectoryReader` procesa solo `.pdf`, `.txt`, `.md`; las imágenes se procesan por separado.

### Frontend (`frontend/src/`)

**Capas:**
- `api/ragApi.ts` — Única interfaz con el backend (axios). Todo el manejo de SSE streaming está en `useChat()` usando `fetch` + `ReadableStream` (no axios, porque axios no soporta streaming).
- `composables/useRag.ts` — Composables Vue que encapsulan la lógica de negocio: `useHealth`, `useDocuments`, `useIngest`, `useIngestStatus`, `useChat`, `useQuery`.
- `stores/useConversationStore.ts` — Pinia store persistido en `localStorage` (`rag_conversations`, `rag_folders`, `rag_active_conversation_id`). Maneja conversaciones, carpetas, mensajes y el `sessionId` del backend.
- `stores/useCollectionStore.ts` — Pinia store para colección activa, persistida en `localStorage`.
- `types/rag.ts` — Interfaces TypeScript que espejo los schemas Pydantic del backend.

**Vistas:** `HomeView` (chat + sidebars), `SettingsView`, `EvalView`. El sidebar derecho (documentos/ingestión) es colapsable.

**Paleta de colores:** Cape Cod (grises oscuros). Variables en `style.css` — `--text-primary`, `--text-secondary`, `--text-muted`, `--success`, `--warning`, `--error`. No usar variables `var(--cyan-*)` ni `var(--violet-*)` — no están definidas.

### Key `.env` variables
```
GOOGLE_API_KEY=          # Requerida
EMBEDDING_DIM=3072       # Debe coincidir con el modelo (gemini-embedding-2-preview = 3072)
COLLECTION_NAME=facultad_rag
ENABLE_HYBRID=true
ENABLE_RERANKER=true
ENABLE_HYDE=false
ENABLE_SEMANTIC_CHUNKING=false
```

> Cambiar `ENABLE_HYDE` via `PUT /config` invalida `_CHAT_ENGINES` automáticamente.
> Cambiar `ENABLE_SEMANTIC_CHUNKING` requiere re-ingestión completa de documentos.

## Memory

You have access to Engram persistent memory via MCP tools (`mem_save`, `mem_search`, `mem_session_summary`, etc.).
- Save proactively after significant work — don't wait to be asked.
- After any compaction or context reset, call `mem_context` to recover session state before continuing.
