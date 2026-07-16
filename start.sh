#!/bin/bash

# Start the FastAPI backend in the background
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &

# Start the Streamlit frontend in the foreground
# Render automatically sets the $PORT variable (usually 10000)
python3 -m streamlit run app-simple.py --server.port $PORT --server.address 0.0.0.0