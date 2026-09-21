from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.security import APIKeyHeader
from fastapi.responses import HTMLResponse, RedirectResponse
import os
from dotenv import load_dotenv
from app.api import proxmox_routes, auth_routes, users, companies, vms, terminals
from app.api.snapshots import router as snapshots_router

load_dotenv()

# API Key for docs protection
API_KEY = os.getenv("DOCS_API_KEY", "your-docs-key")
api_key_header = APIKeyHeader(name="X-API-Key")

async def verify_api_key(api_key: str = Depends(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authenticated"
        )
    return api_key

# Create app with docs_url set to None initially
app = FastAPI(
    title="Proxmox API Proxy",
    docs_url=None,  # Disable default docs
    redoc_url=None
)

# Add custom docs endpoint with authentication
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi

@app.get("/docs", include_in_schema=False, response_class=HTMLResponse)
async def get_docs(key: str = None):
    """Show Swagger UI only if API key is provided"""
    if not key or key != API_KEY:
        return RedirectResponse(url="/docs-login")
    
    return get_swagger_ui_html(
        openapi_url=f"/openapi.json?key={key}",
        title="Proxmox API - Swagger UI"
    )

@app.get("/docs-login", include_in_schema=False, response_class=HTMLResponse)
async def docs_login():
    """Show login form for API key"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Proxmox API - Authentication</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            }
            .login-container {
                background: white;
                padding: 40px;
                border-radius: 10px;
                box-shadow: 0 10px 25px rgba(0, 0, 0, 0.2);
                width: 400px;
            }
            h1 {
                text-align: center;
                color: #333;
                margin-bottom: 30px;
            }
            .form-group {
                margin-bottom: 20px;
            }
            label {
                display: block;
                margin-bottom: 8px;
                color: #555;
                font-weight: bold;
            }
            input[type="password"] {
                width: 100%;
                padding: 12px;
                border: 2px solid #ddd;
                border-radius: 5px;
                font-size: 14px;
                box-sizing: border-box;
                transition: border-color 0.3s;
            }
            input[type="password"]:focus {
                outline: none;
                border-color: #667eea;
            }
            button {
                width: 100%;
                padding: 12px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                border-radius: 5px;
                font-size: 16px;
                font-weight: bold;
                cursor: pointer;
                transition: transform 0.2s;
            }
            button:hover {
                transform: translateY(-2px);
            }
            button:active {
                transform: translateY(0);
            }
            .error {
                color: #d32f2f;
                text-align: center;
                margin-top: 15px;
                display: none;
            }
            .info {
                background: #e3f2fd;
                padding: 10px;
                border-radius: 5px;
                color: #1565c0;
                font-size: 12px;
                margin-bottom: 20px;
            }
        </style>
    </head>
    <body>
        <div class="login-container">
            <h1>🔐 Proxmox API Docs</h1>
            <div class="info">Enter your API key to access the documentation</div>
            <form id="loginForm">
                <div class="form-group">
                    <label for="apiKey">API Key:</label>
                    <input 
                        type="password" 
                        id="apiKey" 
                        name="apiKey" 
                        placeholder="Enter your API key"
                        required
                        autofocus
                    >
                </div>
                <button type="submit">Access Documentation</button>
                <div class="error" id="error"></div>
            </form>
        </div>

        <script>
            document.getElementById('loginForm').addEventListener('submit', (e) => {
                e.preventDefault();
                const apiKey = document.getElementById('apiKey').value;
                window.location.href = '/docs?key=' + encodeURIComponent(apiKey);
            });
        </script>
    </body>
    </html>
    """

@app.get("/openapi.json", include_in_schema=False)
async def openapi_schema(key: str = None):
    """OpenAPI schema with query parameter authentication"""
    if not key or key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authenticated"
        )
    
    if not hasattr(app, "openapi_schema") or app.openapi_schema is None:
        app.openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            routes=app.routes,
        )
        # Add API Key security scheme
        app.openapi_schema["components"] = {
            "securitySchemes": {
                "ApiKeyAuth": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-API-Key",
                }
            }
        }
        app.openapi_schema["security"] = [{"ApiKeyAuth": []}]
    return app.openapi_schema

app.include_router(proxmox_routes.router)
app.include_router(auth_routes.router)
app.include_router(users.router)
app.include_router(companies.router)
app.include_router(vms.router)
app.include_router(terminals.router)
app.include_router(snapshots_router)