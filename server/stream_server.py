# This script runs on your server (or Mac/PC)
# It receives photos from the Pi and shows them on a webpage

from flask import Flask, Response, render_template, request
import time
import cv2
import numpy as np

app = Flask(__name__)

# This variable holds the latest photo from the Pi
latest_photo = None

# Set up the person detector (built into OpenCV, no extra files needed)
detector = cv2.HOGDescriptor()
detector.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

# The Pi sends a photo here
@app.route('/upload', methods=['POST'])
def upload():
    global latest_photo

    # Decode the raw JPEG into an image OpenCV can work with
    image_data = np.frombuffer(request.data, dtype=np.uint8)
    frame = cv2.imdecode(image_data, cv2.IMREAD_COLOR)

    if frame is not None:
        # Run person detection (scale down for speed)
        people, _ = detector.detectMultiScale(frame, winStride=(8, 8), scale=1.05)

        # If anyone is detected, draw a thick red border around the whole frame
        if len(people) > 0:
            h, w = frame.shape[:2]
            cv2.rectangle(frame, (0, 0), (w, h), (0, 0, 255), 20)

        # Re-encode back to JPEG and save
        _, jpeg = cv2.imencode('.jpg', frame)
        latest_photo = jpeg.tobytes()
    else:
        latest_photo = request.data

    return "OK", 200

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
