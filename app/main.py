from fastapi import FastAPI

from app.auth.routes import router as auth_router
from app.routes.documents import router as documents_router

app = FastAPI(title="Entreprise RAG System")
app.include_router(auth_router)
app.include_router(documents_router)