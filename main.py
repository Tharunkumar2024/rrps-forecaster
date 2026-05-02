"""Root entry point for the RRPS Forecaster API.

Usage:
    python main.py [--host 0.0.0.0] [--port 8000] [--reload]
"""

import sys
from pathlib import Path

# Ensure the root directory is in the Python path
root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

if __name__ == "__main__":
    import uvicorn
    from app.core.config import get_settings

    settings = get_settings()

    print(f"Starting server via root main.py...")
    print(f"Config -> host: {settings.host}, port: {settings.port}, reload: {settings.reload}")
    
    uvicorn.run(
        "app.main:app", 
        host=settings.host, 
        port=settings.port, 
        reload=settings.reload,
    )
