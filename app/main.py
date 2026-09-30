from fastapi import FastAPI

from app.auth.routes import router as auth_router

app = FastAPI(title="Entreprise RAG System")
app.include_router(auth_router)