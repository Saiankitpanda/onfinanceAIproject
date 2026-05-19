from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.api.routes_documents import router as documents_router

app = FastAPI(title="ClauseMark Backend")

frontend_dir = Path(__file__).resolve().parent / "frontend"
app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

app.include_router(documents_router)

@app.get("/")
def serve_frontend():
    return FileResponse(frontend_dir / "index.html")

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "ClauseMark Backend"
    }

