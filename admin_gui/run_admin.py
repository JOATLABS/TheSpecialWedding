#!/usr/bin/env python3
"""
Launcher script for the Wedding Admin GUI

This script provides a simple way to launch the Streamlit-based admin interface.
It checks for required dependencies and environment before starting the app.
"""
import os
import sys
import subprocess
import webbrowser
from pathlib import Path

def check_dependencies():
    """Check if required packages are installed"""
    try:
        import streamlit
        import pandas
        import requests
        return True
    except ImportError as e:
        print(f"Missing dependency: {e}")
        print("Please install required dependencies with: pip install -r requirements.txt")
        return False

def check_environment():
    """Check if environment is properly set up"""
    # Check for .env file
    env_file = Path("../.env")
    if not env_file.exists():
        print("WARNING: .env file not found in parent directory")
        print("Some features may not work correctly")
    
    # Check API access
    try:
        import requests
        response = requests.get("http://localhost:8000/health/")
        if response.status_code == 200:
            print("✅ API is accessible")
        else:
            print("⚠️ API responded with status code", response.status_code)
    except Exception as e:
        print("⚠️ Cannot connect to API:", str(e))

def run_streamlit():
    """Launch the Streamlit app"""
    # Determine the path to the Streamlit app
    app_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "admin_gui.py")
    
    # Build the Streamlit command
    cmd = [
        "streamlit", "run", 
        app_path,
        "--server.port=8501", 
        "--server.address=0.0.0.0"
    ]
    
    # Launch the app
    print("Starting Streamlit app...")
    process = subprocess.Popen(cmd)
    
    # Open browser
    webbrowser.open("http://localhost:8501")
    
    # Wait for the process to complete
    try:
        process.wait()
    except KeyboardInterrupt:
        print("\nShutting down Streamlit app...")
        process.terminate()

if __name__ == "__main__":
    print("Wedding Admin GUI Launcher")
    print("=========================")
    
    # Check dependencies and environment
    if not check_dependencies():
        sys.exit(1)
    
    check_environment()
    
    # Run the app
    run_streamlit()