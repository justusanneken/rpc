# This script runs on the Raspberry Pi
# It captures frames from the camera and sends them to the server

import cv2        # used to access the camera
import requests   # used to send data over the internet
import time       # used to wait a bit if something goes wrong

# Change this to the IP address of your server
SERVER_URL = "http://10.0.0.8:5050/upload"

# Open the camera (0 = first camera connected)
camera = cv2.VideoCapture(0)

print("Starting stream... press Ctrl+C to stop")

while True:
    # Grab a single photo from the camera
    success, frame = camera.read()

    if not success:
        print("Couldn't read from camera, trying again...")
        time.sleep(1)
        continue

    # Turn the photo into a JPEG so it's small enough to send fast
    success, jpeg = cv2.imencode('.jpg', frame)

    # Send the photo to the server
    try:
        requests.post(SERVER_URL, data=jpeg.tobytes(), headers={"Content-Type": "image/jpeg"}, timeout=2)
    except:
        print("Couldn't reach server, trying again...")
        time.sleep(1)
