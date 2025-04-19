#!/usr/bin/env python3
"""
Installation script for OpenHAB MCP Server.
This script checks requirements, installs dependencies, and sets up the environment.
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

MIN_PYTHON_VERSION = (3, 7)

def check_python_version():
    """Check if Python version meets requirements."""
    if sys.version_info < MIN_PYTHON_VERSION:
        print(f"Error: Python {MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]} or higher is required.")
        sys.exit(1)
    print(f"✓ Python version {sys.version_info.major}.{sys.version_info.minor} meets requirements.")

def check_uv_installed():
    """Check if uv is installed, install it if not."""
    uv_path = shutil.which("uv")
    if uv_path:
        print(f"✓ uv is installed at {uv_path}")
        return True
    
    print("uv is not installed. Installing...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "uv"], check=True)
        print("✓ uv installed successfully.")
        return True
    except subprocess.CalledProcessError:
        print("Error: Failed to install uv. Please install it manually with 'pip install uv'.")
        sys.exit(1)

def create_virtual_environment():
    """Create a virtual environment using uv."""
    if os.path.exists(".venv"):
        print("✓ Virtual environment already exists.")
        return
    
    print("Creating virtual environment...")
    try:
        subprocess.run(["uv", "venv"], check=True)
        print("✓ Virtual environment created successfully.")
    except subprocess.CalledProcessError:
        print("Error: Failed to create virtual environment.")
        sys.exit(1)

def install_dependencies():
    """Install dependencies using uv."""
    print("Installing dependencies...")
    try:
        subprocess.run(["uv", "pip", "install", "-r", "requirements.txt"], check=True)
        print("✓ Dependencies installed successfully.")
    except subprocess.CalledProcessError:
        print("Error: Failed to install dependencies.")
        sys.exit(1)

def setup_env_file():
    """Create .env file from .env.example if it doesn't exist."""
    if os.path.exists(".env"):
        print("✓ .env file already exists.")
        return
    
    if os.path.exists(".env.example"):
        print("Creating .env file from .env.example...")
        with open(".env.example", "r") as example_file:
            example_content = example_file.read()
        
        with open(".env", "w") as env_file:
            env_file.write(example_content)
        
        print("✓ .env file created. Please update it with your OpenHAB connection details.")
    else:
        print("Warning: .env.example file not found. Please create a .env file manually.")

def print_next_steps():
    """Print instructions for next steps."""
    print("\n=== Installation Complete ===")
    print("\nNext steps:")
    print("1. Update the .env file with your OpenHAB connection details")
    print("2. Run the server with: uv run openhab_mcp_server.py")
    print("   Or activate the virtual environment and run: python openhab_mcp_server.py")
    print("\nFor development:")
    print("- Start a local OpenHAB instance with: docker-compose up")
    print("- See DEVELOPER.md for more information")

def main():
    """Main installation function."""
    print("=== OpenHAB MCP Server Installation ===\n")
    
    check_python_version()
    check_uv_installed()
    create_virtual_environment()
    install_dependencies()
    setup_env_file()
    print_next_steps()

if __name__ == "__main__":
    main()
