import cv2
import paho.mqtt.client as mqtt
import json
import threading
import time
import queue
import imutils # If you want to use imutils.resize

# --- Configuration ---
JETSON_RTSP_URL = "rtsp://192.168.2.100:8554/test" # IMPORTANT: Replace with your Jetson's actual IP
MQTT_BROKER_HOST = "127.0.0.1" # MQTT broker is now LOCAL to the edge server
MQTT_PORT = 1883
MQTT_TOPIC = "jetson/face_recognition/results"

# Global variable to store the latest detection results
latest_detections = []
detections_lock = threading.Lock()

# Queue for frames from RTSP stream
frame_queue = queue.Queue(maxsize=5)

# --- MQTT Callbacks ---
def on_connect(client, userdata, flags, rc):
    print(f"MQTT Client Connected with result code {rc}")
    client.subscribe(MQTT_TOPIC)
    print(f"Subscribed to topic: {MQTT_TOPIC}")

def on_message(client, userdata, msg):
    global latest_detections
    try:
        # Decode the JSON payload
        results = json.loads(msg.payload.decode())
        results_1 = {'timestamp': '2025-07-07T19:56:14.855707',
                   'frame_dimensions': {'width': 1280, 'height': 720},
                   'detected_faces': [{
                        "box": [100, 50, 150, 200],  # x, y, width, height
                        "name": "John Doe",
                        "confidence": 95,
                        "person_id": "some_id_123"
                    }],
                   'flask_processing_fps': 0.9458355583137295,
                   'avg_inference_time_ms': 1086.901370684306}
        # Extract detected faces
        detected_faces = results.get("detected_faces", [])
        print(results)
        print(detected_faces)
        with detections_lock:
            latest_detections = detected_faces
        print(f"Received {len(detected_faces)} detections via MQTT.")
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from MQTT: {e}")
    except Exception as e:
        print(f"Error processing MQTT message: {e}")

# --- RTSP Stream Reader Thread ---
def rtsp_reader_loop():
    cap = None
    while True:
        if cap is None or not cap.isOpened():
            print(f"Attempting to open RTSP stream: {JETSON_RTSP_URL}")
            cap = cv2.VideoCapture(JETSON_RTSP_URL)
            if not cap.isOpened():
                print("Failed to open RTSP stream. Retrying in 5 seconds...")
                time.sleep(5)
                continue
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1) # Reduce buffer for lower latency
            print("RTSP stream opened successfully.")

        ret, frame = cap.read()
        if ret:
            try:
                # Put frame into queue, dropping oldest if full
                frame_queue.put_nowait(frame)
            except queue.Full:
                frame_queue.get_nowait() # Discard oldest
                frame_queue.put_nowait(frame)
        else:
            print("Failed to read frame from RTSP stream. Re-initializing capture...")
            cap.release()
            cap = None # Force re-initialization

        time.sleep(0.01) # Small sleep to prevent busy-waiting

# --- Main Display Logic ---
if __name__ == "__main__":
    # Start MQTT client
    mqtt_client = mqtt.Client()
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.connect(MQTT_BROKER_HOST, MQTT_PORT, 60)
    mqtt_client.loop_start() # Start MQTT loop in background

    # Start RTSP reader thread
    reader_thread = threading.Thread(target=rtsp_reader_loop, daemon=True)
    reader_thread.start()

    print("Starting display loop. Press 'q' to quit.")

    while True:
        try:
            # Get the latest frame from the queue (non-blocking, or with a short timeout)
            frame = frame_queue.get(timeout=0.1) # Get with timeout to allow loop to check for 'q'

            if frame is None:
                continue

            # Overlay detections
            # You might need to adjust scaling if the display resolution is different from the Jetson's stream
            # Assuming original stream is 1280x720 and you want to display at 1200 width
            display_width = 1200
            display_height = int(frame.shape[0] * (display_width / frame.shape[1]))
            frame_display = imutils.resize(frame, width=display_width)

            # Calculate scaling factors for bounding boxes
            scale_x = display_width / frame.shape[1]
            scale_y = display_height / frame.shape[0]

            with detections_lock:
                current_detections = list(latest_detections) # Get a copy

            for detection in current_detections:
                # Bounding box coordinates from MQTT are [x, y, w, h]
                x_orig, y_orig, w_orig, h_orig = detection["box"]
                name = detection["name"]
                confidence = detection["confidence"]
                print(name)

                # Scale bounding box coordinates to the display frame size
                x = int(x_orig * scale_x)
                y = int(y_orig * scale_y)
                w = int(w_orig * scale_x)
                h = int(h_orig * scale_y)

                color = (0, 255, 0) if name != "Unknown" else (0, 0, 255)
                cv2.rectangle(frame_display, (x, y), (x + w, y + h), color, 2)

                label = f"{name}"
                if confidence > 0:
                    label += f" ({confidence:.0f}%)"

                cv2.putText(frame_display, label, (x, y+h+20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

            # Display the frame
            cv2.imshow('Processed RTSP Stream (Edge Server)', frame_display)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break

        except queue.Empty:
            # No frame available, just continue loop
            pass
        except Exception as e:
            print(f"Error in display loop: {e}")
            time.sleep(0.1)

    cv2.destroyAllWindows()
    mqtt_client.loop_stop()
    mqtt_client.disconnect()
    print("Application shut down.")