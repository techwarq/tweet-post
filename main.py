"""Main FastAPI application for Twitter Post Generator."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import router

# Create FastAPI application
app = FastAPI(
    title="Twitter Post Generator API",
    description="API for scraping Twitter profiles, analyzing engagement patterns, and generating viral posts",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

# Include router
app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)