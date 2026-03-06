PI KAMERA STREAM - TECHNISCHE DOKUMENTATION
============================================

SCHNELLSTART
------------
Server starten:  bash start.sh
Pi starten:      python3 pi_client/stream_client.py
Im Browser:      http://10.0.0.8:5050


SYSTEMARCHITEKTUR
-----------------
Das System besteht aus zwei Prozessen, die über ein lokales IP-Netzwerk
kommunizieren:

  [Raspberry Pi]  ──HTTP POST /upload──>  [Flask-Server]  ──HTTP GET /stream──>  [Browser]
  (Produzent)          JPEG-Rohdaten      (Verteiler +        MJPEG-Multipart
                                          Detektor)           Response

Der Pi agiert als reiner Produzent: Er nimmt Frames auf, kodiert sie als JPEG
und schickt sie per HTTP POST an den Server. Der Server hält immer nur das
jeweils neueste Frame im RAM (als Python-bytes-Objekt in der globalen Variable
`latest_photo`). Der Browser ruft den Stream dann per HTTP GET ab.

Es gibt keinen persistenten Netzwerk-Socket oder eine dauerhafte Verbindung
zwischen Pi und Server – jeder Frame ist eine eigenständige HTTP-Transaktion.


NETZWERKTOPOLOGIE
-----------------
  Gerät              IP            Port   Protokoll
  -------------------------------------------------------
  Server (Mac/PC)    10.0.0.8      5050   HTTP (Flask)
  Raspberry Pi       (DHCP)        –      HTTP-Client
  Browser            (lokal)       –      HTTP-Client

Der Server bindet an 0.0.0.0:5050, hört also auf allen Netzwerkinterfaces.
Der Pi hat die Server-IP fest im Quellcode hinterlegt (SERVER_URLS-Liste).


ABHÄNGIGKEITEN
--------------
Raspberry Pi (APT-Pakete):
  python3-picamera2   – libcamera-basierter Kamera-Treiber für Pi-CSI-Kameras
  python3-opencv      – OpenCV für Farbraumkonvertierung und JPEG-Kodierung
  python3-requests    – HTTP-Clientbibliothek für POST-Anfragen

Server (pip-Pakete, via start.sh installiert):
  flask               – WSGI-Webframework, stellt alle HTTP-Endpunkte bereit
  opencv-python       – OpenCV für Bewegungserkennung (Bildverarbeitung)
  numpy               – wird von OpenCV intern benötigt; np.frombuffer dekodiert
                        die eingehenden JPEG-Bytes in ein NumPy-Array


DATEI: pi_client/stream_client.py
----------------------------------
Läuft dauerhaft auf dem Raspberry Pi in einer Endlosschleife.

1. KAMERA-INITIALISIERUNG
   Picamera2 wird mit der Standard-Preview-Konfiguration geöffnet:
     camera = Picamera2()
     camera.configure(camera.create_preview_configuration())
     camera.start()
   create_preview_configuration() liefert einen YUV420- oder XBGR8888-Stream
   (je nach Pi-Modell und libcamera-Version) in einer niedrigen Auflösung
   (~640×480), was die CPU-Last und Netzwerkbandbreite gering hält.

2. FARBRAUMKORREKTUR (NoIR-Kamera)
   Die NoIR-Kamera hat keinen Infrarot-Sperrfilter. picamera2 liefert das Frame
   im BGRA-Format (4 Kanäle: Blue, Green, Red, Alpha/IR).

   Schritt 1 – Alpha-Kanal entfernen:
     frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
   Ohne diesen Schritt würde cv2.imencode() den Frame falsch interpretieren.

   Schritt 2 – Rot- und Blaukanal tauschen:
     b, g, r = cv2.split(frame)
     frame = cv2.merge([r, g, b])
   OpenCV arbeitet intern mit BGR-Reihenfolge. Da die NoIR-Kamera durch das
   fehlende IR-Filter einen starken Rotstich produziert, werden R und B manuell
   vertauscht, um einen natürlicheren Farbeindruck zu erzeugen.

3. ROTATION
     frame = cv2.rotate(frame, cv2.ROTATE_180)
   Die Kamera ist physisch umgekehrt montiert, daher wird jeder Frame um 180°
   gedreht, bevor er gesendet wird.

4. JPEG-KODIERUNG
     success, jpeg = cv2.imencode('.jpg', frame)
   cv2.imencode komprimiert das unkomprimierte BGR-Array (mehrere MB) in ein
   JPEG-Byte-Array (typisch 15–60 KB je nach Inhalt). Die Kompressionsrate
   hängt von der Bildkomplexität ab. Bei Misserfolg (success == False) wird der
   Frame übersprungen und 1 Sekunde gewartet.

5. HTTP POST AN DEN SERVER
     requests.post(url, data=jpeg.tobytes(),
                   headers={"Content-Type": "image/jpeg"}, timeout=2)
   Das JPEG wird als Raw-Body (kein Multipart-Formular) per POST gesendet.
   Der Content-Type-Header ist informell – der Server liest request.data
   ungefiltert. timeout=2 verhindert, dass ein nicht erreichbarer Server den
   Pi blockiert. Fehler werden per except gefangen und geloggt, der Loop
   läuft weiter ohne Verzögerung (kein explizites sleep zwischen Frames –
   die Framerate ist ausschließlich durch CPU- und Netzwerklatenz begrenzt).

   SERVER_URLS ist eine Liste, sodass bei Bedarf mehrere Server gleichzeitig
   beliefert werden können.


DATEI: server/stream_server.py
--------------------------------
Läuft auf dem Server (Mac oder Windows). Startet einen Flask-WSGI-Server mit
`threaded=True`, sodass jede eingehende HTTP-Verbindung in einem eigenen Thread
bearbeitet wird.

GLOBALER ZUSTAND (im RAM, nicht thread-sicher gesperrt):
  latest_photo     bytes | None   – Rohbytes des zuletzt empfangenen JPEG
  motion_detected  bool           – True wenn Bewegung erkannt wurde
  previous_frame   np.ndarray     – Letztes Graustufen-Frame für den Diff

  Hinweis: Zugriffe auf diese globalen Variablen sind nicht durch Locks
  geschützt. Bei hoher Last kann es zu Race Conditions kommen (ein Thread
  liest latest_photo während ein anderer schreibt). Im Praxisbetrieb im
  Heimnetz ist dies unkritisch, da Python's GIL einzelne Byte-Zuweisungen
  atomar hält.

HTTP-ENDPUNKTE:

  POST /upload
    Empfängt den Frame vom Pi. request.data enthält den rohen JPEG-Body.
    Der Frame wird in latest_photo gespeichert (alte Daten werden sofort
    überschrieben – es gibt keinen Puffer/Queue). Antwort: "OK" mit HTTP 200.

  GET /stream
    Liefert einen MJPEG-Stream (Motion JPEG) mit dem MIME-Typ
    multipart/x-mixed-replace; boundary=frame.
    Das ist ein HTTP/1.1 Chunked-Response, bei dem der Server die Verbindung
    nie schließt und kontinuierlich neue JPEG-Frames sendet:

      --frame
      Content-Type: image/jpeg
      <JPEG-Bytes>
      --frame
      Content-Type: image/jpeg
      <JPEG-Bytes>
      ...

    Der Browser interpretiert dies nativ als Video-Stream in einem <img>-Tag.
    Nach jedem Frame wartet der Generator 0.03 Sekunden, was einer theoretischen
    Obergrenze von ~33 FPS entspricht. Die tatsächliche Rate ist durch die
    Upload-Frequenz des Pi begrenzt.

  GET /status
    Gibt {"motion": true|false} als JSON zurück. Wird vom Browser-Frontend
    per Polling aufgerufen.

  GET /
    Liefert index.html via Jinja2-Template-Rendering (render_template).

BEWEGUNGSERKENNUNGS-THREAD (detection_loop):
  Läuft als Daemon-Thread parallel zu Flask. Iterationsrate: 5 Hz (sleep 0.2s).
  Verarbeitet immer das aktuell in latest_photo gespeicherte Frame.

  Algorithmus (Frame-Differenz-Methode):

  1. JPEG-Bytes deserialisieren:
       image_data = np.frombuffer(frame_data, dtype=np.uint8)
       frame = cv2.imdecode(image_data, cv2.IMREAD_COLOR)
     np.frombuffer interpretiert die Bytes als 1D-uint8-Array; cv2.imdecode
     dekodiert das JPEG zurück in ein BGR-Array.

  2. Graustufen-Konvertierung:
       grey = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
     Reduziert 3 Kanäle auf 1. Bewegungserkennung auf Farbdaten ist anfälliger
     für Beleuchtungsänderungen; Graustufen sind robuster.

  3. Gaussian Blur (Kernel 21×21, Sigma 0):
       grey = cv2.GaussianBlur(grey, (21, 21), 0)
     Glättet hochfrequentes Rauschen (Kamerarauschen, JPEG-Artefakte), das
     sonst zu Falschpositiven führen würde. Sigma 0 lässt OpenCV den Sigma-Wert
     automatisch aus der Kernelgröße berechnen (sigma ≈ 0.3 * ((21-1)/2 - 1)
     + 0.8 ≈ 3.4).

  4. Frame-Differenz:
       diff = cv2.absdiff(previous_frame, grey)
     Berechnet den pixelweisen absoluten Differenzbetrag zwischen dem aktuellen
     und dem vorherigen Frame. Bereiche ohne Bewegung → diff ≈ 0.
     Bewegte Objekte → diff > 0.

  5. Schwellenwert-Binarisierung:
       _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
     Pixel mit diff > 25 werden auf 255 (weiß) gesetzt, alle anderen auf 0
     (schwarz). Der Schwellenwert 25 filtert kleine Helligkeitsschwankungen
     durch wechselndes Umgebungslicht heraus.

  6. Pixel zählen und Entscheidung:
       changed_pixels = cv2.countNonZero(thresh)
       motion_detected = changed_pixels > 3000
     Wenn mehr als 3000 Pixel als "verändert" markiert sind, wird Bewegung
     gemeldet. Bei ~640×480 = 307.200 Pixel entspricht das ca. 1% der
     Bildfläche als Mindestschwelle.


DATEI: server/templates/index.html
------------------------------------
Minimales Browser-Frontend ohne externe Abhängigkeiten.

MJPEG-ANZEIGE:
  <img src="/stream" />
  Der Browser öffnet eine persistente HTTP-Verbindung zu /stream. Da der
  MIME-Typ multipart/x-mixed-replace ist, ersetzt der Browser das Bild
  automatisch durch jeden neu eintreffenden JPEG-Frame. Es wird kein
  JavaScript für den Videostream benötigt.

BEWEGUNGSANZEIGE:
  Ein <div id="alert"> ist standardmäßig per CSS auf visibility: hidden
  gesetzt (display: inline-block bleibt erhalten, um Layout-Shifts zu
  vermeiden). Ein setInterval-Timer ruft alle 1000 ms per Fetch-API den
  /status-Endpunkt ab:

    fetch('/status')
      .then(r => r.json())
      .then(data => {
        document.getElementById('alert').style.visibility =
          data.motion ? 'visible' : 'hidden';
      });

  Die Verzögerung zwischen tatsächlicher Bewegung und Alarmanzeige beträgt
  maximal ~1.2 Sekunden (0.2s Detektionsschleife + 1.0s Poll-Intervall).


DATEI: start.sh
---------------
Bash-Skript für den Server-Rechner.

  pip install flask opencv-python
  python server/stream_server.py

Installiert die pip-Dependencies und startet den Server direkt. Es wird keine
virtuelle Umgebung erstellt – Pakete werden in die aktive Python-Umgebung
(oder ggf. das System-Python) installiert. Für eine sauberere Installation
kann vorher manuell `python -m venv .venv && source .venv/bin/activate`
ausgeführt werden.


AUSFÜHREN
---------

1. SERVER (Mac/Windows):
   bash start.sh
   → Browser: http://localhost:5050

2. RASPBERRY PI:
   git clone https://github.com/justusanneken/rpc.git
   cd rpc
   sudo apt install python3-picamera2 python3-opencv python3-requests -y
   python3 pi_client/stream_client.py

   Der Pi sendet Frames an die in SERVER_URLS konfigurierte Adresse (10.0.0.8:5050).
   Soll ein anderer Server genutzt werden, muss SERVER_URLS in stream_client.py
   angepasst werden.


PERFORMANCE-KENNDATEN (Richtwerte)
-----------------------------------
  Frame-Obergrenze Stream:      ~33 FPS  (0.03s sleep in generate())
  Detektions-Rate:              5 Hz     (0.2s sleep in detection_loop())
  Max. Alarmverzögerung:        ~1.2 s   (Detektion + Poll-Intervall)
  Typische JPEG-Größe:          15–60 KB (abhängig von Bildkomplexität)
  Bewegungsschwelle:            3000 Px  (~1% bei 640×480)
  Differenz-Binarisierungswert: 25       (von 0–255 Graustufen)
  Gaussian-Blur-Kernel:         21×21    (Sigma ≈ 3.4)
