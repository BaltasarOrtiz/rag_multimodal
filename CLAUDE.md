# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Docker (primary workflow)
```bash
# Development with hot-reload (uses docker-compose.override.yml automatically)
docker compose up -d
docker compose logs -f api

# Production (without override)
docker compose -f docker-compose.yml up -d

# Rebuild after changes to Dockerfile or requirements.txt
docker compose build api
docker compose build frontend
```

### Frontend (local development without Docker)
```bash
cd frontend
npm install
npm run dev        # Vite at http://localhost:5173
npm run build      # vue-tsc + vite build (what runs in Docker)
npm run type-check # vue-tsc without emitting
```

### Backend (outside Docker, with Qdrant already running)
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Tests
```bash
# Backend
cd backend && pytest tests/ -v
pytest tests/test_api.py::test_health -v  # individual test

# Frontend
cd frontend && npx vitest run
npx vitest run src/tests/useRag.test.ts   # individual test
```

## Architecture

### Services (Docker Compose)
- **qdrant** — Vector database. Data persisted in `./qdrant_storage/` (local volume).
- **api** — FastAPI on port 8000. Documents in `./backend/data/`, LlamaIndex index in `./backend/storage/`.
- **frontend** — Nginx on port 80. Serves the Vue build and proxies `/api/` → `api:8000`.

In development, `docker-compose.override.yml` mounts `./backend:/app` for hot-reload with `uvicorn --reload`.

### Backend (`backend/`)

**Data flow:**
1. `config.py` — `Settings` (pydantic-settings) reads `.env`. It is the single source of truth for configuration. All feature flags are here (`enable_hybrid`, `enable_reranker`, `enable_hyde`, `enable_semantic_chunking`).
2. `main.py` — FastAPI app with all endpoints. Maintains in-memory state: `INDEX_CACHE` (TTLCache), `_CHAT_ENGINES` (TTLCache), `INGEST_STATUS`, `EVAL_JOBS`, `FEEDBACK_FILE`.
3. `rag/ingest.py` — Ingestion pipeline. Data per collection in `./data/{collection}/`. LlamaIndex settings are global (singleton with lock) — initialized once in `_init_llama_settings()`.
4. `rag/query.py` — Single-turn query and multi-turn chat. The `_HyDERetriever` is a `BaseRetriever` wrapper that applies `HyDEQueryTransform` before retrieving, necessary because `CondensePlusContextChatEngine` does not expose a query transform hook directly. Chat engines are cached in `_CHAT_ENGINES` keyed by `f"{session_id}:{top_k}:{apply_hyde}"`.
5. `rag/eval.py` — RAGAS-style evaluation using `Settings.llm.complete()` as judge (no dependency on the RAGAS library).
6. `rag/models.py` — Pydantic schemas for all requests/responses.

**Multi-collection:** Each collection has its own `./data/{name}/`, `./storage/{name}/` directory and Qdrant collection. The active collection is passed in requests; if not specified, uses `COLLECTION_NAME` from `.env`.

**Hybrid search:** Dense (Gemini embeddings 3072d) + sparse (BM25 via fastembed). If the collection exists without sparse vectors and `ENABLE_HYBRID=true`, `get_vector_store()` with `allow_recreate=True` deletes and recreates it on ingestion. With `allow_recreate=False` (startup) it silently degrades to dense-only.

**Images:** `_embed_images_natively()` in `ingest.py` generates `ImageNode` with native multimodal embeddings (base64 → Gemini) instead of OCR. `SimpleDirectoryReader` processes only `.pdf`, `.txt`, `.md`; images are processed separately.

### Frontend (`frontend/src/`)

**Layers:**
- `api/ragApi.ts` — Single interface with the backend (axios). All SSE streaming handling is in `useChat()` using `fetch` + `ReadableStream` (not axios, because axios does not support streaming).
- `composables/useRag.ts` — Vue composables that encapsulate business logic: `useHealth`, `useDocuments`, `useIngest`, `useIngestStatus`, `useChat`, `useQuery`.
- `stores/useConversationStore.ts` — Pinia store persisted in `localStorage` (`rag_conversations`, `rag_folders`, `rag_active_conversation_id`). Manages conversations, folders, messages and the backend `sessionId`.
- `stores/useCollectionStore.ts` — Pinia store for the active collection, persisted in `localStorage`.
- `types/rag.ts` — TypeScript interfaces that mirror the backend Pydantic schemas.

**Views:** `HomeView` (chat + sidebars), `SettingsView`, `EvalView`. The right sidebar (documents/ingestion) is collapsible.

**Color palette:** Cape Cod (dark grays). Variables in `style.css` — `--text-primary`, `--text-secondary`, `--text-muted`, `--success`, `--warning`, `--error`. Do not use `var(--cyan-*)` or `var(--violet-*)` variables — they are not defined.

### Key `.env` variables
```
GOOGLE_API_KEY=          # Required
EMBEDDING_DIM=3072       # Must match the model (gemini-embedding-2-preview = 3072)
COLLECTION_NAME=facultad_rag
ENABLE_HYBRID=true
ENABLE_RERANKER=true
ENABLE_HYDE=false
ENABLE_SEMANTIC_CHUNKING=false
```

> Changing `ENABLE_HYDE` via `PUT /config` invalidates `_CHAT_ENGINES` automatically.
> Changing `ENABLE_SEMANTIC_CHUNKING` requires a full re-ingestion of documents.

## Memory

You have access to Engram persistent memory via MCP tools (`mem_save`, `mem_search`, `mem_session_summary`, etc.).
- Save proactively after significant work — don't wait to be asked.
- After any compaction or context reset, call `mem_context` to recover session state before continuing.
