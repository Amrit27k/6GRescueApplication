#!/bin/bash
# install.sh - Complete installation script for 6G-RESCUE Edge ML System

set -e  # Exit on any error

echo "🚀 6G-RESCUE Edge ML System Installation"
echo "========================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Check if running on supported OS
check_os() {
    print_header "Checking operating system..."
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        print_status "Linux detected ✓"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        print_status "macOS detected ✓"
    elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
        print_status "Windows with WSL/Cygwin detected ✓"
    else
        print_error "Unsupported operating system: $OSTYPE"
        exit 1
    fi
}

# Check prerequisites
check_prerequisites() {
    print_header "Checking prerequisites..."
    
    # Check Python
    if command -v python3 &> /dev/null; then
        python_version=$(python3 --version | cut -d' ' -f2)
        print_status "Python3 found: $python_version ✓"
    else
        print_error "Python3 is required but not installed"
        exit 1
    fi
    
    # Check Node.js
    if command -v node &> /dev/null; then
        node_version=$(node --version)
        print_status "Node.js found: $node_version ✓"
    else
        print_error "Node.js is required but not installed"
        echo "Please install Node.js 16+ from https://nodejs.org/"
        exit 1
    fi
    
    # Check npm
    if command -v npm &> /dev/null; then
        npm_version=$(npm --version)
        print_status "npm found: $npm_version ✓"
    else
        print_error "npm is required but not installed"
        exit 1
    fi
}

# Install backend dependencies
install_backend() {
    print_header "Installing backend dependencies..."
    
    if [ -d "edge-ml-backend" ]; then
        cd edge-ml-backend
        
        # Create virtual environment
        print_status "Creating Python virtual environment..."
        python3 -m venv venv
        
        # Activate virtual environment
        source venv/bin/activate
        
        # Upgrade pip
        print_status "Upgrading pip..."
        pip install --upgrade pip
        
        # Install dependencies
        print_status "Installing Python packages..."
        if [ -f "requirements.txt" ]; then
            pip install -r requirements.txt
        else
            print_warning "requirements.txt not found, installing basic dependencies..."
            pip install fastapi uvicorn[standard] opencv-python httpx aiofiles paho-mqtt imutils numpy
        fi
        
        # Install package in development mode
        if [ -f "setup.py" ]; then
            print_status "Installing package in development mode..."
            pip install -e .
        fi
        
        print_status "Backend installation completed ✓"
        cd ..
    else
        print_error "Backend directory 'edge-ml-backend' not found"
        exit 1
    fi
}

# Install frontend dependencies
install_frontend() {
    print_header "Installing frontend dependencies..."
    
    if [ -d "edge-ml-frontend" ]; then
        cd edge-ml-frontend
        
        # Install npm dependencies
        print_status "Installing Node.js packages..."
        npm install
        
        print_status "Frontend installation completed ✓"
        cd ..
    else
        print_error "Frontend directory 'edge-ml-frontend' not found"
        exit 1
    fi
}

# Create configuration files
create_config() {
    print_header "Creating configuration files..."
    
    # Backend configuration
    if [ -d "edge-ml-backend" ]; then
        cd edge-ml-backend
        
        if [ ! -f ".env" ]; then
            print_status "Creating backend .env file..."
            cat > .env << EOF
# 6G-RESCUE Backend Configuration
JUPYTERHUB_URL=http://10.70.0.64
JUPYTERHUB_USER=akumar
JUPYTERHUB_TOKEN=your_token_here
JETSON_IP=192.168.2.100
MQTT_BROKER=127.0.0.1
MQTT_PORT=1883
BACKEND_HOST=10.70.0.64
BACKEND_PORT=8080
EOF
            print_status "Created .env file - please update with your settings"
        fi
        
        cd ..
    fi
    
    # Frontend configuration
    if [ -d "edge-ml-frontend" ]; then
        cd edge-ml-frontend
        
        if [ ! -f ".env" ]; then
            print_status "Creating frontend .env file..."
            cat > .env << EOF
# 6G-RESCUE Frontend Configuration
REACT_APP_API_BASE=http://10.70.0.64:8080/api
REACT_APP_BACKEND_HOST=10.70.0.64
REACT_APP_BACKEND_PORT=8080
EOF
            print_status "Created frontend .env file - please update with your settings"
        fi
        
        cd ..
    fi
}

# Create startup scripts
create_startup_scripts() {
    print_header "Creating startup scripts..."
    
    # Backend startup script
    cat > start-backend.sh << 'EOF'
#!/bin/bash
echo "Starting 6G-RESCUE Backend..."
cd edge-ml-backend
source venv/bin/activate
uvicorn main:app --host 10.70.0.64 --port 8080 --reload
EOF
    chmod +x start-backend.sh
    
    # Frontend startup script
    cat > start-frontend.sh << 'EOF'
#!/bin/bash
echo "Starting 6G-RESCUE Frontend..."
cd edge-ml-frontend
npm start
EOF
    chmod +x start-frontend.sh
    
    # Combined startup script
    cat > start-all.sh << 'EOF'
#!/bin/bash
echo "Starting 6G-RESCUE Complete System..."
echo "This will start both backend and frontend in separate terminals"

# Start backend in background
gnome-terminal -- bash -c "./start-backend.sh; exec bash" 2>/dev/null || \
xterm -e "./start-backend.sh" 2>/dev/null || \
echo "Please run './start-backend.sh' in a separate terminal"

# Wait a bit for backend to start
sleep 3

# Start frontend in background
gnome-terminal -- bash -c "./start-frontend.sh; exec bash" 2>/dev/null || \
xterm -e "./start-frontend.sh" 2>/dev/null || \
echo "Please run './start-frontend.sh' in a separate terminal"

echo "System startup initiated!"
echo "Backend: http://10.70.0.64:8080"
echo "Frontend: http://localhost:3000"
EOF
    chmod +x start-all.sh
    
    print_status "Startup scripts created ✓"
}

# Main installation process
main() {
    print_status "Starting installation process..."
    
    check_os
    check_prerequisites
    install_backend
    install_frontend
    create_config
    create_startup_scripts
    
    echo ""
    echo "🎉 Installation completed successfully!"
    echo "======================================="
    echo ""
    echo "Next steps:"
    echo "1. Update configuration files (.env) with your network settings"
    echo "2. Ensure your Jetson device is running RTSP server"
    echo "3. Start the backend: ./start-backend.sh"
    echo "4. Start the frontend: ./start-frontend.sh"
    echo "5. Or start both: ./start-all.sh"
    echo ""
    echo "Access points:"
    echo "• Frontend Dashboard: http://localhost:3000"
    echo "• Backend API: http://10.70.0.64:8080"
    echo "• API Documentation: http://10.70.0.64:8080/docs"
    echo ""
    print_status "Installation complete! 🚀"
}

# Run main function
main "$@"