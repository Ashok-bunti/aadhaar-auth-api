from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router
from app.core.config import SAVE_DIR
from app.core.db import check_db_connection

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Check MongoDB on startup
    if await check_db_connection():
        print("✅ MongoDB Atlas Connected Successfully")
    else:
        print("❌ MongoDB Atlas Connection Failed")
    yield

app = FastAPI(title="Aadhaar KYC Verification", lifespan=lifespan)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for extracted photos
app.mount("/saved_images", StaticFiles(directory=SAVE_DIR), name="saved_images")

# Include API routes
app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
