from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

# Import routers
from api.proxy import router as proxy_router

app = FastAPI(
    title="StealthWriter Proxy Server",
    description="A reverse proxy for sharing authenticated sessions",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(proxy_router)

@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint with status and instructions"""
    cookie_status = load_manual_cookies()
    status_text = 'Active' if cookie_status.get("exists") and not cookie_status.get("expired") else 'Expired' if cookie_status.get("exists") else 'Not Found'
    error_text = cookie_status.get("error", "")
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>StealthWriter.ai Proxy Server</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; background: #f8fafc; }}
            .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
            .status {{ padding: 20px; border-radius: 8px; margin: 15px 0; }}
            .success {{ background: #d4edda; border-left: 5px solid #28a745; }}
            .warning {{ background: #fff3cd; border-left: 5px solid #ffc107; }}
            .error {{ background: #f8d7da; border-left: 5px solid #dc3545; }}
            .endpoint {{ background: #f8f9fa; padding: 12px; margin: 8px 0; border-radius: 6px; font-family: 'Monaco', monospace; border-left: 3px solid #007bff; }}
            h1 {{ color: #2c3e50; margin-bottom: 10px; }}
            h2 {{ color: #34495e; margin-top: 30px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🛡️ StealthWriter.ai Proxy Server</h1>
            <p>Secure proxy server with manual cookie authentication</p>
            
            <h2>📊 Current Status</h2>
            <div class="status {'success' if status_text == 'Active' else 'warning' if status_text == 'Expired' else 'error'}">
                {'✅' if status_text == 'Active' else '⚠️' if status_text == 'Expired' else '❌'} 
                <strong>Authentication Cookies:</strong> {status_text}
                {f"<br><small>❌ Error: {error_text}</small>" if error_text else ""}
            </div>
            
            <h2>🔗 API Endpoints</h2>
            <div class="endpoint">GET /dashboard - Access StealthWriter dashboard</div>
            <div class="endpoint">GET /session-status - Check session and cookie status</div>
            <div class="endpoint">POST /refresh-session - Force refresh session</div>
            <div class="endpoint">GET /manual-login - Trigger manual login flow</div>
            <div class="endpoint">POST /update-cookies - Update cookies via API</div>
            
            <h2>🎯 Usage Instructions</h2>
            <ol>
                <li><strong>Ensure valid cookies:</strong> Check that manual_cookies.json contains fresh authentication cookies</li>
                <li><strong>Access dashboard:</strong> Navigate to <code>http://your-server:8000/dashboard</code></li>
                <li><strong>Monitor status:</strong> Use <code>/session-status</code> to monitor authentication health</li>
            </ol>
            
            <p><small>Server running on port 8000 • Simplified HTTPX proxy</small></p>
        </div>
    </body>
    </html>
    """
    return html_content

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "StealthWriter Proxy",
        "version": "1.0.0"
    }

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc),
            "path": str(request.url)
        }
    )

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=False
    )
