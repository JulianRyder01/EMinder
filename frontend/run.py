# frontend/run.py
# ========================== START: MODIFICATION (Code Addition) ==========================
# DESIGNER'S NOTE:
# This is the new entry point script for the frontend application.
# Its primary role is to correctly set up the Python path so that relative imports
# within the 'frontend/app' package work flawlessly, regardless of how the script is executed.
# This approach is robust and avoids common 'ModuleNotFoundError' issues in complex projects.

import sys
import os

def main():
    """
    Sets up the Python path and runs the frontend application.
    This runner script ensures that relative imports within the 'frontend' package work correctly.
    """
    # Get the absolute path of the project root directory (the 'frontend' folder itself)
    project_root = os.path.dirname(os.path.abspath(__file__))
    
    # Add the project root to the Python path.
    # This allows Python to find the 'app' package.
    sys.path.insert(0, project_root)

    print("Initializing frontend application...")

    # Now that the path is set up, we can import and run the main function from the package.
    from app.main import main as run_frontend_app
    
    # Execute the main application logic
    run_frontend_app()

if __name__ == "__main__":
    main()