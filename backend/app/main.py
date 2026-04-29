"""FastAPI application main file"""
import asyncio
from fastapi import FastAPI, Request, status, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from contextlib import asynccontextmanager
from app.config import settings
from app.database import connect_to_mongo, close_mongo_connection
from app.routes import auth, datasets
from app.routes import chat as chat_routes
from app.routes import dashboard as dashboard_routes
from app.routes import test_direct_query
from app.services.langchain_agent import _get_sql_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events"""
    # Startup
    await connect_to_mongo()

    # Warm up LangChain SQLDatabase cache (read-only) so first query is fast
    sql_db_ready = False
    try:
        print("[Main] Warming up SQLDatabase cache (read-only)...")
        await asyncio.to_thread(_get_sql_db)
        print("[Main] SQLDatabase cache ready")
        sql_db_ready = True
    except Exception as e:
        # Do not block app startup if SQL Server is temporarily unavailable
        print(f"[Main] SQLDatabase warm-up failed: {e}")

    # Launch background DB snapshot pre-fetch for all roles (executive, sales, operations).
    # Runs after the SQL DB cache is ready so queries reuse the warm connection.
    # Non-blocking — server is fully ready before snapshots complete.
    if sql_db_ready:
        try:
            from app.services.db_snapshot import run_all_snapshots
            asyncio.create_task(run_all_snapshots())
            print("[Main] DB snapshot pre-fetch task launched in background")
        except Exception as e:
            print(f"[Main] DB snapshot task launch failed: {e}")
    else:
        print("[Main] DB snapshot pre-fetch skipped (SQL DB not available)")

    yield
    # Shutdown
    await close_mongo_connection()


app = FastAPI(
    title="SPARSLens API",
    description="Backend API for DataLens application",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,      # disable default /docs
    redoc_url=None,     # disable default /redoc
    openapi_url=None,   # hide openapi.json from unauthenticated requests
)

# CORS middleware - must be added before routes
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": str(exc) if str(exc) else "Internal server error",
            "type": type(exc).__name__
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Validation exception handler"""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()}
    )

# Include routers
app.include_router(auth.router, prefix="/api")
app.include_router(datasets.router, prefix="/api")
app.include_router(chat_routes.router, prefix="/api")
app.include_router(dashboard_routes.router, prefix="/api")
app.include_router(test_direct_query.router, prefix="/api")


@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "SPARSLens API is running"}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/debug/cors")
async def debug_cors():
    """Debug endpoint to check CORS configuration"""
    return {
        "cors_origins": settings.CORS_ORIGINS,
        "cors_origins_type": str(type(settings.CORS_ORIGINS))
    }


# ---------------------------------------------------------------------------
# Password-gated Swagger UI
# ---------------------------------------------------------------------------

_DOCS_PASSWORD_GATE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>SPARSLens API Docs</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      background: #0f1117;
      font-family: 'Segoe UI', system-ui, sans-serif;
    }
    .card {
      background: #1a1d27;
      border: 1px solid #2a2d3d;
      border-radius: 12px;
      padding: 2.5rem 2rem;
      width: 100%;
      max-width: 380px;
      box-shadow: 0 20px 60px rgba(0,0,0,.5);
    }
    .logo {
      font-size: 1.5rem;
      font-weight: 700;
      color: #fff;
      text-align: center;
      margin-bottom: .25rem;
    }
    .sub {
      text-align: center;
      color: #6b7280;
      font-size: .85rem;
      margin-bottom: 2rem;
    }
    label {
      display: block;
      font-size: .8rem;
      color: #9ca3af;
      margin-bottom: .4rem;
      letter-spacing: .04em;
      text-transform: uppercase;
    }
    .input-wrap { position: relative; }
    input[type=password], input[type=text] {
      width: 100%;
      padding: .7rem 2.6rem .7rem .9rem;
      background: #0f1117;
      border: 1px solid #2a2d3d;
      border-radius: 8px;
      color: #f3f4f6;
      font-size: .95rem;
      outline: none;
      transition: border-color .2s;
    }
    input:focus { border-color: #6366f1; }
    .toggle-eye {
      position: absolute;
      right: .75rem;
      top: 50%;
      transform: translateY(-50%);
      background: none;
      border: none;
      cursor: pointer;
      color: #6b7280;
      font-size: 1rem;
      line-height: 1;
    }
    .error {
      margin-top: .6rem;
      color: #f87171;
      font-size: .82rem;
      min-height: 1.1rem;
    }
    button.submit {
      margin-top: 1.5rem;
      width: 100%;
      padding: .75rem;
      background: #6366f1;
      color: #fff;
      border: none;
      border-radius: 8px;
      font-size: .95rem;
      font-weight: 600;
      cursor: pointer;
      transition: background .2s;
    }
    button.submit:hover { background: #4f46e5; }
    button.submit:active { background: #4338ca; }
  </style>
</head>
<body>
  <div class="card">
    <div class="logo">SPARSLens API</div>
    <div class="sub">Enter password to access the documentation</div>
    <label for="pwd">Password</label>
    <div class="input-wrap">
      <input type="password" id="pwd" placeholder="••••••••••" autocomplete="current-password" />
      <button class="toggle-eye" type="button" onclick="togglePwd()" id="eyeBtn" title="Show/hide">👁</button>
    </div>
    <div class="error" id="err"></div>
    <button class="submit" onclick="unlock()">Access Docs</button>
  </div>
  <script>
    function togglePwd() {
      const f = document.getElementById('pwd');
      f.type = f.type === 'password' ? 'text' : 'password';
    }
    async function unlock() {
      const pwd = document.getElementById('pwd').value;
      const err = document.getElementById('err');
      err.textContent = '';
      const res = await fetch('/docs-unlock', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password: pwd })
      });
      if (res.ok) {
        window.location.href = '/docs-ui';
      } else {
        err.textContent = 'Incorrect password. Please try again.';
        document.getElementById('pwd').value = '';
        document.getElementById('pwd').focus();
      }
    }
    document.getElementById('pwd').addEventListener('keydown', e => {
      if (e.key === 'Enter') unlock();
    });
  </script>
</body>
</html>
"""


@app.get("/docs", include_in_schema=False)
async def docs_gate():
    """Password gate page for Swagger UI"""
    return HTMLResponse(_DOCS_PASSWORD_GATE_HTML)


@app.post("/docs-unlock", include_in_schema=False)
async def docs_unlock(payload: dict):
    """Verify the docs password"""
    if payload.get("password") != settings.DOCS_PASSWORD:
        raise HTTPException(status_code=401, detail="Incorrect password")
    return {"ok": True}


@app.get("/docs-ui", include_in_schema=False)
async def docs_ui():
    """Actual Swagger UI — only reachable after password check"""
    return get_swagger_ui_html(openapi_url="/openapi.json", title="SPARSLens API – Docs")


@app.get("/openapi.json", include_in_schema=False)
async def openapi_schema():
    """Serve the OpenAPI schema (reached via /docs-ui)"""
    return get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

