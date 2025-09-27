#!/bin/bash

# Startup script for Ecommerce Insights Server

echo "🚀 Starting Ecommerce Insights Server..."

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install/update dependencies
echo "📦 Installing dependencies..."
pip install -q -r requirements.txt

# Create necessary directories
mkdir -p logs data/vectordb

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found. Creating from example..."
    cp .env.example .env
    echo "📝 Please edit .env with your configuration"
fi

# Check if Ollama is running
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "⚠️  Warning: Ollama doesn't seem to be running"
    echo "   Start it with: ollama serve"
fi

# Check if MongoDB is accessible
python3 -c "
import os
from pymongo import MongoClient
from dotenv import load_dotenv
load_dotenv()
url = os.getenv('MONGODB_URL', 'mongodb://localhost:27017')
try:
    client = MongoClient(url, serverSelectionTimeoutMS=2000)
    client.server_info()
    print('✅ MongoDB connected')
except:
    print('⚠️  Warning: Cannot connect to MongoDB')
    print('   Check your MONGODB_URL in .env')
"

# Start the server
echo "🌐 Starting server on http://localhost:8000"
echo "📚 API docs available at http://localhost:8000/docs"
echo ""
uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload