# RAG Multimodal — AI Agent Instructions

## Project Context

**RAG Multimodal** fullstack system with multi-turn chat and SSE streaming.
Allows uploading documents (PDF, images, text/markdown), ingesting them into a
vector database and querying them via AI-generated chat with real-time responses.

**Stack:**
- Backend: Python 3.11 + FastAPI + LlamaIndex + `llama-index-llms-google-genai`
  + Gemini 2.5 Flash + Gemini Embedding 2 Preview + Qdrant
- Frontend: Vue 3 (Composition API) + TypeScript + PrimeVue 4 + Axios + Vite
- Infra: Docker Compose (3 services: `qdrant`, `api`, `frontend`)
- Search: hybrid dense+sparse (BM25 via fastembed) + cross-encoder reranking

---

## Essential Commands

```bash
# Development (hot-reload via override)
docker compose up -d
docker compose logs -f api

# Production
docker compose -f docker-compose.yml up -d

# Frontend outside Docker
cd frontend && npm run dev   # http://localhost:5173

# Backend tests
cd backend && pytest tests/ -v

# Frontend tests
cd frontend && npm run test

# Clean rebuild after Dockerfile or requirements changes
docker compose build --no-cache
docker compose up -d
```

---

## Canonical Project Structure

```
rag_multimodal/
├── AGENTS.md
├── .env                          # Do not commit — ignored in .gitignore
├── .env.example                  # Public template with example values
├── .gitignore
├── .github/
│   └── copilot-instructions.md  # Same content as AGENTS.md
├── .claude/
│   └── rules/project.md         # Same content as AGENTS.md
├── docker-compose.yml
├── docker-compose.override.yml
├── qdrant_storage/               # Persistent volume — DO NOT delete
├── backend/
└── frontend/
```

---

## BACKEND — Rules and Structure

### Mandatory folder structure

```
backend/
├── main.py               # FastAPI app: lifespan, CORS, routers, rate limiting
├── config.py             # Settings with pydantic-settings (BaseSettings)
├── logger.py             # Structured JSON logger with loguru
├── eval_pipeline.py      # CLI for RAGAS evaluation (do not touch in features)
├── requirements.txt
├── Dockerfile
├── .dockerignore
│
├── rag/
│   ├── __init__.py
│   ├── ingest.py         # Full pipeline: load → chunking → embed → Qdrant
│   ├── query.py          # RAG single-turn + multi-turn chat + SSE streaming
│   └── models.py         # Pydantic schemas for ALL requests/responses
│
├── data/                 # Uploaded documents (Docker volume — DO NOT touch in code)
├── storage/              # LlamaIndex persisted index (JSON — DO NOT delete)
│
└── tests/
    ├── conftest.py       # Fixtures: app, client, mock_index
    └── test_api.py       # Integration tests with httpx + pytest-asyncio
```

### Backend Rules

**Modules and responsibilities:**

- `main.py` only contains: FastAPI instance, lifespan, middleware, router
  inclusion and simple endpoints. **Never** business logic in `main.py`.
- `rag/ingest.py` is the only place where `SimpleDirectoryReader`,
  `SentenceSplitter`, `GoogleGenAIEmbedding` are instantiated and written to Qdrant.
- `rag/query.py` is the only place where `GoogleGenAI` (LLM),
  `ChatMemoryBuffer`, `CondensePlusContextChatEngine` are instantiated and SSE is generated.
- `rag/models.py` contains **all** Pydantic schemas. Never inline in
  endpoints. Always separate `*Request` from `*Response`.
- `config.py` uses `pydantic-settings`. All environment variable accesses
  must go through the `settings` object. **Never** use `os.environ.get()`
  directly in modules.

**LlamaIndex / Gemini:**

- **Always** use `from llama_index.llms.google_genai import GoogleGenAI`
  (never `from llama_index.llms.gemini import Gemini` — it is deprecated).
- **Always** use `from llama_index.embeddings.google_genai import GoogleGenAIEmbedding`
  (never `GeminiEmbedding`).
- LLM model: `gemini-2.5-flash` by default.
- Embedding model: `models/gemini-embedding-2-preview` with `EMBEDDING_DIM=3072`.
- The index is loaded from Qdrant in the `lifespan` startup. If it does not exist,
  it is created empty. **Never** recreate the index on each request.

**Security (do not omit in any feature):**

- Validate file type with `filetype` (magic bytes), never by extension alone.
- Protect `DELETE /documents/{filename}` against path traversal using
  `pathlib.Path` and verifying the file is inside `./data/`.
- If `settings.api_key` is defined, require `Authorization: Bearer <token>`.
  Apply `Depends(verify_api_key)` to all endpoints that modify state.
- Rate limiting with `slowapi` according to the endpoint table defined below.
- Restricted CORS: never use `allow_origins=["*"]` in production.
  Always use `settings.cors_origins` (explicit list from `.env`).

**Mandatory code patterns:**

```python
# ✅ Correct: async endpoints with explicit return type
@router.post("/upload", response_model=UploadResponse, status_code=201)
async def upload_file(file: UploadFile = File(...)) -> UploadResponse:
    ...

# ✅ Correct: background tasks for ingestion
@router.post("/ingest")
async def start_ingest(background_tasks: BackgroundTasks) -> IngestResponse:
    background_tasks.add_task(run_ingest_pipeline)
    ...

# ✅ Correct: SSE streaming with EventSourceResponse
@router.post("/chat/stream")
async def chat_stream(req: ChatRequest) -> EventSourceResponse:
    async def generator():
        async for token in engine.astream_chat(req.message):
            yield {"event": "token", "data": token.delta}
        yield {"event": "sources", "data": json.dumps(sources)}
    return EventSourceResponse(generator())

# ❌ Forbidden: business logic in endpoints
@router.post("/query")
async def query(req: QueryRequest):
    results = qdrant_client.search(...)  # ❌ direct DB access in endpoint
    llm = GoogleGenAI(...)               # ❌ instantiation on each request
```

**Error handling:**

```python
# Always use HTTPException with descriptive detail
raise HTTPException(status_code=422, detail="Unsupported file type")

# Structured logger on all unhandled errors
logger.exception("Ingestion error: {error}", error=str(e))
```

**API Endpoints (implementation reference):**

| Method | Route | Rate Limit | Auth Required |
|--------|-------|-----------|---------------|
| GET | `/health` | — | No |
| POST | `/upload` | 10/min | If API_KEY defined |
| GET | `/documents` | — | No |
| DELETE | `/documents/{filename}` | — | Yes |
| POST | `/ingest` | 5/min | Yes |
| GET | `/ingest/status` | — | No |
| POST | `/query` | 20/min | No |
| POST | `/chat` | 20/min | No |
| POST | `/chat/stream` | 20/min | No |
| DELETE | `/chat/{session_id}` | — | No |
| GET | `/collections` | — | No |
| DELETE | `/collection` | — | Yes |
| POST | `/feedback` | — | No |

---

## FRONTEND — Rules and Structure

### Mandatory folder structure

```
frontend/
├── package.json
├── vite.config.ts
├── tsconfig.json
├── nginx.conf              # SPA fallback + proxy /api/ → backend:8000
├── Dockerfile
├── .dockerignore
│
└── src/
    ├── main.ts             # Bootstrap: createApp + PrimeVue + Router + Pinia
    ├── App.vue             # Root component: <Toast /> + <RouterView />
    ├── style.css           # Global CSS variables (dark mode, glassmorphism)
    │
    ├── api/
    │   └── ragApi.ts       # Single source of truth for HTTP calls
    │                       # Axios instance with baseURL=/api, interceptors
    │
    ├── types/
    │   └── rag.ts          # TypeScript interfaces: mirrors of Pydantic schemas
    │
    ├── composables/        # State logic and side effects (one composable per domain)
    │   └── useRag.ts       # Exports: useHealth, useDocuments, useIngest,
    │                       #          useQuery, useChat, useIngestStatus, useReset
    │
    ├── components/
    │   ├── AppHeader.vue       # Sticky header: logo + API/Index status badge
    │   ├── DocumentUpload.vue  # Drag&drop + document list + individual delete
    │   ├── IngestPanel.vue     # Ingestion buttons + status polling every 3s
    │   ├── QueryPanel.vue      # Multi-turn chat + SSE streaming + feedback
    │   └── SourcesDisplay.vue  # Source chunks with relevance score
    │
    ├── views/
    │   └── HomeView.vue    # Layout: sidebar | main chat area
    │
    ├── router/
    │   └── index.ts        # createRouter: route "/" → HomeView
    │
    └── tests/
        └── useRag.test.ts  # Composable tests with Vitest
```

### Frontend Rules

**Component conventions:**

- **Always** use `<script setup lang="ts">`. Never Options API or `defineComponent`.
- Each component has **a single responsibility**. If a `.vue` file exceeds 300 lines,
  refactor into sub-components or composables.
- Props always typed with `defineProps<{...}>()`. Never `props: { ... }` from Options API.
- Emits always typed with `defineEmits<{...}>()`.

**API layer (`src/api/ragApi.ts`):**

- **A single file** for all HTTP calls. Components and composables
  **never** call axios directly.
- The axios instance uses `baseURL: '/api'` (the nginx proxy redirects to the backend).
- Type the return of each function: `Promise<DocumentsResponse>`, etc.

```typescript
// ✅ Correct
const api = axios.create({ baseURL: '/api' })
export const getDocuments = (): Promise<DocumentsResponse> =>
  api.get('/documents').then(r => r.data)

// ❌ Forbidden: axios directly in components
const { data } = await axios.get('http://localhost:8000/documents')
```

**Types (`src/types/rag.ts`):**

- Keep synchronized with the Pydantic schemas in the backend. If a schema
  in `rag/models.py` is modified, update the corresponding type in `rag.ts`.
- Use `interface` for data objects, `type` for unions/aliases.

```typescript
// Mirrors of Pydantic schemas
export interface DocumentInfo {
  filename: string
  size: number
  uploaded_at: string
  file_type: string
}

export interface ChatRequest {
  message: string
  session_id?: string
  top_k?: number
}

export type IngestStatus = 'idle' | 'running' | 'done' | 'failed'
```

**Composables (`src/composables/useRag.ts`):**

- Each composable manages its own reactive state (`ref`, `computed`) and
  its side effects.
- Composables return objects with state + actions with explicit names.
- Ingestion polling (every 3s) lives **only** in `useIngestStatus`
  and is cleaned up with `onUnmounted`.

```typescript
// ✅ Correct composable pattern
export function useDocuments() {
  const documents = ref<DocumentInfo[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  const fetchDocuments = async () => {
    loading.value = true
    try {
      documents.value = await getDocuments()
    } catch (e) {
      error.value = 'Error fetching documents'
    } finally {
      loading.value = false
    }
  }

  return { documents, loading, error, fetchDocuments }
}
```

**SSE Streaming:**

- SSE streaming in `QueryPanel.vue` is handled with `fetch` + `ReadableStream`.
  **Never** polling to simulate streaming. **Never** native `EventSource` for
  POST endpoints (EventSource only supports GET).
- Tokens are accumulated in a `ref<string>` and rendered with `marked` +
  `DOMPurify` to prevent XSS.

```typescript
// ✅ Correct pattern: fetch + ReadableStream for SSE with POST
const streamChat = async (message: string) => {
  const response = await fetch('/api/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId.value })
  })
  const reader = response.body!.getReader()
  const decoder = new TextDecoder()
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    currentResponse.value += decoder.decode(value)
  }
}

// ❌ Forbidden: EventSource for POST endpoints
const es = new EventSource('/api/chat/stream')  // ❌ only supports GET
```

**Frontend security:**

- All HTML generated from AI responses must go through `DOMPurify.sanitize()`
  before using `v-html`.
- Do not expose `GOOGLE_API_KEY` or any secret in `VITE_*` variables.
  Only `VITE_API_BASE_URL` is an allowed environment variable in the frontend.

---

## DOCKER — Rules

### Services in `docker-compose.yml`

```yaml
# Dependency order: qdrant → api → frontend
services:
  qdrant:      # pinned image (e.g.: qdrant/qdrant:v1.13.2), data in ./qdrant_storage/
  api:         # port 8000, depends on qdrant with healthcheck, mounts ./backend/data/
  frontend:    # port 80, depends on api with healthcheck, nginx serves dist/
```

### Image version rules

- **Never use `latest`** as a tag. Always pin an exact version:
  - ✅ `qdrant/qdrant:v1.13.2`
  - ✅ `node:22-alpine3.21`
  - ✅ `nginx:1.27-alpine`
  - ✅ `python:3.11-slim`
  - ❌ `qdrant/qdrant:latest`

### Alpine image security — mandatory rule

All Alpine-based images **must include** `apk update && apk upgrade --no-cache`
as the first `RUN` immediately after `FROM`. This patches OS package CVEs
(busybox, musl-libc, libssl, etc.) at build time without needing to change
the base image.

```dockerfile
# ✅ Correct — always after each FROM with Alpine
FROM node:22-alpine3.21 AS builder
RUN apk update && apk upgrade --no-cache

FROM nginx:1.27-alpine AS final
RUN apk update && apk upgrade --no-cache
```

```dockerfile
# ❌ Forbidden — unpatched Alpine image
FROM nginx:1.27-alpine AS final
COPY --from=builder /app/dist /usr/share/nginx/html
```

> **Note:** The `apk upgrade` in Stage 1 (builder) does not affect the final image,
> but is included for consistency. The critical one is always Stage 2 (runtime).

### Correct backend Dockerfile structure (multi-stage)

```dockerfile
# ── Stage 1: builder ────────────────────────────────────────
FROM python:3.11-slim AS builder
RUN apt-get update && apt-get install -y gcc libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: minimal runtime ─────────────────────────────────
FROM python:3.11-slim AS final
RUN apt-get update && apt-get install -y libgl1 libglib2.0-0 curl \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /install /usr/local
WORKDIR /app
# Only files needed for production — never tests/ or eval_pipeline.py
COPY main.py config.py logger.py ./
COPY rag/ ./rag/
RUN mkdir -p /app/data /app/storage /home/appuser /tmp/fastembed_cache \
    && addgroup --system appgroup \
    && adduser --system --ingroup appgroup --home /home/appuser appuser \
    && chown -R appuser:appgroup /app /home/appuser /tmp/fastembed_cache
USER appuser
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Correct frontend Dockerfile structure (multi-stage)

```dockerfile
# ── Stage 1: Build ──────────────────────────────────────────
FROM node:22-alpine3.21 AS builder
RUN apk update && apk upgrade --no-cache
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# ── Stage 2: Serve with nginx ────────────────────────────────
FROM nginx:1.27-alpine AS final
RUN apk update && apk upgrade --no-cache
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
RUN chown -R nginx:nginx /var/cache/nginx /var/log/nginx /usr/share/nginx/html \
    && touch /run/nginx.pid \
    && chown nginx:nginx /run/nginx.pid
USER nginx
EXPOSE 80
```

### Nginx (`frontend/nginx.conf`) — mandatory configuration

```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    client_max_body_size 50M;   # same as MAX_UPLOAD_MB in the backend

    # SPA fallback
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Proxy to backend — SSE directives are CRITICAL, do not remove
    location /api/ {
        proxy_pass http://api:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_buffering off;           # CRITICAL for SSE — never remove
        proxy_cache off;               # CRITICAL for SSE — never remove
        proxy_read_timeout 300s;       # required for long LLM responses
        chunked_transfer_encoding on;  # CRITICAL for SSE — never remove
    }
}
```

### `docker-compose.override.yml` for development

- Backend: mount `./backend:/app` as a single volume (includes `data/` and `storage/`
  implicitly — **do not duplicate** subdirectory mounts) + `--reload`.
- Frontend: no override needed — use `npm run dev` directly with Vite.

```yaml
# ✅ Correct — no redundant mounts
services:
  api:
    volumes:
      - ./backend:/app
      - fastembed_cache:/tmp/fastembed_cache
    command: uvicorn main:app --reload --host 0.0.0.0 --port 8000

# ❌ Forbidden — redundant mounts (data/ and storage/ are already inside /app)
services:
  api:
    volumes:
      - ./backend:/app
      - ./backend/data:/app/data      # redundant
      - ./backend/storage:/app/storage  # redundant
```

### Qdrant image — do not use `nginxinc/nginx-unprivileged`

**Do not migrate** to `nginxinc/nginx-unprivileged` in this project. It would require
changing the port to 8080 and reconfiguring docker-compose.yml, with risk of breaking
the SSE pipeline that is already validated. Keep `nginx:1.27-alpine` with `apk upgrade`.

---

## Environment Variables — Complete Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `GOOGLE_API_KEY` | **required** | Google AI API key |
| `QDRANT_HOST` | `qdrant` | Qdrant service host |
| `QDRANT_PORT` | `6333` | Qdrant port |
| `COLLECTION_NAME` | `facultad_rag` | Qdrant collection name |
| `EMBEDDING_DIM` | `3072` | Gemini Embedding 2 Preview dimension |
| `ENABLE_HYBRID` | `true` | Hybrid dense+sparse BM25 search |
| `ENABLE_RERANKER` | `true` | Cross-encoder reranking |
| `ENABLE_SEMANTIC_CHUNKING` | `false` | Semantic chunking (slower) |
| `ENABLE_HYDE` | `false` | HyDE query transform |
| `API_KEY` | `null` | Bearer token for critical endpoints |
| `MAX_UPLOAD_MB` | `50` | Maximum file size |
| `API_PORT` | `8000` | Backend port |
| `CORS_ORIGINS` | `http://localhost,http://localhost:80,http://localhost:5173` | CORS origins (comma-separated) |

> **Critical:** `EMBEDDING_DIM=3072` must match the collection in Qdrant.
> If the embedding model is changed, delete the collection and re-ingest.

---

## Forbidden Anti-Patterns

### Backend
- ❌ Import `google.generativeai` (use `google.genai` via `llama-index-llms-google-genai`)
- ❌ Instantiate the LLM, embeddings or the index inside an endpoint (only in `lifespan`)
- ❌ Use `os.environ.get()` outside of `config.py`
- ❌ Business logic in `main.py`
- ❌ Inline Pydantic schemas in endpoints

### Frontend
- ❌ Call axios directly from components (always via `ragApi.ts`)
- ❌ Use `v-html` without `DOMPurify.sanitize()`
- ❌ Polling to simulate streaming (use `fetch` + `ReadableStream`)
- ❌ Native `EventSource` for POST endpoints (only supports GET)
- ❌ Environment variables with secrets in `VITE_*`
- ❌ Options API (always `<script setup lang="ts">`)

### Docker
- ❌ Alpine image without `apk update && apk upgrade --no-cache` after `FROM`
- ❌ Use `latest` as an image tag (always pin a version)
- ❌ `proxy_buffering on` in nginx with SSE (cuts the stream)
- ❌ Running containers as `root`
- ❌ Committing `.env` to the repository
- ❌ Redundant subdirectory mounts in override when the parent is already mounted
- ❌ Copying `tests/` or `eval_pipeline.py` into the backend production image

---

## Tests — Conventions

**Backend (`pytest` + `pytest-asyncio` + `httpx`):**
- Each endpoint has at least: 1 happy path test + 1 error case.
- `conftest.py` fixtures provide `AsyncClient` and a mocked index.
- Do not connect to a real Qdrant in unit tests (use mock).
- Do not import `settings` directly in tests — use `override_settings` or test environment variables.

**Frontend (`Vitest`):**
- Composables are tested with `@vue/test-utils` + `vi.mock` for `ragApi.ts`.
- At least 1 test per composable: initial state, successful call, error handling.
- The `ragApi.ts` mock must respect the types defined in `src/types/rag.ts`.
