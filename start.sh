#!/bin/bash

# Exit on error
set -e

echo "🚀 Setting up Mood Your Weather Backend..."

# 1. Check Python version
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install it first."
    exit 1
fi

# 2. Setup Virtual Environment
if [ -d "venv" ] && [ ! -f "venv/bin/activate" ]; then
    echo "⚠️  Virtual environment appears corrupt. Recreating..."
    rm -rf venv
fi

if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Double check creation
if [ ! -f "venv/bin/activate" ]; then
     echo "❌ Failed to create virtual environment (venv/bin/activate missing)."
     echo "please try running: python3 -m venv venv manually."
     exit 1
fi

# Activate venv
source venv/bin/activate

# 3. Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# 4. Install Dependencies
echo "⬇️  Installing dependencies..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    echo "⚠️  requirements.txt not found!"
fi

# Ensure critical packages are installed
pip install "uvicorn[standard]" fastapi

# 5. Check for Credentials
KEY_FILE="mood-your-weather-firebase-adminsdk-fbsvc-da13f7ee3e.json"
if [ ! -f "$KEY_FILE" ]; then
    echo " "
    echo "⚠️  CRITICAL WARNING: Firebase Key File Missing!"
    echo "---------------------------------------------------"
    echo "The application expects to find '$KEY_FILE' in this directory."
    echo "Without it, the server will crash on startup."
    echo "Please download it from Firebase Console or ask your team lead."
    echo "---------------------------------------------------"
    echo " "
    # We don't exit here to allow user to see the error from the app itself if they want, 
    # or arguably we SHOULD exit. The previous run crashed, so maybe we should pause.
    read -p "Press Enter to try running anyway (or Ctrl+C to abort)..."
fi

# 6. Run Application
echo "🔥 Starting Uvicorn Server..."
echo "Output will be shown below. Press Ctrl+C to stop."
echo "---------------------------------------------------"

# Run with python -m to ensure we use the venv's uvicorn
python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
