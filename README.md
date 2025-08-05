# 6G-RESCUE Edge ML Operations System

A comprehensive edge computing platform demonstrating ML model deployment and real-time face recognition using 6G infrastructure, developed as part of the 6G-PATH project at Newcastle University.

## 🏗️ System Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   React Frontend │────│  FastAPI Backend │────│  JupyterHub     │
│   (Dashboard)    │    │  (Edge Server)   │    │  (akumar)       │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                    ┌───────────┼───────────┐
                    │           │           │
              ┌─────▼────┐ ┌───▼────┐ ┌───▼─────┐
              │   MQTT   │ │  RTSP  │ │ WebSocket│
              │ Broker   │ │ Stream │ │   API    │
              └──────────┘ └────────┘ └─────────┘
                    │           │
              ┌─────▼───────────▼─────┐
              │    Jetson Nano        │
              │  (192.168.2.100)     │
              │  Face Recognition     │
              └───────────────────────┘
```

## 🚀 Quick Start (Automated Installation)

### 1. Clone Repository and Run Installer
```bash
git clone <repository-url>
cd 6GRescueApplication
chmod +x install.sh
./install.sh
```

The automated installer will:
- ✅ Check system prerequisites
- ✅ Install all Python dependencies
- ✅ Install all Node.js dependencies  
- ✅ Create configuration files
- ✅ Generate startup scripts

### 2. Configure Your Network Settings
```bash
# Edit backend configuration
nano edge-ml-backend/.env

# Edit frontend configuration  
nano edge-ml-frontend/.env
```

### 3. Start the System
```bash
# Start both backend and frontend
./start-all.sh

# Or start individually:
./start-backend.sh    # In one terminal
./start-frontend.sh   # In another terminal
```

### 4. Access the Application
- **Frontend Dashboard**: http://localhost:3000
- **Backend API**: http://10.70.0.64:8080
- **API Documentation**: http://10.70.0.64:8080/docs

## 📋 Manual Installation

If you prefer manual installation or the automated script doesn't work:

### Backend Setup
```bash
cd edge-ml-backend

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install package in development mode
pip install -e .

# Start server
uvicorn main:app --host 10.70.0.64 --port 8080 --reload
```

### Frontend Setup
```bash
cd edge-ml-frontend

# Install dependencies
npm install

# Start development server
npm start
```

## 📦 Project Structure

```
6G-RESCUE-EdgeML/
├── edge-ml-backend/
│   ├── main.py                 # FastAPI application
│   ├── mqtt_stream_client.py   # RTSP/MQTT client
│   ├── requirements.txt        # Python dependencies
│   ├── setup.py               # Package setup
│   ├── .env                   # Configuration (created by installer)
│   └── README.md
├── edge-ml-frontend/
│   ├── src/
│   │   ├── App.js             # Main React component
│   │   ├── App.css            # Styling
│   │   └── index.js           # React entry point
│   ├── package.json           # Node.js dependencies
│   ├── .env                   # Configuration (created by installer)
│   └── README.md
├── install.sh                 # Automated installer
├── start-backend.sh           # Backend startup script
├── start-frontend.sh          # Frontend startup script
├── start-all.sh              # Combined startup script
└── README.md                 # This file
```

## ⚙️ Configuration Files

### Backend Configuration (.env)
```bash
# 6G-RESCUE Backend Configuration
JUPYTERHUB_URL=http://10.70.0.64
JUPYTERHUB_USER=akumar
JUPYTERHUB_TOKEN=your_token_here
JETSON_IP=192.168.2.100
MQTT_BROKER=127.0.0.1
MQTT_PORT=1883
BACKEND_HOST=10.70.0.64
BACKEND_PORT=8080
```

### Frontend Configuration (.env)
```bash
# 6G-RESCUE Frontend Configuration
REACT_APP_API_BASE=http://10.70.0.64:8080/api
REACT_APP_BACKEND_HOST=10.70.0.64
REACT_APP_BACKEND_PORT=8080
```

## 🔧 Dependencies

### Backend (Python 3.8+)
- **FastAPI**: Web framework
- **OpenCV**: Computer vision
- **MQTT**: Message broker communication
- **HTTPx**: Async HTTP client
- **Uvicorn**: ASGI server

See `edge-ml-backend/requirements.txt` for complete list.

### Frontend (Node.js 16+)
- **React**: UI framework
- **Lucide React**: Icons
- **Axios**: HTTP client

See `edge-ml-frontend/package.json` for complete list.

## 🔌 Hardware Setup

### Jetson Device Configuration
```bash
# Start RTSP server on Jetson:
gst-launch-1.0 -v test-launch \
    "v4l2src device=/dev/video0 ! video/x-raw,width=1280,height=720,framerate=30/1 ! \
     videoconvert ! x264enc bitrate=2000 ! rtph264pay name=pay0 pt=96"

# Install MQTT publisher for face recognition results
pip install paho-mqtt
```

### JupyterHub Setup
```bash
# Generate API token
jupyterhub token akumar

# Create required directories
mkdir -p /home/jupyter-akumar/face_recognition_system/edge_server/images
mkdir -p /home/jupyter-akumar/face_recognition_system/edge_server/examples
```

## 🛠️ Development

### Backend Development
```bash
cd edge-ml-backend
source venv/bin/activate

# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Code formatting
black .
flake8 .
```

### Frontend Development
```bash
cd edge-ml-frontend

# Install development dependencies (already included)
npm install

# Run tests
npm test

# Build for production
npm run build

# Lint code
npm run lint
```

## 📊 Package Management

### Python Package Installation
```bash
# Install in development mode
git clone <repo>
cd 6GRescueApplication/edge-ml-backend
pip install -e .
```

### Node.js Package Installation
```bash
# Install from source
git clone <repo>
cd 6GRescueApplication/edge-ml-frontend
npm install
```

## 🐛 Troubleshooting

### Installation Issues
```bash
# Clear npm cache
npm cache clean --force

# Clear pip cache
pip cache purge

# Reinstall dependencies
rm -rf node_modules package-lock.json
npm install

# Python virtual environment issues
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Runtime Issues
- Check `.env` configuration files
- Verify network connectivity between components
- Check firewall settings for required ports
- Review logs in startup scripts

## 📚 API Documentation

Complete API documentation is available at: `http://YOUR_BACKEND_IP:8080/docs`

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/new-feature`
3. Install development dependencies: `pip install -e ".[dev]"`
4. Make changes and add tests
5. Run tests: `pytest` and `npm test`
6. Format code: `black .` and `npm run format`
7. Commit changes: `git commit -am 'Add new feature'`
8. Push to branch: `git push origin feature/new-feature`
9. Submit pull request

---

**System Status**: ✅ Fully Operational  
**Installation**: ✅ Automated with `install.sh`  
**Last Updated**: August 2025  
**Version**: 1.0.0