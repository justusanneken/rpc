#!/bin/bash

# --------------------------------------------
# Setup and start the Pi camera stream CLIENT
# Run this on the Raspberry Pi (not the server)
# --------------------------------------------

echo "Installing Pi dependencies..."
pip install opencv-python requests

echo ""
read -p "Enter the server IP address: " SERVER_IP

# Replace the placeholder in the client script with the entered IP
sed -i "s|http://.*:5050/upload|http://$SERVER_IP:5050/upload|" pi_client/stream_client.py

echo ""
echo "Server IP set to $SERVER_IP"
echo "Starting the camera stream..."
echo ""

python pi_client/stream_client.py
