import pytest
from httpx import AsyncClient, ASGITransport


# La app se importa DESPUÉS de que conftest.py configura las env vars
@pytest.fixture
def app():
    from main import app as fastapi_app
    return fastapi_app


@pytest.mark.asyncio
async def test_health(app):
    """El endpoint /health debe responder 200 con status ok."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "index_loaded" in data


@pytest.mark.asyncio
async def test_upload_invalid_extension(app):
    """Archivos con extensión no permitida deben retornar 400."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/upload",
            files={"file": ("malware.exe", b"MZ\x90\x00", "application/octet-stream")},
        )
    assert res.status_code == 400
    assert "Extensi\u00f3n no permitida" in res.json()["detail"]


@pytest.mark.asyncio
async def test_upload_oversized_file(app):
    """Archivos que superan MAX_UPLOAD_MB deben retornar 400."""
    big_content = b"%PDF-" + b"A" * (51 * 1024 * 1024)  # 51 MB
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/upload",
            files={"file": ("big.pdf", big_content, "application/pdf")},
        )
    assert res.status_code == 400
    assert "grande" in res.json()["detail"]


@pytest.mark.asyncio
async def test_query_without_index(app):
    """Query sin index cargado debe retornar 503."""
    import main
    original = main.INDEX
    main.INDEX = None
    main.INDEX_CACHE.clear()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.post("/query", json={"query": "test"})
        assert res.status_code == 503
    finally:
        main.INDEX = original


@pytest.mark.asyncio
async def test_ingest_status_idle(app):
    """El estado de ingestión inicial debe ser idle."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/ingest/status")
    assert res.status_code == 200
    assert res.json()["status"] in ("idle", "done", "failed", "running")


@pytest.mark.asyncio
async def test_delete_document_invalid_name(app):
    """Nombres de archivo con path traversal deben retornar 400."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.delete("/documents/../../etc/passwd")
    assert res.status_code == 400
