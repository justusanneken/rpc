# This script runs on your server (or Mac/PC)
# It receives photos from the Pi and shows them on a webpage

from flask import Flask, Response, render_template, request
import time

app = Flask(__name__)

# This variable holds the latest photo from the Pi
latest_photo = None

# The Pi sends a photo here
@app.route('/upload', methods=['POST'])
def upload():
    global latest_photo
    latest_photo = request.data   # save the photo
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
