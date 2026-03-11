# RAG Multimodal — Instrucciones para Agente IA

## Contexto del Proyecto

Sistema **RAG Multimodal** fullstack con chat multi-turn y streaming SSE.
Permite subir documentos (PDF, imágenes, texto/markdown), ingestarlos en una
base vectorial y consultarlos mediante chat generado por IA con respuestas en
tiempo real.

**Stack:**
- Backend: Python 3.11 + FastAPI + LlamaIndex + `llama-index-llms-google-genai`
  + Gemini 2.5 Flash + Gemini Embedding 2 Preview + Qdrant
- Frontend: Vue 3 (Composition API) + TypeScript + PrimeVue 4 + Axios + Vite
- Infra: Docker Compose (3 servicios: `qdrant`, `api`, `frontend`)
- Búsqueda: híbrida dense+sparse (BM25 via fastembed) + reranking cross-encoder

---

## Comandos Esenciales

```bash
# Desarrollo (hot-reload via override)
docker compose up -d
docker compose logs -f api

# Producción
docker compose -f docker-compose.yml up -d

# Frontend fuera de Docker
cd frontend && npm run dev   # http://localhost:5173

# Tests backend
cd backend && pytest tests/ -v

# Tests frontend
cd frontend && npm run test
```

---

## Estructura Canónica del Proyecto

```
rag_multimodal/
├── AGENTS.md
├── .env
├── .env.example
├── docker-compose.yml
├── docker-compose.override.yml
├── qdrant_storage/
├── backend/
└── frontend/
```

---

## BACKEND — Reglas y Estructura

### Estructura de carpetas obligatoria

```
backend/
├── main.py               # FastAPI app: lifespan, CORS, routers, rate limiting
├── config.py             # Settings con pydantic-settings (BaseSettings)
├── logger.py             # Logger estructurado JSON con loguru
├── eval_pipeline.py      # CLI para evaluación RAGAS (no tocar en features)
├── requirements.txt
├── Dockerfile
│
├── rag/
│   ├── __init__.py
│   ├── ingest.py         # Pipeline completo: carga → chunking → embed → Qdrant
│   ├── query.py          # RAG single-turn + chat multi-turn + SSE streaming
│   └── models.py         # Schemas Pydantic para TODOS los request/response
│
├── data/                 # Documentos subidos (volumen Docker — NO tocar en código)
├── storage/              # Índice persistido de LlamaIndex (JSON — NO borrar)
│
└── tests/
    ├── conftest.py       # Fixtures: app, client, mock_index
    └── test_api.py       # Tests de integración con httpx + pytest-asyncio
```

### Reglas del Backend

**Módulos y responsabilidades:**

- `main.py` solo contiene: instancia FastAPI, lifespan, middleware, inclusion
  de routers y endpoints simples. **Nunca** lógica de negocio en `main.py`.
- `rag/ingest.py` es el único lugar donde se instancia `SimpleDirectoryReader`,
  `SentenceSplitter`, `GoogleGenAIEmbedding` y se escribe en Qdrant.
- `rag/query.py` es el único lugar donde se instancia `GoogleGenAI` (LLM),
  `ChatMemoryBuffer`, `CondensePlusContextChatEngine` y se genera SSE.
- `rag/models.py` contiene **todos** los schemas Pydantic. Nunca inline en los
  endpoints. Separar siempre `*Request` de `*Response`.
- `config.py` usa `pydantic-settings`. Todos los accesos a variables de entorno
  deben hacerse a través del objeto `settings`. **Nunca** `os.environ.get()`
  directo en los módulos.

**LlamaIndex / Gemini:**

- Usar **siempre** `from llama_index.llms.google_genai import GoogleGenAI`
  (nunca `from llama_index.llms.gemini import Gemini` — está deprecado).
- Usar **siempre** `from llama_index.embeddings.google_genai import GoogleGenAIEmbedding`
  (nunca `GeminiEmbedding`).
- Modelo LLM: `gemini-2.5-flash` por defecto.
- Modelo Embedding: `models/gemini-embedding-2-preview` con `EMBEDDING_DIM=3072`.
- El índice se carga desde Qdrant en el `lifespan` startup. Si no existe, se
  crea vacío. **Nunca** recrear el índice en cada request.

**Seguridad (no omitir en ninguna feature):**

- Validar tipo de archivo con `filetype` (magic bytes), nunca solo por extensión.
- Proteger `DELETE /documents/{filename}` contra path traversal usando
  `pathlib.Path` y verificando que el archivo esté dentro de `./data/`.
- Si `settings.API_KEY` está definida, exigir `Authorization: Bearer <token>`.
  Aplicar el `Depends(verify_api_key)` a todos los endpoints que modifican estado.
- Rate limiting con `slowapi` según la tabla de endpoints definida más abajo.
- CORS restringido: nunca usar `allow_origins=["*"]` en producción.

**Patrones de código obligatorios:**

```python
# ✅ Correcto: async endpoints con tipo de retorno explícito
@router.post("/upload", response_model=UploadResponse, status_code=201)
async def upload_file(file: UploadFile = File(...)) -> UploadResponse:
    ...

# ✅ Correcto: background tasks para ingestión
@router.post("/ingest")
async def start_ingest(background_tasks: BackgroundTasks) -> IngestResponse:
    background_tasks.add_task(run_ingest_pipeline)
    ...

# ✅ Correcto: SSE streaming con EventSourceResponse
@router.post("/chat/stream")
async def chat_stream(req: ChatRequest) -> EventSourceResponse:
    async def generator():
        async for token in engine.astream_chat(req.message):
            yield {"event": "token", "data": token.delta}
        yield {"event": "sources", "data": json.dumps(sources)}
    return EventSourceResponse(generator())

# ❌ Prohibido: lógica de negocio en endpoints
@router.post("/query")
async def query(req: QueryRequest):
    results = qdrant_client.search(...)  # ❌ acceso directo a DB en endpoint
    llm = GoogleGenAI(...)               # ❌ instanciación en cada request
```

**Manejo de errores:**

```python
# Usar siempre HTTPException con detalle descriptivo
raise HTTPException(status_code=422, detail="Tipo de archivo no soportado")

# Logger estructurado en todos los errores no controlados
logger.exception("Error en ingestión: {error}", error=str(e))
```

**Endpoints de la API (referencia para implementación):**

| Método | Ruta | Rate Limit | Auth Requerida |
|--------|------|-----------|----------------|
| GET | `/health` | — | No |
| POST | `/upload` | 10/min | Si API_KEY definida |
| GET | `/documents` | — | No |
| DELETE | `/documents/{filename}` | — | Sí |
| POST | `/ingest` | 5/min | Sí |
| GET | `/ingest/status` | — | No |
| POST | `/query` | 20/min | No |
| POST | `/chat` | 20/min | No |
| POST | `/chat/stream` | 20/min | No |
| DELETE | `/chat/{session_id}` | — | No |
| GET | `/collections` | — | No |
| DELETE | `/collection` | — | Sí |
| POST | `/feedback` | — | No |

---

## FRONTEND — Reglas y Estructura

### Estructura de carpetas obligatoria

```
frontend/
├── package.json
├── vite.config.ts
├── tsconfig.json
├── nginx.conf              # SPA fallback + proxy /api/ → backend:8000
├── Dockerfile
│
└── src/
    ├── main.ts             # Bootstrap: createApp + PrimeVue + Router + Pinia
    ├── App.vue             # Root component: <Toast /> + <RouterView />
    ├── style.css           # Variables CSS globales (dark mode, glassmorphism)
    │
    ├── api/
    │   └── ragApi.ts       # Única fuente de verdad para llamadas HTTP
    │                       # Axios instance con baseURL=/api, interceptors
    │
    ├── types/
    │   └── rag.ts          # Interfaces TypeScript: mirrors de schemas Pydantic
    │
    ├── composables/        # Lógica de estado y side effects (un composable por dominio)
    │   └── useRag.ts       # Exporta: useHealth, useDocuments, useIngest,
    │                       #          useQuery, useChat, useIngestStatus, useReset
    │
    ├── components/
    │   ├── AppHeader.vue       # Header sticky: logo + badge estado API/Index
    │   ├── DocumentUpload.vue  # Drag&drop + lista documentos + eliminar individual
    │   ├── IngestPanel.vue     # Botones ingestión + polling estado cada 3s
    │   ├── QueryPanel.vue      # Chat multi-turn + SSE streaming + feedback
    │   └── SourcesDisplay.vue  # Chunks fuente con score de relevancia
    │
    ├── views/
    │   └── HomeView.vue    # Layout: sidebar | área chat principal
    │
    ├── router/
    │   └── index.ts        # createRouter: ruta "/" → HomeView
    │
    └── tests/
        └── useRag.test.ts  # Tests de composables con Vitest
```

### Reglas del Frontend

**Convenciones de componentes:**

- Usar **siempre** `<script setup lang="ts">`. Nunca Options API ni `defineComponent`.
- Cada componente tiene **una sola responsabilidad**. Si un `.vue` supera 300 líneas,
  refactorizar en sub-componentes o composables.
- Props siempre tipadas con `defineProps<{...}>()`. Nunca `props: { ... }` de Options API.
- Emits siempre tipados con `defineEmits<{...}>()`.

**Capa de API (`src/api/ragApi.ts`):**

- **Un único archivo** para todas las llamadas HTTP. Los componentes y composables
  **nunca** llaman a axios directamente.
- La instancia axios usa `baseURL: '/api'` (el proxy de nginx redirige al backend).
- Tipar el retorno de cada función: `Promise<DocumentsResponse>`, etc.

```typescript
// ✅ Correcto
const api = axios.create({ baseURL: '/api' })
export const getDocuments = (): Promise<DocumentsResponse> =>
  api.get('/documents').then(r => r.data)

// ❌ Prohibido: axios directamente en componentes
const { data } = await axios.get('http://localhost:8000/documents')
```

**Tipos (`src/types/rag.ts`):**

- Mantener sincronizados con los schemas Pydantic del backend. Si se modifica un
  schema en `rag/models.py`, actualizar el tipo correspondiente en `rag.ts`.
- Usar `interface` para objetos de datos, `type` para uniones/alias.

```typescript
// Mirrors de los schemas Pydantic
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

- Cada composable maneja su propio estado reactivo (`ref`, `computed`) y
  sus side effects.
- Los composables devuelven objetos con state + actions con nombres explícitos.
- El polling de ingestión (cada 3s) vive **únicamente** en `useIngestStatus`
  y se limpia con `onUnmounted`.

```typescript
// ✅ Patrón correcto de composable
export function useDocuments() {
  const documents = ref<DocumentInfo[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  const fetchDocuments = async () => {
    loading.value = true
    try {
      documents.value = await getDocuments()
    } catch (e) {
      error.value = 'Error al obtener documentos'
    } finally {
      loading.value = false
    }
  }

  return { documents, loading, error, fetchDocuments }
}
```

**SSE Streaming:**

- El streaming SSE en `QueryPanel.vue` se maneja con `EventSource` nativo o
  `fetch` con `ReadableStream`. **Nunca** polling para simular streaming.
- Los tokens se acumulan en un `ref<string>` y se renderizan con `marked` +
  `DOMPurify` para prevenir XSS.

```typescript
// ✅ Patrón SSE con fetch streaming
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
```

**Seguridad en frontend:**

- Todo HTML generado desde respuestas de IA debe pasar por `DOMPurify.sanitize()`
  antes de usar `v-html`.
- No exponer `GOOGLE_API_KEY` ni ningún secret en variables `VITE_*`.
  Solo `VITE_API_BASE_URL` es variable de entorno permitida en frontend.

---

## DOCKER — Reglas

**Tres servicios en `docker-compose.yml`:**

```yaml
# Orden de dependencias: qdrant → api → frontend
services:
  qdrant:      # puerto 6333 (REST) + 6334 (gRPC), datos en ./qdrant_storage/
  api:         # puerto 8000, depende de qdrant, lee .env, monta ./backend/data/
  frontend:    # puerto 80, Nginx sirve dist/ + proxy /api/ → api:8000
```

**Nginx (`frontend/nginx.conf`) debe tener:**

```nginx
location /api/ {
    proxy_pass http://api:8000/;   # proxy al backend interno
    proxy_set_header Host $host;
    proxy_buffering off;           # CRÍTICO para SSE streaming
    proxy_cache off;               # CRÍTICO para SSE streaming
    chunked_transfer_encoding on;  # CRÍTICO para SSE streaming
}

location / {
    try_files $uri $uri/ /index.html;  # SPA fallback
}
```

**Dockerfiles — reglas:**

- Backend: imagen base `python:3.11-slim`. Copiar solo lo necesario (no `tests/`,
  no `.env`). Ejecutar con usuario no-root.
- Frontend: multi-stage (`node:20-alpine` para build, `nginx:stable-alpine` para serve).
- Siempre incluir `.dockerignore` en ambos servicios.

**`docker-compose.override.yml` para desarrollo:**

- Backend: montar `./backend:/app` como volumen + `command: uvicorn main:app --reload`
- Frontend: no se usa en override (usar `npm run dev` directamente con Vite)

---

## Variables de Entorno — Referencia Completa

| Variable | Default | Descripción |
|----------|---------|-------------|
| `GOOGLE_API_KEY` | **requerida** | API key de Google AI |
| `QDRANT_HOST` | `qdrant` | Host del servicio Qdrant |
| `QDRANT_PORT` | `6333` | Puerto Qdrant |
| `COLLECTION_NAME` | `facultad_rag` | Nombre colección Qdrant |
| `EMBEDDING_DIM` | `3072` | Dimensión Gemini Embedding 2 Preview |
| `ENABLE_HYBRID` | `true` | Búsqueda híbrida dense+sparse BM25 |
| `ENABLE_RERANKER` | `true` | Cross-encoder reranking |
| `ENABLE_SEMANTIC_CHUNKING` | `false` | Chunking semántico (más lento) |
| `ENABLE_HYDE` | `false` | HyDE query transform |
| `API_KEY` | `null` | Bearer token para endpoints críticos |
| `MAX_UPLOAD_MB` | `50` | Tamaño máximo de archivos |
| `API_PORT` | `8000` | Puerto del backend |
| `CORS_ORIGINS` | `http://localhost:80` | Orígenes permitidos (separados por coma) |

> **Crítico:** `EMBEDDING_DIM=3072` debe coincidir con la colección en Qdrant.
> Si se cambia el modelo de embedding, eliminar la colección y reingestár.

---

## Anti-Patrones Prohibidos

### Backend
- ❌ Importar `google.generativeai` (usar `google.genai` via `llama-index-llms-google-genai`)
- ❌ Instanciar el LLM, embeddings o el índice dentro de un endpoint (solo en `lifespan`)
- ❌ Usar `os.environ.get()` fuera de `config.py`
- ❌ Lógica de negocio en `main.py`
- ❌ Schemas Pydantic inline en los endpoints

### Frontend
- ❌ Llamar a axios directamente desde componentes (siempre vía `ragApi.ts`)
- ❌ Usar `v-html` sin `DOMPurify.sanitize()`
- ❌ Polling para simular streaming (usar SSE/ReadableStream)
- ❌ Variables de entorno con secrets en `VITE_*`
- ❌ Options API (siempre `<script setup lang="ts">`)

### Docker
- ❌ `proxy_buffering on` en nginx cuando hay SSE (corta el stream)
- ❌ Correr contenedores como `root`
- ❌ Commitear `.env` al repositorio (agregar a `.gitignore`)

---

## Tests — Convenciones

**Backend (`pytest` + `pytest-asyncio` + `httpx`):**
- Cada endpoint tiene al menos: 1 test happy path + 1 error case.
- Los fixtures de `conftest.py` proveen `AsyncClient` y un índice mockeado.
- No conectar a Qdrant real en tests unitarios (usar mock).

**Frontend (`Vitest`):**
- Los composables se testean con `@vue/test-utils` + `vi.mock` para `ragApi.ts`.
- Al menos 1 test por composable: estado inicial, llamada exitosa, manejo de error.
