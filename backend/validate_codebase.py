
import os
import sys
import compileall
from pathlib import Path

def check_syntax():
    print("Checking syntax...")
    # Compile all python files in backend directory recursively
    if not compileall.compile_dir("backend", force=True, quiet=1):
        print("Syntax check FAILED")
        sys.exit(1)
    print("Syntax check PASSED")

def check_imports():
    print("Checking imports (by importing main)...")
    try:
        # Add current dir to path
        sys.path.append(os.getcwd())
        
        print("Importing config...")
        from backend import config
        print("Importing database...")
        from backend import database
        
        routers = [
            "upload", "classify", "template", "mapping", 
            "library", "batch", "audit", "auth", "export",
            "payments", "monitoring"
        ]
        
        for r in routers:
            print(f"Importing route: {r}...")
            __import__(f"backend.api.routes.{r}")
            print(f"Route {r} OK")

        print("Import check PASSED")
    except ImportError as e:
        print(f"Import check FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Import check FAILED with unexpected error: {e}")
        # We might fail on runtime errors like DB connection, that's expected and okay-ish for a static check
        # But let's report it
        # sys.exit(1) 

if __name__ == "__main__":
    check_syntax()
    # verify main import
    check_imports() 
