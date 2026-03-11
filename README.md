# RAG Multimodal

## Visión General

Sistema **RAG (Retrieval-Augmented Generation) Multimodal** completo con arquitectura fullstack. Permite subir documentos (PDF, imágenes, texto/markdown), ingestarlos en una base vectorial y luego consultarlos mediante chat multi-turn con respuestas generadas por IA, con streaming en tiempo real.

**Stack tecnológico:**
- **Backend:** Python + FastAPI + LlamaIndex + Gemini 2.5 Flash (LLM) + Gemini Embedding 2 Preview + Qdrant (vector store)
- **Frontend:** Vue 3 (Composition API) + TypeScript + PrimeVue 4 + Axios + Vite
- **Infraestructura:** Docker Compose (3 servicios: `qdrant`, `api`, `frontend`)
- **Búsqueda:** Híbrida dense+sparse (BM25 via fastembed) + reranking con cross-encoder local

---

## Estructura de Carpetas

```
rag_multimodal/
├── .env                          # Variables de entorno (GOOGLE_API_KEY, etc.)
├── docker-compose.yml            # Configuración de producción
├── docker-compose.override.yml   # Configuración de desarrollo (hot-reload)
├── qdrant_storage/               # Datos persistentes de Qdrant (colección facultad_rag)
│
├── backend/
│   ├── main.py                   # App FastAPI: todos los endpoints REST
│   ├── config.py                 # Settings centralizados (pydantic-settings)
│   ├── logger.py                 # Logger estructurado JSON (loguru)
│   ├── eval_pipeline.py          # Evaluación RAG con RAGAS (CLI)
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── data/                     # Documentos subidos (montado como volumen)
│   ├── storage/                  # Índice persistido de LlamaIndex (JSON)
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── ingest.py             # Pipeline de ingestión: carga → chunking → embed → Qdrant
│   │   ├── query.py              # Query RAG single-turn + Chat multi-turn + SSE streaming
│   │   └── models.py             # Schemas Pydantic para requests/responses
│   └── tests/
│       ├── conftest.py
│       └── test_api.py           # Tests de integración con httpx + pytest-asyncio
│
└── frontend/
    ├── package.json
    ├── vite.config.ts
    ├── nginx.conf                # Nginx: SPA fallback + proxy /api/ → backend:8000
    ├── Dockerfile
    └── src/
        ├── main.ts               # Entry point: Vue app + PrimeVue + Router + Pinia
        ├── App.vue               # Root: <Toast> + <RouterView>
        ├── style.css             # Variables CSS globales (dark mode, glassmorphism)
        ├── api/
        │   └── ragApi.ts         # Cliente HTTP (axios): todas las llamadas a la API
        ├── types/
        │   └── rag.ts            # Tipos TypeScript (mirrors de los schemas Pydantic)
        ├── composables/
        │   └── useRag.ts         # Composables Vue: useHealth, useDocuments, useIngest,
        │                         #   useQuery, useIngestStatus, useReset, useChat
        ├── components/
        │   ├── AppHeader.vue     # Header sticky: logo + badge de estado API/Index
        │   ├── DocumentUpload.vue # Upload drag&drop + lista de documentos + eliminar
        │   ├── IngestPanel.vue   # Botones de ingestión + polling de estado
        │   ├── QueryPanel.vue    # Chat multi-turn con streaming SSE + feedback
        │   └── SourcesDisplay.vue # Visualización de chunks fuente con score
        ├── views/
        │   └── HomeView.vue      # Layout: sidebar (upload+ingest+danger zone) | chat
        ├── router/
        │   └── index.ts          # Vue Router: ruta "/" → HomeView
        └── tests/
            └── useRag.test.ts    # Tests de composables con vitest
```

---

## Flujo de Funcionamiento

### 1. Ingestión de Documentos

1. El usuario sube archivos vía `POST /upload` (validación por magic bytes: PDF, PNG, JPG, TXT, MD — máx. 50 MB)
2. `POST /ingest` dispara en background:
   - `SimpleDirectoryReader` carga los documentos de `./data/`
   - Chunking con `SentenceSplitter` (512 tokens, overlap 64) o semántico si `ENABLE_SEMANTIC_CHUNKING=true`
   - Embeddings con **Gemini Embedding 2 Preview** (3072 dimensiones)
   - Almacenamiento en **Qdrant** (búsqueda híbrida dense+sparse BM25 si `ENABLE_HYBRID=true`)
   - Metadata enriquecida por nodo: `file_type`, `ingested_at`, `file_size`, `page_label`
   - El índice se persiste en `./storage/` (JSON de LlamaIndex)
3. `GET /ingest/status` reporta: `idle | running | done | failed`

### 2. Consulta RAG (single-turn)

- `POST /query` con `{ query, top_k, file_type_filter?, use_hyde? }`
- Recupera `top_k * 3` candidatos vía búsqueda híbrida → reranking con cross-encoder `ms-marco-MiniLM-L-2-v2` → devuelve `top_k` resultados
- Opcionalmente aplica **HyDE** (genera documento hipotético antes de buscar)
- Responde `{ query_id, answer, sources[], nodes_retrieved }`

### 3. Chat Multi-turn con Streaming

- `POST /chat/stream` devuelve **SSE (Server-Sent Events)**:
  - Eventos `token` con cada token generado
  - Evento final `sources` con los chunks recuperados + `query_id` + `session_id`
- Memoria de conversación por `session_id` (almacenada en RAM, `ChatMemoryBuffer` 4096 tokens)
- `POST /chat` como fallback sin streaming
- `DELETE /chat/{session_id}` limpia la sesión

### 4. Frontend (SPA)

Layout de dos columnas:
- **Sidebar izquierda:** upload drag&drop → lista de documentos (con eliminar individual) → panel de ingestión (con polling automático cada 3s) → "Zona de peligro" (reset total)
- **Área principal:** chat con historial, streaming token a token, renderizado Markdown seguro (marked + DOMPurify), feedback thumbs up/down por mensaje, exportación a Markdown, configuración de `top_k` mediante slider

---

## Variables de Entorno (`.env`)

| Variable | Default | Descripción |
|---|---|---|
| `GOOGLE_API_KEY` | **requerida** | API key de Google AI (Gemini) |
| `QDRANT_HOST` | `qdrant` | Host del servicio Qdrant |
| `QDRANT_PORT` | `6333` | Puerto Qdrant |
| `COLLECTION_NAME` | `facultad_rag` | Nombre de la colección en Qdrant |
| `EMBEDDING_DIM` | `3072` | Dimensión del embedding (Gemini Embedding 2) |
| `ENABLE_HYBRID` | `true` | Búsqueda híbrida dense+sparse (BM25) |
| `ENABLE_RERANKER` | `true` | Cross-encoder reranking |
| `ENABLE_HYDE` | `false` | HyDE query transform |
| `API_KEY` | `null` | Bearer token para autenticar endpoints (opcional) |
| `MAX_UPLOAD_MB` | `50` | Tamaño máximo de archivos subidos |
| `API_PORT` | `8000` | Puerto del backend |

> **Importante:** La dimensión del embedding debe coincidir con la salida del modelo. Para `gemini-embedding-2-preview` el valor es `3072`.

---

## Endpoints de la API

| Método | Ruta | Límite | Descripción |
|---|---|---|---|
| `GET` | `/health` | — | Estado de la API e índice |
| `POST` | `/upload` | 10/min | Subir documento (multipart) |
| `GET` | `/documents` | — | Listar documentos subidos |
| `DELETE` | `/documents/{filename}` | — | Eliminar documento + vectores de Qdrant |
| `POST` | `/ingest` | 5/min | Iniciar ingestión en background |
| `GET` | `/ingest/status` | — | Estado de la ingestión |
| `POST` | `/query` | 20/min | Consulta RAG single-turn |
| `POST` | `/chat` | 20/min | Chat multi-turn sin streaming |
| `POST` | `/chat/stream` | 20/min | Chat multi-turn con SSE streaming |
| `DELETE` | `/chat/{session_id}` | — | Limpiar historial de sesión |
| `GET` | `/collections` | — | Listar colecciones en Qdrant |
| `DELETE` | `/collection` | — | Reset total de la colección |
| `POST` | `/feedback` | — | Registrar feedback de calidad (JSONL) |

---

## Docker Compose

| Servicio | Puerto | Descripción |
|---|---|---|
| `qdrant` | `6333`, `6334` (gRPC) | Vector database, datos en `./qdrant_storage/` |
| `api` | `8000` | Backend FastAPI |
| `frontend` | `80` | Nginx sirviendo el build de Vue |

```bash
# Desarrollo (hot-reload activado via override)
docker compose up -d
docker compose logs -f api

# Producción (sin override)
docker compose -f docker-compose.yml up -d

# Apagar (los datos persisten en volúmenes montados)
docker compose down
```

Para desarrollo del frontend fuera de Docker:
```bash
cd frontend
npm install
npm run dev   # Vite en http://localhost:5173
```

---

## Seguridad Implementada

- Validación de tipo de archivo por **magic bytes** (no solo extensión) con `filetype`
- Protección contra **path traversal** en `DELETE /documents/{filename}`
- **Rate limiting** por IP con `slowapi`
- Auth opcional mediante **Bearer token** (si `API_KEY` está definida)
- Sanitización de Markdown en frontend con **DOMPurify** (previene XSS)
- CORS restringido a orígenes explícitos

---

## Evaluación del Pipeline RAG

`eval_pipeline.py` permite medir la calidad del pipeline con **RAGAS**:

```bash
python eval_pipeline.py --questions questions.json --top_k 5 --output eval_results.json
```

Métricas reportadas: `faithfulness`, `answer_relevancy`, `context_recall`, `context_precision`.
