#!/usr/bin/env python3
"""
AudioEnhance Pro - Startup Script
"""

import uvicorn
import os
from pathlib import Path

def create_directories():
    """Create necessary directories if they don't exist"""
    directories = ['uploads', 'processed', 'temp', 'models']
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)

def main():
    """Main startup function"""
    print("🎵 Starting AudioEnhance Pro...")
    
    # Create necessary directories
    create_directories()
    
    # Set default host and port
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    
    print(f"🚀 Server starting on http://{host}:{port}")
    print("📚 API Documentation: http://localhost:8000/api/docs")
    print("🎨 Web Interface: http://localhost:8000")
    
    # Start the server
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )

if __name__ == "__main__":
    main()