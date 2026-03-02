# This script runs on your server (or Mac/PC)
# It receives photos from the Pi and shows them on a webpage

from flask import Flask, Response, render_template, request, jsonify
import time
import cv2
import numpy as np
import threading

app = Flask(__name__)

# Shared variables
latest_photo = None
motion_detected = False
previous_frame = None

# This runs in the background and checks for motion between frames
def detection_loop():
    global motion_detected, previous_frame
    while True:
        frame_data = latest_photo
        if frame_data:
            image_data = np.frombuffer(frame_data, dtype=np.uint8)
            frame = cv2.imdecode(image_data, cv2.IMREAD_COLOR)
            if frame is not None:
                # Convert to greyscale and blur to reduce noise
                grey = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                grey = cv2.GaussianBlur(grey, (21, 21), 0)

                if previous_frame is None:
                    previous_frame = grey
                else:
                    # Compare current frame to previous frame
                    diff = cv2.absdiff(previous_frame, grey)
                    # Anything that changed a lot becomes white, rest is black
                    _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
                    # Count how many pixels changed
                    changed_pixels = cv2.countNonZero(thresh)
                    # If enough pixels changed, something moved
                    motion_detected = changed_pixels > 3000
                    previous_frame = grey
        time.sleep(0.2)

# Start the detection thread
threading.Thread(target=detection_loop, daemon=True).start()

# The Pi sends a photo here
@app.route('/upload', methods=['POST'])
def upload():
    global latest_photo
    latest_photo = request.data
    return "OK", 200

# The webpage asks this to know if motion is detected
@app.route('/status')
def status():
    return jsonify({"motion": motion_detected})

# The browser calls this to get a live stream of photos
@app.route('/stream')
def stream():
    def generate():
        while True:
            if latest_photo:
                # Send the photo in a format browsers understand as a video stream
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + latest_photo + b'\r\n')
            # Wait a little before sending the next frame (30fps max)
            time.sleep(0.03)

    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

# The main webpage
@app.route('/')
def index():
    return render_template('index.html')

# Start the server (threaded=True lets the Pi upload and the browser stream at the same time)
app.run(host='0.0.0.0', port=5050, threaded=True)
