from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import workbooks, jobs, model_workflows, explorations
from app.middleware.rate_limiter import RateLimitMiddleware
from app.middleware.secure_headers import SecureHeadersMiddleware
from app.middleware.error_handler import global_exception_handler
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

app = FastAPI(title="TabuLens API")

# 1. Global Exception Handler
app.add_exception_handler(RequestValidationError, global_exception_handler)
app.add_exception_handler(StarletteHTTPException, global_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)

# 2. Secure Headers Middleware
app.add_middleware(SecureHeadersMiddleware)

# 3. Rate Limiting Middleware (100 requests per minute for /api/*)
app.add_middleware(RateLimitMiddleware, window_ms=60000, limit=100, path_prefix="/api")

# 4. Configure CORS
# In production, this should be restricted to specific origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:29384"],  # Match the new frontend port
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
)

app.include_router(workbooks.router, prefix="/api/workbooks", tags=["workbooks"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(model_workflows.router, prefix="/api/model-workflows", tags=["model-workflows"])
app.include_router(explorations.router, prefix="/api/explorations", tags=["explorations"])

@app.get("/api")
async def root():
    return {"message": "Welcome to TabuLens API"}

# --- Static File Serving ---
# Adjust this path based on your deployment structure
# This assumes apps/web/dist exists (built via pnpm build)
frontend_path = os.path.join(os.path.dirname(__file__), "..", "..", "web", "dist")

if os.path.exists(frontend_path):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_path, "assets")), name="static")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # If it's an API call that wasn't matched, it should return 404 naturally
        # but for SPA routing, we serve index.html for non-asset/non-api paths
        if full_path.startswith("api"):
            return {"detail": "Not Found"}

        index_file = os.path.join(frontend_path, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"detail": "Frontend not built. Run 'pnpm build' in apps/web."}
else:
    @app.get("/")
    async def root_fallback():
        return {"message": "TabuLens API is running. Frontend dist not found."}
