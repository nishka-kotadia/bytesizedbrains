"""
Uvicorn entry point for the Multi-Agent Research Intelligence System.

Usage:
    uvicorn main:app --reload --host 0.0.0.0 --port 8000

Or run directly:
    python main.py
"""

import uvicorn
from api.server import app  # noqa: F401  — re-exported so uvicorn can find it

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
