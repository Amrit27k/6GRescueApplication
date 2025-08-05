import cv2
import paho.mqtt.client as mqtt
import json
import threading
import time
import queue
import imutils
import logging

logger = logging.getLogger(__name__)

class RTSPMQTTStreamClient:
    def __init__(self):
        # Configuration - same as your original script
        self.JETSON_RTSP_URL = "rtsp://192.168.2.100:8554/test"
        self.MQTT_BROKER_HOST = "127.0.0.1"
        self.MQTT_PORT = 1883
        self.MQTT_TOPIC = "jetson/face_recognition/results"

        # Global variables - same as your original
        self.latest_detections = []
        self.detections_lock = threading.Lock()
        self.frame_queue = queue.Queue(maxsize=5)

        # Control variables
        self.mqtt_client = None
        self.rtsp_thread = None
        self.is_running = False
        self.mqtt_connected = False

        # Callbacks for external integration
        self.on_detection_callback = None
        self.on_frame_callback = None
        self.on_status_change_callback = None

    def on_connect(self, client, userdata, flags, rc):
        """MQTT connection callback - same as your original"""
        logger.info(f"MQTT Client Connected with result code {rc}")
        if rc == 0:
            self.mqtt_connected = True
            client.subscribe(self.MQTT_TOPIC)
            logger.info(f"Subscribed to topic: {self.MQTT_TOPIC}")
            if self.on_status_change_callback:
                self.on_status_change_callback("mqtt_connected", True)
        else:
            self.mqtt_connected = False
            if self.on_status_change_callback:
                self.on_status_change_callback("mqtt_connected", False)

    def on_message(self, client, userdata, msg):
        """MQTT message callback - same as your original"""
        try:
            # Decode the JSON payload
            results = json.loads(msg.payload.decode())

            # Your original test data structure (keep for fallback)
            results_1 = {
                'timestamp': '2025-07-07T19:56:14.855707',
                'frame_dimensions': {'width': 1280, 'height': 720},
                'detected_faces': [{
                    "box": [100, 50, 150, 200],  # x, y, width, height
                    "name": "John Doe",
                    "confidence": 95,
                    "person_id": "some_id_123"
                }],
                'flask_processing_fps': 0.9458355583137295,
                'avg_inference_time_ms': 1086.901370684306
            }

            # Extract detected faces
            detected_faces = results.get("detected_faces", [])

            with self.detections_lock:
                self.latest_detections = detected_faces

            logger.info(f"Received {len(detected_faces)} detections via MQTT.")

            # Call external callback if provided
            if self.on_detection_callback:
                self.on_detection_callback(detected_faces, results)

        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from MQTT: {e}")
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")

    def on_disconnect(self, client, userdata, rc):
        """MQTT disconnect callback"""
        self.mqtt_connected = False
        logger.info("MQTT Client Disconnected")
        if self.on_status_change_callback:
            self.on_status_change_callback("mqtt_connected", False)

    def rtsp_reader_loop(self):
        """RTSP stream reader thread - same as your original"""
        cap = None
        while self.is_running:
            try:
                if cap is None or not cap.isOpened():
                    logger.info(f"Attempting to open RTSP stream: {self.JETSON_RTSP_URL}")
                    cap = cv2.VideoCapture(self.JETSON_RTSP_URL)
                    if not cap.isOpened():
                        logger.warning("Failed to open RTSP stream. Retrying in 5 seconds...")
                        time.sleep(5)
                        continue
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reduce buffer for lower latency
                    logger.info("RTSP stream opened successfully.")
                    if self.on_status_change_callback:
                        self.on_status_change_callback("rtsp_connected", True)

                ret, frame = cap.read()
                if ret:
                    print(f"DEBUG: Successfully read frame {frame.shape}, queue size: {self.frame_queue.qsize()}")
                    try:
                        # Put frame into queue, dropping oldest if full
                        self.frame_queue.put_nowait(frame)

                        # Call external callback if provided
                        if self.on_frame_callback:
                            self.on_frame_callback(frame)

                    except queue.Full:
                        try:
                            self.frame_queue.get_nowait()  # Discard oldest
                            self.frame_queue.put_nowait(frame)
                        except queue.Empty:
                            pass
                else:
                    logger.warning("Failed to read frame from RTSP stream. Re-initializing capture...")
                    if cap is not None:
                        cap.release()
                    cap = None
                    if self.on_status_change_callback:
                        self.on_status_change_callback("rtsp_connected", False)

                time.sleep(0.01)  # Small sleep to prevent busy-waiting

            except Exception as e:
                logger.error(f"Error in RTSP reader loop: {e}")
                if cap is not None:
                    cap.release()
                cap = None
                if self.on_status_change_callback:
                    self.on_status_change_callback("rtsp_connected", False)
                time.sleep(5)

        # Cleanup when stopping
        if cap is not None:
            cap.release()
        logger.info("RTSP reader loop stopped")

    def get_latest_frame_with_detections(self, display_width=800):
        """
        Get the latest frame with detection overlays applied
        Same logic as your original display loop
        """
        try:
            # Get the latest frame from the queue (non-blocking)
            frame = self.frame_queue.get_nowait()
            if hasattr(self, '_frame_count'):
                self._frame_count += 1
            else:
                self._frame_count = 1

            if self._frame_count % 30 == 0:  # Every ~1 second
                logger.debug(f"Processing frame {self._frame_count}, queue size: {self.frame_queue.qsize()}")
        except queue.Empty:
            return None

        if frame is None:
            return None

        # Overlay detections - same as your original logic
        display_height = int(frame.shape[0] * (display_width / frame.shape[1]))
        frame_display = imutils.resize(frame, width=display_width)

        # Calculate scaling factors for bounding boxes
        scale_x = display_width / frame.shape[1]
        scale_y = display_height / frame.shape[0]

        with self.detections_lock:
            current_detections = list(self.latest_detections)  # Get a copy

        for detection in current_detections:
            try:
                # Bounding box coordinates from MQTT are [x, y, w, h]
                x_orig, y_orig, w_orig, h_orig = detection["box"]
                name = detection["name"]
                confidence = detection["confidence"]

                # Scale bounding box coordinates to the display frame size
                x = int(x_orig * scale_x)
                y = int(y_orig * scale_y)
                w = int(w_orig * scale_x)
                h = int(h_orig * scale_y)

                # Ensure coordinates are within bounds
                x = max(0, min(x, frame_display.shape[1] - 1))
                y = max(0, min(y, frame_display.shape[0] - 1))
                w = max(1, min(w, frame_display.shape[1] - x))
                h = max(1, min(h, frame_display.shape[0] - y))

                color = (0, 255, 0) if name != "Unknown" else (0, 0, 255)
                cv2.rectangle(frame_display, (x, y), (x + w, y + h), color, 2)

                label = f"{name}"
                if confidence > 0:
                    label += f" ({confidence:.0f}%)"

                cv2.putText(frame_display, label, (x, y + h + 20),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            except Exception as e:
                logger.error(f"Error drawing detection: {e}")

        return frame_display

    def start_services(self):
        """Start MQTT client and RTSP thread"""
        if self.is_running:
            logger.warning("Services already running")
            return True

        try:
            self.is_running = True

            # Start MQTT client
            self.mqtt_client = mqtt.Client()
            self.mqtt_client.on_connect = self.on_connect
            self.mqtt_client.on_message = self.on_message
            self.mqtt_client.on_disconnect = self.on_disconnect
            self.mqtt_client.connect(self.MQTT_BROKER_HOST, self.MQTT_PORT, 60)
            self.mqtt_client.loop_start()  # Start MQTT loop in background

            # Start RTSP reader thread
            self.rtsp_thread = threading.Thread(target=self.rtsp_reader_loop, daemon=True)
            self.rtsp_thread.start()

            logger.info("RTSP and MQTT services started successfully")
            return True

        except Exception as e:
            logger.error(f"Error starting services: {e}")
            self.is_running = False
            return False

    def stop_services(self):
        """Stop MQTT client and RTSP thread"""
        logger.info("Stopping RTSP and MQTT services...")

        self.is_running = False

        # Stop MQTT client
        if self.mqtt_client is not None:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
            self.mqtt_client = None
            self.mqtt_connected = False

        # Clear detection data
        with self.detections_lock:
            self.latest_detections.clear()

        # Clear frame queue
        while not self.frame_queue.empty():
            try:
                self.frame_queue.get_nowait()
            except queue.Empty:
                break

        logger.info("Services stopped successfully")

    def get_status(self):
        """Get current service status"""
        return {
            "is_running": self.is_running,
            "mqtt_connected": self.mqtt_connected,
            "rtsp_url": self.JETSON_RTSP_URL,
            "mqtt_broker": f"{self.MQTT_BROKER_HOST}:{self.MQTT_PORT}",
            "mqtt_topic": self.MQTT_TOPIC,
            "active_detections": len(self.latest_detections),
            "frame_queue_size": self.frame_queue.qsize()
        }

    def get_latest_detections(self):
        """Get copy of latest detections"""
        with self.detections_lock:
            return list(self.latest_detections)

    def set_callbacks(self, on_detection=None, on_frame=None, on_status_change=None):
        """Set callback functions for external integration"""
        self.on_detection_callback = on_detection
        self.on_frame_callback = on_frame
        self.on_status_change_callback = on_status_change


def main():
    """Original main function for standalone execution"""
    stream_client = RTSPMQTTStreamClient()

    try:
        # Start services
        if not stream_client.start_services():
            print("Failed to start services")
            return

        print("Starting display loop. Press 'q' to quit.")

        while True:
            try:
                frame_display = stream_client.get_latest_frame_with_detections(display_width=1200)

                if frame_display is not None:
                    # Display the frame - same as your original
                    cv2.imshow('Processed RTSP Stream (Edge Server)', frame_display)

                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break

            except Exception as e:
                print(f"Error in display loop: {e}")
                time.sleep(0.1)

    finally:
        cv2.destroyAllWindows()
        stream_client.stop_services()
        print("Application shut down.")

if __name__ == "__main__":
    main()