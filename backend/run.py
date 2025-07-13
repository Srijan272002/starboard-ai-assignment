import uvicorn
import os
import sys
from pathlib import Path

def main():
    """
    Run the FastAPI application using uvicorn
    """
    # Get the project root directory (one level up from current file)
    current_dir = Path(__file__).parent
    project_root = current_dir.parent
    
    # Add the project root to Python path
    sys.path.append(str(project_root))
    
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[str(current_dir)]
    )

if __name__ == "__main__":
    main() 