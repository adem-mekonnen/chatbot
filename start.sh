#!/bin/bash

# 1. Index the documents using the Cloud API (Uses very little RAM)
echo "Starting Knowledge-Base Ingestion..."
python3 -m scripts.ingest

# 2. Initialize and seed the database (Supabase)
echo "Initializing Database..."
python3 -c "import asyncio; from app.database import init_db, seed_demo_data; asyncio.run(init_db()); asyncio.run(seed_demo_data())"

# 3. Start the FastAPI backend in the background
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &

# 4. Wait for backend to warm up
sleep 10

# 5. Start the Streamlit frontend
python3 -m streamlit run app-simple.py --server.port $PORT --server.address 0.0.0.0