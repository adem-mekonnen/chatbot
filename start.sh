#!/bin/bash

# 1. Initialize and seed the database (Supabase)
# This is fast and won't cause a timeout
echo "Initializing Database..."
python3 -c "import asyncio; from app.database import init_db, seed_demo_data; asyncio.run(init_db()); asyncio.run(seed_demo_data())"

# 2. Start the FastAPI backend in the background
echo "Starting Backend..."
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &

# 3. Start the Streamlit frontend in the foreground
# This opens the port Render is looking for immediately
echo "Starting UI..."
python3 -m streamlit run app-simple.py --server.port $PORT --server.address 0.0.0.0