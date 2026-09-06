from fastapi import FastAPI, Request
from fastapi.openapi.docs import get_redoc_html
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.database import Base, engine
from app.routers import auth, links, dashboard, redirect
from app.routers.auth import NotLoggedInUI

# Creates data/app.db and all tables on first run if they don't exist yet.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Link Shortener", version="0.6.0", redoc_url=None)

app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/redoc", include_in_schema=False)
async def redoc_html():
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - ReDoc",
        redoc_js_url="/static/js/redoc.standalone.js",
    )


@app.exception_handler(NotLoggedInUI)
async def not_logged_in_handler(request: Request, exc: NotLoggedInUI):
    return RedirectResponse("/login", status_code=303)


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/dashboard", status_code=303)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(links.router)
app.include_router(dashboard.router)
app.include_router(redirect.router)
