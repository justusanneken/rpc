# This script runs on the Raspberry Pi
# It captures frames from the camera and sends them to the server

from picamera2 import Picamera2  # built-in Pi camera library
import requests                  # used to send data over the internet
import time                      # used to wait if something goes wrong
import cv2                       # used to convert the frame to JPEG

# Change this to the IP address of your server
SERVER_URL = "http://10.0.0.8:5050/upload"

# Set up the camera
camera = Picamera2()
camera.configure(camera.create_preview_configuration())
camera.start()

print("Starting stream... press Ctrl+C to stop")

while True:
    # Grab a single photo from the camera
    frame = camera.capture_array()

    # picamera2 gives us a 4-channel image, drop the extra channel
    frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

    # NoIR fix: swap red and blue channels to correct the pink/IR tint
    b, g, r = cv2.split(frame)
    frame = cv2.merge([r, g, b])

    # Turn the photo into a JPEG so it's small enough to send fast
    success, jpeg = cv2.imencode('.jpg', frame)

    if not success:
        print("Couldn't encode frame, trying again...")
        time.sleep(1)
        continue

    # Send the photo to the server
    try:
        requests.post(SERVER_URL, data=jpeg.tobytes(), headers={"Content-Type": "image/jpeg"}, timeout=2)
    except:
        print("Couldn't reach server, trying again...")
        time.sleep(1)
