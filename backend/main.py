import logging
import os
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from dotenv import load_dotenv
from contextlib import asynccontextmanager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Load environment variables
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()  # Try to load from default locations

# Import API routers
from api.auth import router as auth_router
from api.calls import router as calls_router
from api.users import router as users_router
from api.settings import router as settings_router

# Import database
from models.database import engine, Base, get_db

# Set up lifespan events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables if they don't exist
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/verified")
    
    # You could also initialize other resources here
    logger.info("Application startup complete")
    
    yield
    
    # Cleanup on shutdown
    logger.info("Application shutdown")

# Create FastAPI app
app = FastAPI(
    title="RingCentral-Zoho Integration API",
    description="API for integrating RingCentral call data with Zoho CRM",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
app.include_router(calls_router, prefix="/api/calls", tags=["Call Processing"])
app.include_router(users_router, prefix="/api/users", tags=["User Management"])
app.include_router(settings_router, prefix="/api/settings", tags=["Settings"])

# Root endpoint
@app.get("/", tags=["Health Check"])
async def root():
    return {
        "status": "online",
        "api_version": "1.0.0",
        "message": "RingCentral-Zoho Integration API is running"
    }

# Health check endpoint
@app.get("/health", tags=["Health Check"])
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("API_PORT", 8000))
    debug = os.getenv("DEBUG", "false").lower() == "true"
    
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=debug) 