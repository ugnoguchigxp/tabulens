from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import workbooks, jobs, model_workflows, explorations
from app.middleware.rate_limiter import RateLimitMiddleware
from app.middleware.secure_headers import SecureHeadersMiddleware
from app.middleware.error_handler import global_exception_handler
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

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

@app.get("/")
async def root():
    return {"message": "Welcome to TabuLens API"}
