from fastapi import FastAPI, HTTPException, UploadFile, File, Form, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
import httpx
import asyncio
import json
import os
import shutil
import subprocess
import logging
from typing import List, Optional
from pydantic import BaseModel
import uuid
from datetime import datetime
import aiofiles
from pathlib import Path
import base64
import cv2
import json as json_lib
from mqtt_stream_client import RTSPMQTTStreamClient
import numpy as np
import time
import queue
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Edge ML Operations API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://10.70.0.64:3000",
        "*"  # Allow all origins for development (remove in production)
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Add OPTIONS handler for preflight requests
@app.options("/{path:path}")
async def options_handler(path: str):
    return {"message": "OK"}

# Configuration
JUPYTERHUB_URL = "http://10.70.0.64"
JUPYTERHUB_API = f"{JUPYTERHUB_URL}/hub/api"
JUPYTERHUB_USER = "akumar"  # Your specific user
JETSON_IP = "192.168.2.100"
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
websocket_message_queue = queue.Queue()

# Global variables for tracking operations
training_status = {}
deployment_status = {}
jupyterhub_token = None

# Stream client global variables
stream_client = None
active_websockets = []

# Pydantic models
class JupyterHubTokenRequest(BaseModel):
    token: str

class TrainingRequest(BaseModel):
    object_name: str
    training_id: str

class DeploymentRequest(BaseModel):
    model_type: str = "rf"

class StatusResponse(BaseModel):
    status: str
    message: str
    progress: Optional[int] = None
    details: Optional[dict] = None

# Stream client initialization
def initialize_stream_client():
    """Initialize the MQTT/RTSP stream client with queue-based messaging"""
    global stream_client
    if stream_client is None:
        stream_client = RTSPMQTTStreamClient()

        def on_detection_callback(detected_faces, full_results):
            """Called when new detections arrive via MQTT - uses queue"""
            if detected_faces and active_websockets:
                detection_data = {
                    "type": "detections",
                    "data": detected_faces,
                    "timestamp": full_results.get("timestamp", ""),
                    "frame_dimensions": full_results.get("frame_dimensions", {"width": 1280, "height": 720})
                }

                # Put message in queue instead of sending directly
                try:
                    websocket_message_queue.put_nowait(detection_data)
                except queue.Full:
                    logger.warning("WebSocket message queue is full, dropping message")

        def on_status_change_callback(status_type, status_value):
            """Called when service status changes - uses queue"""
            status_data = {
                "type": "status_change",
                "status_type": status_type,
                "status_value": status_value,
                "timestamp": datetime.now().isoformat()
            }

            try:
                websocket_message_queue.put_nowait(status_data)
            except queue.Full:
                logger.warning("WebSocket message queue is full, dropping status message")

        # Set callbacks
        stream_client.set_callbacks(
            on_detection=on_detection_callback,
            on_status_change=on_status_change_callback
        )

    return stream_client

def generate_frames():
    """Generate frames for HTTP streaming using your MQTT client logic"""
    client = initialize_stream_client()

    while True:
        try:
            # Use your existing logic to get frame with detections
            frame_display = client.get_latest_frame_with_detections(display_width=800)

            if frame_display is not None:
                last_frame =  frame_display.copy()
            elif last_frame is not None:
                frame_display = last_frame
            else:
                # Send a black frame if no stream available
                frame_display = np.zeros((450, 800, 3), dtype=np.uint8)
                cv2.putText(frame_display, "No RTSP Stream", (250, 225),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

            # Encode frame as JPEG
            ret, buffer = cv2.imencode('.jpg', frame_display, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if not ret:
                continue

            frame_bytes = buffer.tobytes()

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            time.sleep(0.333)
        except Exception as e:
            logger.error(f"Error in generate_frames: {e}")
            time.sleep(0.1)

# Health check
@app.get("/")
async def root():
    return {"message": "Edge ML Operations API is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# JupyterHub connection management
@app.post("/api/jupyterhub/connect")
async def connect_jupyterhub(request: JupyterHubTokenRequest):
    global jupyterhub_token

    try:
        # Test the token by listing users
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{JUPYTERHUB_API}/users",
                headers={"Authorization": f"token {request.token}"},
                timeout=10.0
            )

        if response.status_code == 200:
            jupyterhub_token = request.token
            users = response.json()

            # Check if akumar user exists
            akumar_user = None
            for user in users:
                if user['name'] == JUPYTERHUB_USER:
                    akumar_user = user
                    break

            if not akumar_user:
                raise HTTPException(status_code=404, detail=f"User '{JUPYTERHUB_USER}' not found on JupyterHub")

            return {
                "status": "connected",
                "message": f"Successfully connected to JupyterHub as {JUPYTERHUB_USER}",
                "user_info": {
                    "name": akumar_user['name'],
                    "admin": akumar_user['admin'],
                    "server_running": akumar_user['server'] is not None
                }
            }
        else:
            raise HTTPException(status_code=401, detail="Invalid JupyterHub token")

    except httpx.TimeoutException:
        raise HTTPException(status_code=408, detail="JupyterHub connection timeout")
    except Exception as e:
        logger.error(f"JupyterHub connection error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Connection failed: {str(e)}")

@app.get("/api/jupyterhub/status")
async def jupyterhub_status():
    if not jupyterhub_token:
        return {"status": "disconnected", "message": "No token configured"}

    try:
        async with httpx.AsyncClient() as client:
            # Check user status
            response = await client.get(
                f"{JUPYTERHUB_API}/users/{JUPYTERHUB_USER}",
                headers={"Authorization": f"token {jupyterhub_token}"},
                timeout=5.0
            )

        if response.status_code == 200:
            user_info = response.json()
            return {
                "status": "connected",
                "message": f"JupyterHub accessible for user {JUPYTERHUB_USER}",
                "user_info": {
                    "name": user_info['name'],
                    "server_running": user_info['server'] is not None,
                    "last_activity": user_info.get('last_activity')
                }
            }
        else:
            return {"status": "error", "message": "User authentication failed"}

    except Exception as e:
        return {"status": "error", "message": f"Connection error: {str(e)}"}

@app.post("/api/jupyterhub/start-server")
async def start_jupyterhub_server():
    """Start JupyterHub server for akumar user"""
    if not jupyterhub_token:
        raise HTTPException(status_code=401, detail="JupyterHub not connected")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{JUPYTERHUB_API}/users/{JUPYTERHUB_USER}/server",
                headers={"Authorization": f"token {jupyterhub_token}"},
                timeout=30.0
            )

        if response.status_code in [201, 202]:
            return {"status": "starting", "message": f"Server starting for user {JUPYTERHUB_USER}"}
        elif response.status_code == 400:
            return {"status": "already_running", "message": f"Server already running for {JUPYTERHUB_USER}"}
        else:
            raise HTTPException(status_code=response.status_code, detail="Failed to start server")

    except Exception as e:
        logger.error(f"Error starting server: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Server start failed: {str(e)}")

# File upload for training
@app.post("/api/training/upload")
async def upload_training_images(
    object_name: str = Form(...),
    files: List[UploadFile] = File(...)
):
    if not jupyterhub_token:
        raise HTTPException(status_code=401, detail="JupyterHub not connected")

    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    training_id = str(uuid.uuid4())
    training_dir = UPLOAD_DIR / training_id
    training_dir.mkdir(exist_ok=True)

    try:
        uploaded_files = []

        # Save files locally first
        for i, file in enumerate(files):
            if not file.content_type.startswith('image/'):
                continue

            filename = f"{object_name}_{i+1}.jpg"
            file_path = training_dir / filename

            async with aiofiles.open(file_path, 'wb') as f:
                content = await file.read()
                await f.write(content)

            uploaded_files.append(str(file_path))

        if not uploaded_files:
            raise HTTPException(status_code=400, detail="No valid image files found")

        # Upload to JupyterHub using Contents API
        await upload_files_to_jupyterhub(object_name, uploaded_files)

        return {
            "training_id": training_id,
            "object_name": object_name,
            "files_uploaded": len(uploaded_files),
            "message": "Files uploaded successfully to JupyterHub"
        }

    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

async def upload_files_to_jupyterhub(object_name: str, file_paths: List[str]):
    """Upload files to JupyterHub via Contents API"""
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Ensure server is running
        await ensure_server_running(client)

        for i, file_path in enumerate(file_paths):
            filename = f"{object_name}_{i+1}.jpg"

            # Read file content and encode as base64
            async with aiofiles.open(file_path, 'rb') as f:
                file_content = await f.read()
                encoded_content = base64.b64encode(file_content).decode('utf-8')

            # Create directory structure in JupyterHub
            jupyter_path = f"face_recognition_system/edge_server/images/{object_name}"

            # Create directory first
            dir_data = {
                "type": "directory"
            }
            await client.put(
                f"{JUPYTERHUB_URL}/user/{JUPYTERHUB_USER}/api/contents/{jupyter_path}",
                headers={"Authorization": f"token {jupyterhub_token}"},
                json=dir_data
            )

            # Upload file
            file_data = {
                "type": "file",
                "format": "base64",
                "content": encoded_content
            }

            response = await client.put(
                f"{JUPYTERHUB_URL}/user/{JUPYTERHUB_USER}/api/contents/{jupyter_path}/{filename}",
                headers={"Authorization": f"token {jupyterhub_token}"},
                json=file_data
            )

            if response.status_code not in [200, 201]:
                logger.error(f"Failed to upload {filename}: {response.text}")
                raise Exception(f"Failed to upload {filename} to JupyterHub")

async def ensure_server_running(client: httpx.AsyncClient):
    """Ensure JupyterHub server is running for akumar user"""
    # Check if server is running
    response = await client.get(
        f"{JUPYTERHUB_API}/users/{JUPYTERHUB_USER}",
        headers={"Authorization": f"token {jupyterhub_token}"}
    )

    if response.status_code == 200:
        user_info = response.json()
        if user_info['server'] is None:
            # Start server
            logger.info(f"Starting server for user {JUPYTERHUB_USER}")
            start_response = await client.post(
                f"{JUPYTERHUB_API}/users/{JUPYTERHUB_USER}/server",
                headers={"Authorization": f"token {jupyterhub_token}"}
            )

            if start_response.status_code in [201, 202]:
                # Wait for server to be ready
                for _ in range(30):  # Wait up to 30 seconds
                    await asyncio.sleep(1)
                    check_response = await client.get(
                        f"{JUPYTERHUB_API}/users/{JUPYTERHUB_USER}",
                        headers={"Authorization": f"token {jupyterhub_token}"}
                    )
                    if check_response.status_code == 200:
                        user_status = check_response.json()
                        if user_status['server'] is not None:
                            logger.info(f"Server ready for user {JUPYTERHUB_USER}")
                            return

                raise Exception("Server failed to start within timeout")

# Deployment operations
@app.post("/api/deployment/start")
async def start_deployment(request: DeploymentRequest, background_tasks: BackgroundTasks):
    if not jupyterhub_token:
        raise HTTPException(status_code=401, detail="JupyterHub not connected")

    deployment_id = str(uuid.uuid4())

    # Initialize deployment status
    deployment_status[deployment_id] = {
        "status": "starting",
        "progress": 0,
        "message": "Initializing deployment...",
        "started_at": datetime.now().isoformat()
    }

    # Start deployment in background
    background_tasks.add_task(execute_deployment, deployment_id, request.model_type)

    return {"deployment_id": deployment_id, "status": "started", "message": "Deployment started"}

async def execute_deployment(deployment_id: str, model_type: str):
    """Execute deployment to Jetson for akumar user"""
    try:
        deployment_status[deployment_id].update({
            "status": "running",
            "progress": 20,
            "message": "Ensuring server is running..."
        })

        async with httpx.AsyncClient(timeout=180.0) as client:
            # Ensure server is running
            await ensure_server_running(client)

            deployment_status[deployment_id].update({
                "progress": 40,
                "message": "Creating kernel for deployment..."
            })

            # Create kernel for deployment
            kernel_response = await client.post(
                f"{JUPYTERHUB_URL}/user/{JUPYTERHUB_USER}/api/kernels",
                headers={"Authorization": f"token {jupyterhub_token}"},
                json={"name": "python3"}
            )

            if kernel_response.status_code != 201:
                raise Exception(f"Failed to create kernel for deployment: {kernel_response.text}")

            kernel_data = kernel_response.json()
            kernel_id = kernel_data["id"]

            deployment_status[deployment_id].update({
                "progress": 60,
                "message": "Executing deployment script..."
            })

            # Execute deployment code
            deployment_code = f'''
import subprocess
import sys
import os

try:
    # Change to the correct directory
    os.chdir('/home/jupyter-akumar')

    # Check if deployment script exists
    if os.path.exists('/home/jupyter-akumar/simple_file_transfer.py'):
        print("Found simple_file_transfer.py, executing...")
        result = subprocess.run([sys.executable, 'simple_file_transfer.py', '--model', '{model_type}'],
                               capture_output=True, text=True, timeout=120)

        print("Deployment output:", result.stdout)
        if result.stderr:
            print("Deployment errors:", result.stderr)
        print("Return code:", result.returncode)

        if result.returncode == 0:
            print("SUCCESS: Deployment completed successfully")
        else:
            print(f"ERROR: Deployment failed with return code {{result.returncode}}")
    else:
        print("ERROR: simple_file_transfer.py not found in /home/jupyter-akumar/")

except subprocess.TimeoutExpired:
    print("ERROR: Deployment script timed out")
except Exception as e:
    print(f"ERROR: Deployment failed with exception: {{str(e)}}")
    import traceback
    traceback.print_exc()
'''

            execute_response = await client.post(
                f"{JUPYTERHUB_URL}/user/{JUPYTERHUB_USER}/api/kernels/{kernel_id}/execute",
                headers={"Authorization": f"token {jupyterhub_token}"},
                json={"code": deployment_code}
            )

            if execute_response.status_code == 200:
                deployment_status[deployment_id].update({
                    "status": "completed",
                    "progress": 100,
                    "message": f"Model deployed successfully to Jetson ({model_type})",
                    "completed_at": datetime.now().isoformat()
                })
            else:
                raise Exception(f"Deployment execution failed: {execute_response.text}")

    except Exception as e:
        logger.error(f"Deployment error: {str(e)}")
        deployment_status[deployment_id].update({
            "status": "failed",
            "message": f"Deployment failed: {str(e)}",
            "error_at": datetime.now().isoformat()
        })

@app.get("/api/deployment/status/{deployment_id}")
async def get_deployment_status(deployment_id: str):
    if deployment_id not in deployment_status:
        raise HTTPException(status_code=404, detail="Deployment ID not found")

    return deployment_status[deployment_id]

# Stream endpoints using your MQTT client
@app.get("/api/stream/video")
async def video_stream():
    """HTTP endpoint for video streaming using your MQTT client"""
    client = initialize_stream_client()

    # Start services if not already running
    if not client.is_running:
        success = client.start_services()
        if not success:
            raise HTTPException(status_code=500, detail="Failed to start streaming services")

    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@app.websocket("/api/stream/detections")
async def websocket_detections(websocket: WebSocket):
    """WebSocket endpoint for real-time detection data - now with queue processing"""
    await websocket.accept()
    active_websockets.append(websocket)

    client = initialize_stream_client()

    try:
        while True:
            # Process queued messages first
            while not websocket_message_queue.empty():
                try:
                    message = websocket_message_queue.get_nowait()
                    await websocket.send_text(json_lib.dumps(message))
                except queue.Empty:
                    break
                except Exception as e:
                    logger.error(f"Error sending queued message: {e}")

            # Send periodic status updates
            await asyncio.sleep(0.1)  # Check queue more frequently

            # Send status every 10 iterations (every ~1 second)
            if hasattr(websocket_detections, 'counter'):
                websocket_detections.counter += 1
            else:
                websocket_detections.counter = 1

            if websocket_detections.counter % 10 == 0:
                status_data = {
                    "type": "status",
                    "mqtt_connected": client.mqtt_connected,
                    "active_detections": len(client.latest_detections),
                    "is_running": client.is_running,
                    "timestamp": datetime.now().isoformat()
                }
                await websocket.send_text(json_lib.dumps(status_data))

    except WebSocketDisconnect:
        if websocket in active_websockets:
            active_websockets.remove(websocket)
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if websocket in active_websockets:
            active_websockets.remove(websocket)

@app.post("/api/stream/start")
async def start_stream():
    """Start RTSP and MQTT services using your client"""
    try:
        client = initialize_stream_client()

        if client.is_running:
            return {
                "status": "already_running",
                "message": "Stream services are already running",
                **client.get_status()
            }

        success = client.start_services()

        if success:
            # Wait a moment for connections to establish
            await asyncio.sleep(2)

            return {
                "status": "started",
                "message": "RTSP and MQTT services started successfully",
                **client.get_status()
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to start services")

    except Exception as e:
        logger.error(f"Error starting stream: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start stream services: {str(e)}")

@app.post("/api/stream/stop")
async def stop_stream():
    """Stop RTSP and MQTT services"""
    try:
        client = initialize_stream_client()
        client.stop_services()

        # Clear WebSocket connections
        active_websockets.clear()

        return {
            "status": "stopped",
            "message": "RTSP and MQTT services stopped successfully"
        }

    except Exception as e:
        logger.error(f"Error stopping stream: {e}")
        return {
            "status": "error",
            "message": f"Error stopping services: {str(e)}"
        }

@app.get("/api/stream/status")
async def stream_status():
    """Enhanced stream status using your MQTT client"""
    try:
        client = initialize_stream_client()
        status = client.get_status()

        return {
            "status": "available" if status["is_running"] else "stopped",
            "rtsp_url": status["rtsp_url"],
            "mqtt_broker": status["mqtt_broker"],
            "mqtt_topic": status["mqtt_topic"],
            "mqtt_connected": status["mqtt_connected"],
            "is_running": status["is_running"],
            "active_detections": status["active_detections"],
            "frame_queue_size": status["frame_queue_size"],
            "active_websockets": len(active_websockets),
            "jupyterhub_user": JUPYTERHUB_USER
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

@app.get("/api/stream/detections/current")
async def get_current_detections():
    """Get current detections without WebSocket"""
    try:
        client = initialize_stream_client()
        detections = client.get_latest_detections()

        return {
            "detections": detections,
            "count": len(detections),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "error": str(e),
            "detections": [],
            "count": 0
        }

# System information
@app.get("/api/system/info")
async def system_info():
    return {
        "jupyterhub_url": JUPYTERHUB_URL,
        "jupyterhub_user": JUPYTERHUB_USER,
        "jetson_ip": JETSON_IP,
        "connected": jupyterhub_token is not None,
        "active_deployments": len([d for d in deployment_status.values() if d["status"] == "running"])
    }

# Cleanup old files and statuses
@app.post("/api/system/cleanup")
async def cleanup_system():
    # Clean up old upload directories
    for item in UPLOAD_DIR.iterdir():
        if item.is_dir():
            shutil.rmtree(item)

    # Clean up old statuses (keep only recent ones)
    for deployment_id in list(deployment_status.keys()):
        status = deployment_status[deployment_id]
        if status["status"] in ["completed", "failed"]:
            deployment_status.pop(deployment_id, None)

    return {"message": "Cleanup completed", "jupyterhub_user": JUPYTERHUB_USER}

# Cleanup on app shutdown
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup streaming services on shutdown"""
    global stream_client
    if stream_client is not None:
        logger.info("Shutting down streaming services...")
        stream_client.stop_services()
        stream_client = None

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="10.70.0.64", port=8080)