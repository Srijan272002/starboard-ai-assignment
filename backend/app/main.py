from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import api_router
from app.core.config import settings
from app.core.logging import setup_logging

# Setup logging
setup_logging()

app = FastAPI(
    title="Starboard AI Property Analysis",
    description="Multi-County Property Analysis System",
    version="1.0.0",
)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix="/api/v1")

@app.get("/")
async def root():
    return {"message": "Starboard AI Property Analysis System"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"} 