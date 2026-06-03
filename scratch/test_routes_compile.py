import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from app import app
    print("Application initialized successfully! All routes and models are compiled without syntax or import errors.")
except Exception as e:
    print(f"Failed to initialize application: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
