#!/bin/bash

# --------------------------------------------
# Setup and start the Pi camera stream server
# --------------------------------------------

echo "Installing server dependencies..."
pip install flask

echo ""
echo "Starting the server on http://localhost:5050"
echo "Open that URL in your browser to see the stream."
echo ""

python server/stream_server.py
