#!/bin/bash

# TabuLens Integrated Startup Script
set -e

# --- Configuration ---
PROJECT_ROOT=$(pwd)
API_DIR="$PROJECT_ROOT/apps/api"
WEB_DIR="$PROJECT_ROOT/apps/web"
PYTHON_VERSION="3.11" # Adjusted as needed

echo "🚀 Starting TabuLens Integration..."

# 1. Setup Backend (.venv)
echo "📦 Setting up Backend..."
cd "$API_DIR"

# Check if .venv exists and is healthy
RECREATE_VENV=false
if [ ! -d ".venv" ]; then
    RECREATE_VENV=true
else
    # Try to run python from venv. If it fails (bad interpreter, etc), recreate.
    if ! ./.venv/bin/python --version > /dev/null 2>&1; then
        echo "  - Existing .venv is broken. Recreating..."
        rm -rf .venv
        RECREATE_VENV=true
    fi
fi

if [ "$RECREATE_VENV" = true ]; then
    echo "  - Creating virtual environment..."
    python3 -m venv .venv
fi

echo "  - Installing/Updating backend dependencies..."
./.venv/bin/python -m pip install -e . > /dev/null 2>&1 || ./.venv/bin/python -m pip install fastapi uvicorn pandas openpyxl scikit-learn pydantic numpy joblib python-multipart

# 2. Build Frontend
echo "🎨 Building Frontend..."
cd "$WEB_DIR"
if [ ! -d "node_modules" ]; then
    echo "  - Installing frontend dependencies..."
    pnpm install
fi
echo "  - Running pnpm build..."
pnpm build

# 3. Start Integrated Server
echo "⚡️ Starting Integrated Server at http://localhost:8000"
cd "$API_DIR"
# Make sure we are using the venv uvicorn
./.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
