# RAG Multimodal

> **Local test project** — a complete RAG system built with AI assistance (Claude Code, Gemini, GitHub Copilot / Codex) as a learning experiment and technology exploration. Not intended for production use.

A **Multimodal RAG (Retrieval-Augmented Generation)** system with a containerized fullstack architecture. It allows uploading documents (PDF, images, text), ingesting them into a vector database, and querying them through a multi-turn chat with AI-generated responses and real-time streaming.

---

## Warning

This project was developed **exclusively for local testing and learning purposes**. It does not include production hardening, and requires a Google AI API key to function. It is not recommended to deploy it in internet-facing environments without additional security review.

It was built with the support of generative AI tools:
- **[Claude Code](https://claude.ai/code)** (Anthropic) — primary development assistant
- **Gemini 2.5 Flash / Gemini Embedding 2** (Google) — LLM and embeddings for the RAG pipeline
- **GitHub Copilot / Codex** (OpenAI / GitHub) — code suggestions

---

## What it can do

- **Upload documents:** PDF, images (PNG/JPG), plain text and Markdown, up to 50 MB per file
- **Ingest:** configurable chunking (fixed or semantic), multimodal embeddings with Gemini, storage in Qdrant with hybrid dense + sparse search (BM25)
- **Single-turn query:** direct query with cross-encoder reranking and optional HyDE support (Hypothetical Document Embeddings)
- **Multi-turn chat:** conversation with session memory, token-by-token streaming response via SSE
- **Multiple collections:** create and manage independent Qdrant collections from the UI
- **Evaluate the pipeline:** RAGAS-style metrics (faithfulness, relevancy, recall, precision) without depending on the ragas library
- **Per-message feedback:** thumbs up/down stored in `feedback.jsonl`
- **Export conversations:** download chat history as Markdown

---

## Technology stack

| Layer | Technology |
|---|---|
| **LLM** | Gemini 2.5 Flash (`gemini-2.5-flash`) |
| **Embeddings** | Gemini Embedding 2 Preview (3072 dimensions) |
| **Vector DB** | Qdrant 1.13 with hybrid dense+sparse search |
| **RAG Framework** | LlamaIndex 0.12 |
| **Backend** | Python 3.11, FastAPI, pydantic-settings |
| **Frontend** | Vue 3 (Composition API), TypeScript, Vite, PrimeVue 4, Tailwind CSS 4 |
| **State** | Pinia + localStorage |
| **Infrastructure** | Docker Compose (3 services), Nginx, multi-stage builds |

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- A [Google AI Studio API Key](https://aistudio.google.com/app/apikey) (free with quotas)

---

## Installation and setup

### 1. Clone the repository

```bash
git clone <url-del-repo>
cd rag_multimodal
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and set your Google API key:

```
GOOGLE_API_KEY=tu_api_key_aqui
```

The remaining values can be left at their defaults.

### 3. Start the services

```bash
docker compose up -d
```

This starts three containers:
- **qdrant** — vector database on port `6333`
- **api** — FastAPI backend on port `8000`
- **frontend** — Nginx serving the SPA on port `80`

The first run may take several minutes because it downloads the base images and compiles the fastembed model (~500 MB, cached in a Docker volume).

### 4. Open the application

Go to `http://localhost` in your browser.

---

## Basic usage

1. **Upload documents** from the left sidebar (drag & drop or file picker)
2. **Ingest** using the "Ingestar documentos" button — wait until the status changes to `done`
3. **Chat** in the main panel — responses arrive token by token with cited sources
4. For one-off queries without history, use the **Query** tab in the right sidebar

---

## Advanced configuration

The following variables in `.env` control the pipeline behavior:

| Variable | Default | Description |
|---|---|---|
| `GOOGLE_API_KEY` | **required** | Google AI (Gemini) API key |
| `COLLECTION_NAME` | `facultad_rag` | Default Qdrant collection |
| `EMBEDDING_DIM` | `3072` | Must match the embedding model |
| `ENABLE_HYBRID` | `true` | Hybrid dense+sparse search (BM25) |
| `ENABLE_RERANKER` | `true` | Reranking with local cross-encoder |
| `ENABLE_HYDE` | `false` | HyDE query transform |
| `ENABLE_SEMANTIC_CHUNKING` | `false` | Semantic chunking (requires re-ingestion) |
| `API_KEY` | empty | Optional bearer token to protect the API |
| `MAX_UPLOAD_MB` | `50` | Maximum uploaded file size |
| `API_PORT` | `8000` | Backend port |

> Changing `ENABLE_HYDE` at runtime via `PUT /config` automatically invalidates cached chat sessions.
> Changing `ENABLE_SEMANTIC_CHUNKING` requires re-ingesting all documents.

---

## Local development (without Docker)

### Backend

```bash
cd backend
pip install -r requirements.txt
# Qdrant must be running (e.g. with Docker: docker run -p 6333:6333 qdrant/qdrant)
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev   # Vite en http://localhost:5173 (con proxy /api → localhost:8000)
```

### Tests

```bash
# Backend
cd backend && pytest tests/ -v

# Frontend
cd frontend && npx vitest run
```

---

## Project structure

```
rag_multimodal/
├── .env.example                  # Environment variables template
├── docker-compose.yml            # Production
├── docker-compose.override.yml   # Development (backend hot-reload)
│
├── backend/
│   ├── main.py                   # FastAPI app — all endpoints
│   ├── config.py                 # Centralized settings (pydantic-settings)
│   ├── logger.py                 # Structured JSON logger (loguru)
│   ├── eval_pipeline.py          # RAG evaluation CLI
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── data/                     # Uploaded documents (Docker volume)
│   ├── storage/                  # Persisted LlamaIndex index (Docker volume)
│   └── rag/
│       ├── ingest.py             # Pipeline: load → chunking → embed → Qdrant
│       ├── query.py              # RAG Query + Multi-turn Chat + SSE + HyDE
│       ├── eval.py               # RAGAS-style evaluation (without ragas library)
│       └── models.py             # Pydantic schemas
│
└── frontend/
    ├── nginx.conf                # SPA fallback + proxy /api/ → backend
    ├── Dockerfile
    └── src/
        ├── api/ragApi.ts         # HTTP client (axios + fetch SSE)
        ├── composables/useRag.ts # Encapsulated business logic
        ├── stores/               # Pinia: conversations + collections
        ├── components/           # AppHeader, QueryPanel, EvalPanel, etc.
        └── views/                # HomeView, SettingsView, EvalView
```

---

## Main endpoints

| Method | Route | Description |
|---|---|---|
| `GET` | `/health` | Service and index status |
| `POST` | `/upload` | Upload document (multipart, 10/min) |
| `GET` | `/documents` | List uploaded documents |
| `DELETE` | `/documents/{filename}` | Delete document and its vectors |
| `POST` | `/ingest` | Start background ingestion (5/min) |
| `GET` | `/ingest/status` | Status: `idle \| running \| done \| failed` |
| `POST` | `/query` | Single-turn RAG query (20/min) |
| `POST` | `/chat/stream` | Multi-turn chat with SSE streaming (20/min) |
| `DELETE` | `/chat/{session_id}` | Clear chat session |
| `GET` | `/collections` | List Qdrant collections |
| `POST` | `/collections` | Create new collection |
| `DELETE` | `/collection` | Full reset of the active collection |
| `PUT` | `/config` | Update configuration at runtime |
| `POST` | `/eval` | Start RAG evaluation |
| `POST` | `/feedback` | Record quality feedback |

---

## License

No license defined — personal experimental project. Free to use as a reference.
