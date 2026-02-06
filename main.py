"""
Mood Your Weather Backend API
FastAPI application con Firebase Authentication e Realtime Database
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import firebase_config  # Inizializza Firebase

# Import routers
from routers import auth, moods, stats, weather, sync, nlp, export, challenges


# ==================== Lifespan Events ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestione lifecycle applicazione"""
    # Startup
    print("🚀 Mood Your Weather API starting...")
    print("📱 Firebase connected")
    print("🌤️  Weather service ready")
    print("📊 Ready to track moods!")
    
    yield
    
    # Shutdown
    print("👋 Shutting down Mood Your Weather API...")


# ==================== App Configuration ====================

app = FastAPI(
    title="Mood Your Weather API",
    description="Backend API per l'app Mood Your Weather - Track your mood with weather context",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)


# ==================== CORS Configuration ====================

# Configurazione CORS per permettere richieste dal frontend mobile
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8081",  # Expo dev
        "capacitor://localhost",  # Capacitor iOS
        "ionic://localhost",      # Capacitor Android
        # Aggiungi domini produzione
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== Include Routers ====================

app.include_router(auth.router)
app.include_router(moods.router)
app.include_router(stats.router)
app.include_router(weather.router)
app.include_router(sync.router)
app.include_router(nlp.router)
app.include_router(export.router)
app.include_router(challenges.router)


# ==================== Root Endpoints ====================

@app.get("/")
async def root():
    """Root endpoint con info API"""
    return {
        "name": "Mood Your Weather API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "endpoints": {
            "auth": "/auth",
            "moods": "/moods",
            "stats": "/stats",
            "weather": "/weather",
            "sync": "/sync",
            "nlp": "/nlp (skeleton)",
            "export": "/export (skeleton)",
            "challenges": "/challenges"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "firebase": "connected",
        "timestamp": "2026-01-23"
    }


# ==================== Error Handlers ====================

@app.exception_handler(404)
async def not_found_handler(request, exc):
    """Handler per 404"""
    return JSONResponse(
        status_code=404,
        content={
            "error": "Not Found",
            "detail": f"Path {request.url.path} not found",
            "docs": "/docs"
        }
    )


@app.exception_handler(500)
async def internal_error_handler(request, exc):
    """Handler per 500"""
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "detail": "An unexpected error occurred"
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
