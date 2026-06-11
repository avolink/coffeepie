from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import config
from app.api import cofp_routes, nodes_routes

app = FastAPI(title="Coffee Pie Panel API")

# Browser clients (the panel) call from a different origin, so CORS is required.
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cofp_routes.router)
app.include_router(nodes_routes.router)

# QA-only local login is mounted ONLY when explicitly enabled. In production
# (QA_LOCAL_AUTH unset/false) this router does not exist at all.
if config.QA_LOCAL_AUTH:
    from app.api import auth_routes

    app.include_router(auth_routes.router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "coffeepie-panel-backend",
        "qa_local_auth": config.QA_LOCAL_AUTH,
        "auth_provider": config.AUTH_PROVIDER,
    }
