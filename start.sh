#!/bin/bash

# 1. Start the FastAPI backend in the background on port 8000
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &

# 2. Wait 5 seconds for the database connection and API to warm up
sleep 15

# 3. Start the Streamlit frontend in the foreground on Render's $PORT
# This is the process Render monitors to mark the service as 'Live'
python3 -m streamlit run app-simple.py --server.port $PORT --server.address 0.0.0.0