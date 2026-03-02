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
person_detected = False

# Set up the person detector (built into OpenCV, no extra files needed)
detector = cv2.HOGDescriptor()
detector.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

# This runs in the background and checks the latest photo for people
def detection_loop():
    global person_detected
    while True:
        frame_data = latest_photo
        if frame_data:
            image_data = np.frombuffer(frame_data, dtype=np.uint8)
            frame = cv2.imdecode(image_data, cv2.IMREAD_COLOR)
            if frame is not None:
                # Resize small for speed
                small = cv2.resize(frame, (320, 240))
                people, _ = detector.detectMultiScale(small, winStride=(8, 8), scale=1.05)
                person_detected = len(people) > 0
        time.sleep(0.5)  # check twice per second

# Start the detection thread
threading.Thread(target=detection_loop, daemon=True).start()

# The Pi sends a photo here
@app.route('/upload', methods=['POST'])
def upload():
    global latest_photo
    latest_photo = request.data
    return "OK", 200

# The webpage asks this to know if a person is detected
@app.route('/status')
def status():
    return jsonify({"person": person_detected})

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
