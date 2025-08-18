import React, { useState, useRef, useEffect } from 'react';
import { Upload, Play, Eye, AlertCircle, CheckCircle, Loader, Camera, Send, Server, Wifi, WifiOff, User, FolderUp, Image, PlayCircle, Brain, ExternalLink } from 'lucide-react';
import './App.css';

const EdgeMLDashboard = () => {
  const [activeTab, setActiveTab] = useState('upload');
  const [files, setFiles] = useState([]);
  const [objectName, setObjectName] = useState('');
  const [isUploading, setIsUploading] = useState(false);
  const [isDeploying, setIsDeploying] = useState(false);
  const [isStreamActive, setIsStreamActive] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [hubToken, setHubToken] = useState('e976480cd4dd4addab434134aa5d8e56');
  const [connectionStatus, setConnectionStatus] = useState('disconnected');
  const [userInfo, setUserInfo] = useState(null);
  const [deploymentProgress, setDeploymentProgress] = useState(0);
  const [currentDeploymentId, setCurrentDeploymentId] = useState(null);
  const [systemInfo, setSystemInfo] = useState(null);
  const [uploadHistory, setUploadHistory] = useState([]);
  const [trainingPersonName, setTrainingPersonName] = useState('');
  const [isTraining, setIsTraining] = useState(false);
  const [trainingProgress, setTrainingProgress] = useState(0);
  const [currentTrainingId, setCurrentTrainingId] = useState(null);

  // Stream-specific state
  const [streamConnected, setStreamConnected] = useState(false);
  const [detectionData, setDetectionData] = useState([]);
  const [streamStats, setStreamStats] = useState({
    mqtt_connected: false,
    active_detections: 0,
    active_websockets: 0,
    is_running: false
  });

  const fileInputRef = useRef(null);
  const streamImgRef = useRef(null);
  const websocketRef = useRef(null);

  // Updated API base to match your backend
  const API_BASE = 'http://10.70.0.64:8080/api';
  const JUPYTERHUB_URL = "http://10.70.0.64";
  const addNotification = (message, type = 'info') => {
    const id = Date.now();
    setNotifications(prev => [...prev, { id, message, type }]);
    setTimeout(() => {
      setNotifications(prev => prev.filter(n => n.id !== id));
    }, 5000);
  };

  // Check backend health and get system info
  useEffect(() => {
    const checkBackendHealth = async () => {
      try {
        const response = await fetch('http://10.70.0.64:8080/health');
        if (response.ok) {
          console.log('Backend is healthy');
          // Get system info
          const systemResponse = await fetch(`${API_BASE}/system/info`);
          if (systemResponse.ok) {
            const sysInfo = await systemResponse.json();
            setSystemInfo(sysInfo);
          }
        }
      } catch (error) {
        addNotification('Backend server is not running. Please start the FastAPI server.', 'error');
      }
    };

    checkBackendHealth();

    // Check system info periodically
    const interval = setInterval(checkBackendHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  // WebSocket connection for real-time detection data
  useEffect(() => {
    if (isStreamActive && !websocketRef.current) {
      const wsUrl = `ws://10.70.0.64:8080/api/stream/detections`;
      websocketRef.current = new WebSocket(wsUrl);

      websocketRef.current.onopen = () => {
        console.log('WebSocket connected');
        setStreamConnected(true);
      };

      websocketRef.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          if (data.type === 'detections') {
            setDetectionData(data.data);
          } else if (data.type === 'status') {
            setStreamStats({
              mqtt_connected: data.mqtt_connected,
              active_detections: data.active_detections,
              active_websockets: data.active_websockets || 0,
              is_running: data.is_running
            });
          } else if (data.type === 'status_change') {
            console.log('Status change:', data.status_type, data.status_value);
          }
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };

      websocketRef.current.onclose = () => {
        console.log('WebSocket disconnected');
        setStreamConnected(false);
        websocketRef.current = null;
      };

      websocketRef.current.onerror = (error) => {
        console.error('WebSocket error:', error);
        setStreamConnected(false);
      };
    }

    return () => {
      if (websocketRef.current) {
        websocketRef.current.close();
        websocketRef.current = null;
        setStreamConnected(false);
      }
    };
  }, [isStreamActive]);

  // Poll deployment status
  useEffect(() => {
    let interval;
    if (currentDeploymentId && isDeploying) {
      interval = setInterval(async () => {
        try {
          const response = await fetch(`${API_BASE}/deployment/status/${currentDeploymentId}`);
          if (response.ok) {
            const status = await response.json();
            setDeploymentProgress(status.progress || 0);

            if (status.status === 'completed') {
              setIsDeploying(false);
              setCurrentDeploymentId(null);
              addNotification('Deployment completed successfully!', 'success');
            } else if (status.status === 'failed') {
              setIsDeploying(false);
              setCurrentDeploymentId(null);
              addNotification(`Deployment failed: ${status.message}`, 'error');
            }
          }
        } catch (error) {
          console.error('Error polling deployment status:', error);
        }
      }, 2000);
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [currentDeploymentId, isDeploying]);


  // Poll training status
  useEffect(() => {
    let interval;
    if (currentTrainingId && isTraining) {
      interval = setInterval(async () => {
        try {
          const response = await fetch(`${API_BASE}/training/status/${currentTrainingId}`);
          if (response.ok) {
            const status = await response.json();
            setTrainingProgress(status.progress || 0);

            if (status.status === 'completed') {
              setIsTraining(false);
              setCurrentTrainingId(null);
              addNotification('Model training completed successfully!', 'success');
            } else if (status.status === 'failed') {
              setIsTraining(false);
              setCurrentTrainingId(null);
              addNotification(`Training failed: ${status.message}`, 'error');
            }
          }
        } catch (error) {
          console.error('Error polling training status:', error);
        }
      }, 2000);
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [currentTrainingId, isTraining]);

  const testJupyterHubConnection = async () => {
    if (!hubToken) {
      addNotification('Please enter JupyterHub API token', 'error');
      return;
    }

    try {
      const response = await fetch(`${API_BASE}/jupyterhub/connect`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ token: hubToken }),
      });

      const data = await response.json();

      if (response.ok) {
        setConnectionStatus('connected');
        setUserInfo(data.user_info);
        addNotification(`Connected to JupyterHub as ${data.user_info.name}!`, 'success');

        // Show server status
        if (data.user_info.server_running) {
          addNotification('JupyterHub server is already running', 'success');
        } else {
          addNotification('JupyterHub server is not running. Will start automatically when needed.', 'info');
        }
      } else {
        setConnectionStatus('error');
        addNotification(data.detail || 'Failed to connect to JupyterHub', 'error');
      }
    } catch (error) {
      setConnectionStatus('error');
      addNotification(`Connection error: ${error.message}`, 'error');
    }
  };

  const startJupyterHubServer = async () => {
    try {
      const response = await fetch(`${API_BASE}/jupyterhub/start-server`, {
        method: 'POST',
      });

      const data = await response.json();

      if (response.ok) {
        addNotification(data.message, 'success');
        // Refresh status
        setTimeout(() => {
          checkJupyterHubStatus();
        }, 3000);
      } else {
        addNotification(data.detail || 'Failed to start server', 'error');
      }
    } catch (error) {
      addNotification(`Server start error: ${error.message}`, 'error');
    }
  };

  const checkJupyterHubStatus = async () => {
    try {
      const response = await fetch(`${API_BASE}/jupyterhub/status`);
      const data = await response.json();

      if (data.status === 'connected' && data.user_info) {
        setUserInfo(data.user_info);
      }
    } catch (error) {
      console.error('Error checking JupyterHub status:', error);
    }
  };

  const handleFileUpload = (event) => {
    const selectedFiles = Array.from(event.target.files);
    const imageFiles = selectedFiles.filter(file => file.type.startsWith('image/'));

    if (imageFiles.length !== selectedFiles.length) {
      addNotification('Only image files are allowed', 'warning');
    }

    setFiles(imageFiles);
    addNotification(`${imageFiles.length} images selected`, 'success');
  };

  const handleUploadImages = async () => {
    if (connectionStatus !== 'connected') {
      addNotification('Please connect to JupyterHub first', 'error');
      return;
    }

    if (!objectName.trim()) {
      addNotification('Please enter object name', 'error');
      return;
    }

    if (files.length === 0) {
      addNotification('Please select images to upload', 'error');
      return;
    }

    setIsUploading(true);
    addNotification('Uploading images to JupyterHub...', 'info');

    try {
      // Upload images to JupyterHub
      const formData = new FormData();
      formData.append('object_name', objectName);
      files.forEach(file => {
        formData.append('files', file);
      });

      const uploadResponse = await fetch(`${API_BASE}/training/upload`, {
        method: 'POST',
        body: formData,
      });

      if (!uploadResponse.ok) {
        const error = await uploadResponse.json();
        throw new Error(error.detail || 'Upload failed');
      }

      const uploadData = await uploadResponse.json();
      addNotification(`Successfully uploaded ${uploadData.files_uploaded} images for ${objectName}`, 'success');

      // Add to upload history
      const uploadRecord = {
        id: uploadData.training_id,
        objectName: objectName,
        filesCount: uploadData.files_uploaded,
        timestamp: new Date().toLocaleString(),
        path: `/home/jupyter-akumar/face_recognition_system/edge_server/images/${objectName}`
      };
      setUploadHistory(prev => [uploadRecord, ...prev.slice(0, 9)]); // Keep last 10 uploads

      // Clear form
      setFiles([]);
      setObjectName('');

    } catch (error) {
      addNotification(`Upload error: ${error.message}`, 'error');
    } finally {
      setIsUploading(false);
    }
  };


  const handleStartTraining = async () => {
    if (connectionStatus !== 'connected') {
      addNotification('Please connect to JupyterHub first', 'error');
      return;
    }

    if (!trainingPersonName.trim()) {
      addNotification('Please enter person name for training', 'error');
      return;
    }

    setIsTraining(true);
    setTrainingProgress(0);
    addNotification('Starting model training on JupyterHub...', 'info');

    try {
      const response = await fetch(`${API_BASE}/training/execute-notebook`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          object_name: trainingPersonName,
          notebook_path: 'face_recognition_system/edge_server/edge_train.ipynb',
          timeout: 600
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Training failed to start');
      }

      const data = await response.json();
      setCurrentTrainingId(data.training_id);
      addNotification(`Training started for ${trainingPersonName}`, 'success');

    } catch (error) {
      addNotification(`Training error: ${error.message}`, 'error');
      setIsTraining(false);
      setTrainingProgress(0);
    }
  };

  const handleDeployToJetson = async () => {
    if (connectionStatus !== 'connected') {
      addNotification('Please connect to JupyterHub first', 'error');
      return;
    }

    setIsDeploying(true);
    setDeploymentProgress(0);
    addNotification('Starting deployment to Jetson...', 'info');

    try {
      const response = await fetch(`${API_BASE}/deployment/start`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          model_type: 'rf',
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Deployment failed to start');
      }

      const data = await response.json();
      setCurrentDeploymentId(data.deployment_id);
      addNotification('Deployment started via JupyterHub', 'success');

    } catch (error) {
      addNotification(`Deployment error: ${error.message}`, 'error');
      setIsDeploying(false);
      setDeploymentProgress(0);
    }
  };

  const openJupyterHub = () => {
    window.open(JUPYTERHUB_URL, '_blank');
  };


  const startRTSPStream = async () => {
    setIsStreamActive(true);
    addNotification('Starting RTSP stream with MQTT integration...', 'info');

    try {
      // Start backend streaming services
      const response = await fetch(`${API_BASE}/stream/start`, {
        method: 'POST',
      });

      const data = await response.json();

      if (response.ok) {
        addNotification(`Stream services started. MQTT: ${data.mqtt_connected ? 'Connected' : 'Disconnected'}`, 'success');

        // Set the stream source to the backend video endpoint
        if (streamImgRef.current) {
          streamImgRef.current.src = `http://10.70.0.64:8080/api/stream/video?t=${Date.now()}`;
        }
      } else {
        throw new Error(data.detail || 'Failed to start stream');
      }
    } catch (error) {
      addNotification(`Failed to start stream: ${error.message}`, 'error');
      setIsStreamActive(false);
    }
  };

  const stopRTSPStream = async () => {
    try {
      // Stop backend streaming services
      const response = await fetch(`${API_BASE}/stream/stop`, {
        method: 'POST',
      });

      if (response.ok) {
        addNotification('Stream services stopped', 'info');
      }
    } catch (error) {
      console.error('Error stopping stream:', error);
    }

    // Clean up frontend
    if (streamImgRef.current) {
      streamImgRef.current.src = '';
    }

    if (websocketRef.current) {
      websocketRef.current.close();
      websocketRef.current = null;
    }

    setIsStreamActive(false);
    setStreamConnected(false);
    setDetectionData([]);
    setStreamStats({
      mqtt_connected: false,
      active_detections: 0,
      active_websockets: 0,
      is_running: false
    });

    addNotification('RTSP stream stopped', 'info');
  };

  const ConnectionStatus = () => (
    <div className="connection-status">
      <div className="status-indicator">
        {connectionStatus === 'connected' ? (
          <Wifi className="w-4 h-4 text-green-500" />
        ) : (
          <WifiOff className="w-4 h-4 text-red-500" />
        )}
        <div className={`status-dot ${connectionStatus}`}></div>
      </div>
      <span className="status-text">
        JupyterHub: {connectionStatus === 'connected' ? 'Connected' :
                    connectionStatus === 'error' ? 'Connection Error' : 'Disconnected'}
      </span>
      {userInfo && (
        <div className="user-info">
          <User className="w-4 h-4 text-blue-500" />
          <span className="username">{userInfo.name}</span>
          {userInfo.server_running && (
            <span className="server-status running">Server Running</span>
          )}
        </div>
      )}
    </div>
  );

  const ProgressBar = ({ progress, label }) => (
    <div className="progress-container">
      <div className="progress-header">
        <span>{label}</span>
        <span>{progress}%</span>
      </div>
      <div className="progress-bar">
        <div
          className="progress-fill"
          style={{ width: `${progress}%` }}
        ></div>
      </div>
    </div>
  );

  const NotificationList = () => (
    <div className="notifications-container">
      {notifications.map(notification => (
        <div
          key={notification.id}
          className={`notification ${notification.type}`}
        >
          {notification.type === 'success' && <CheckCircle size={16} />}
          {notification.type === 'error' && <AlertCircle size={16} />}
          {notification.type === 'warning' && <AlertCircle size={16} />}
          <span>{notification.message}</span>
        </div>
      ))}
    </div>
  );

  const StreamTabContent = () => (
    <div className="tab-content">
      <h2 className="tab-title">
        <Eye size={24} />
        <span>Live RTSP Stream with Face Recognition</span>
      </h2>

      <div className="info-box">
        <h3>Stream Information</h3>
        <p>
          Real-time RTSP stream from Jetson device with face recognition overlays via MQTT.
          Detection results are synchronized and displayed in real-time.
        </p>
      </div>

      {/* Stream Status */}
      <div className="stream-status-grid">
        <div className="status-card">
          <div className="status-header">
            <span>RTSP Stream</span>
            <div className={`status-indicator ${isStreamActive ? 'active' : 'inactive'}`}></div>
          </div>
          <p>{isStreamActive ? 'Connected' : 'Disconnected'}</p>
        </div>

        <div className="status-card">
          <div className="status-header">
            <span>MQTT Broker</span>
            <div className={`status-indicator ${streamStats.mqtt_connected ? 'active' : 'inactive'}`}></div>
          </div>
          <p>{streamStats.mqtt_connected ? 'Connected' : 'Disconnected'}</p>
        </div>

        <div className="status-card">
          <div className="status-header">
            <span>WebSocket</span>
            <div className={`status-indicator ${streamConnected ? 'active' : 'inactive'}`}></div>
          </div>
          <p>{streamConnected ? 'Connected' : 'Disconnected'}</p>
        </div>

        <div className="status-card">
          <div className="status-header">
            <span>Active Detections</span>
            <div className="detection-count">{streamStats.active_detections}</div>
          </div>
          <p>Face Recognition Results</p>
        </div>
      </div>

      {/* Video Stream */}
      <div className="video-container">
        {isStreamActive ? (
          <iframe
            src={`http://10.70.0.64:8080/api/stream/video?t=${Date.now()}`}
            style={{
              width: '100%',
              height: '100%',
              backgroundColor: '#000'
            }}
          />
        ) : (
          <div className="video-placeholder">
            <Camera size={48} />
            <p>RTSP Stream Preview</p>
            <p className="stream-url">rtsp://192.168.2.100:8554/test</p>
            <p className="stream-info">Click "Start Stream" to begin</p>
          </div>
        )}
      </div>

      {/* Stream Controls */}
      <div className="stream-controls">
        <button
          onClick={startRTSPStream}
          disabled={isStreamActive}
          className="btn btn-success"
        >
          <Play size={20} />
          <span>Start Stream</span>
        </button>
        <button
          onClick={stopRTSPStream}
          disabled={!isStreamActive}
          className="btn btn-danger"
        >
          <span>Stop Stream</span>
        </button>
      </div>

      {/* Detection Information */}
      {detectionData.length > 0 && (
        <div className="detection-info">
          <h3>Current Detections</h3>
          <div className="detection-list">
            {detectionData.map((detection, index) => (
              <div key={index} className="detection-item">
                <div className="detection-details">
                  <span className="person-name">{detection.name}</span>
                  <span className="confidence">{detection.confidence.toFixed(1)}%</span>
                </div>
                <div className="detection-coords">
                  Box: [{detection.box.join(', ')}]
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Technical Information */}
      <div className="stream-info-grid">
        <div className="stream-info">
          <h4>RTSP Configuration</h4>
          <div className="info-list">
            <p>• URL: rtsp://192.168.2.100:8554/test</p>
            <p>• Resolution: 1280x720 → 800px width</p>
            <p>• Protocol: RTSP over TCP</p>
            <p>• Codec: H.264</p>
          </div>
        </div>
        <div className="stream-info">
          <h4>MQTT Configuration</h4>
          <div className="info-list">
            <p>• Broker: 127.0.0.1:1883</p>
            <p>• Topic: jetson/face_recognition/results</p>
            <p>• Format: JSON with detection data</p>
            <p>• Real-time face recognition overlays</p>
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <div className="dashboard-container">
      <div className="dashboard-content">
        <NotificationList />

        {/* Header */}
        <div className="header-card">
          <div className="header-title">
            <Server className="w-8 h-8 text-blue-600" />
            <h1>Edge ML Operations Dashboard</h1>
            {systemInfo && (
              <div className="system-info">
                User: {systemInfo.jupyterhub_user} | Jetson: {systemInfo.jetson_ip}
              </div>
            )}
          </div>

          {/* JupyterHub Connection */}
          <div className="connection-section">
            <h3>JupyterHub Connection (akumar profile)</h3>
            <ConnectionStatus />
            <div className="connection-controls">
              <input
                type="password"
                placeholder="Enter JupyterHub API Token"
                value={hubToken}
                onChange={(e) => setHubToken(e.target.value)}
                className="token-input"
              />
              <button
                onClick={testJupyterHubConnection}
                className="btn btn-primary"
              >
                Connect
              </button>
            </div>

            {/* Server Control */}
            {connectionStatus === 'connected' && userInfo && !userInfo.server_running && (
              <div className="server-warning">
                <div className="warning-content">
                  <div>
                    <p className="warning-title">JupyterHub Server Not Running</p>
                    <p className="warning-text">Start the server to enable uploads and deployment</p>
                  </div>
                  <button
                    onClick={startJupyterHubServer}
                    className="btn btn-warning btn-small"
                  >
                    <PlayCircle size={16} />
                    <span>Start Server</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="nav-card">
          <div className="nav-tabs">
            {[
              { id: 'upload', label: 'Upload Images', icon: FolderUp },
              { id: 'training', label: 'Model Training & Deploy to IoT', icon: Brain },
              { id: 'stream', label: 'Live Stream', icon: Eye },
            ].map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                onClick={() => setActiveTab(id)}
                className={`nav-tab ${activeTab === id ? 'active' : ''}`}
              >
                <Icon size={18} />
                <span>{label}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Content */}
        <div className="content-card">
          {activeTab === 'upload' && (
            <div className="tab-content">
              <h2 className="tab-title">
                <FolderUp size={24} />
                <span>Upload Images to JupyterHub</span>
              </h2>

              <div className="info-box">
                <h3>Upload Information</h3>
                <p>
                  Images will be uploaded to JupyterHub server (akumar profile) at:
                  <code>/home/jupyter-akumar/face_recognition_system/edge_server/images/</code>
                </p>
              </div>

              <div className="form-grid">
                <div className="form-group">
                  <label>Object Name</label>
                  <input
                    type="text"
                    value={objectName}
                    onChange={(e) => setObjectName(e.target.value)}
                    placeholder="Enter object/person name"
                    className="form-input"
                    disabled={isUploading}
                  />
                </div>

                <div className="form-group">
                  <label>Training Images</label>
                  <div className="file-upload-container">
                    <input
                      type="file"
                      ref={fileInputRef}
                      onChange={handleFileUpload}
                      multiple
                      accept="image/*"
                      className="file-input-hidden"
                      disabled={isUploading}
                    />
                    <button
                      onClick={() => fileInputRef.current?.click()}
                      disabled={isUploading}
                      className="btn btn-secondary file-upload-btn"
                    >
                      <Upload size={18} />
                      <span>Select Images</span>
                    </button>
                  </div>
                  {files.length > 0 && (
                    <p className="file-count">
                      {files.length} image(s) selected
                    </p>
                  )}
                </div>
              </div>

              {files.length > 0 && (
                <div className="image-preview-section">
                  <h3>Selected Images</h3>
                  <div className="image-grid">
                    {files.slice(0, 8).map((file, index) => (
                      <div key={index} className="image-preview">
                        <img
                          src={URL.createObjectURL(file)}
                          alt={`Upload ${index + 1}`}
                          className="preview-img"
                        />
                      </div>
                    ))}
                    {files.length > 8 && (
                      <div className="image-preview more-images">
                        <span>+{files.length - 8} more</span>
                      </div>
                    )}
                  </div>
                </div>
              )}

              <button
                onClick={handleUploadImages}
                disabled={isUploading || !objectName.trim() || files.length === 0 || connectionStatus !== 'connected'}
                className="btn btn-primary btn-large"
              >
                {isUploading ? (
                  <>
                    <Loader className="animate-spin" size={20} />
                    <span>Uploading to JupyterHub...</span>
                  </>
                ) : (
                  <>
                    <FolderUp size={20} />
                    <span>Upload Images</span>
                  </>
                )}
              </button>

              {/* Upload History */}
              {uploadHistory.length > 0 && (
                <div className="upload-history">
                  <h3>Recent Uploads</h3>
                  <div className="history-list">
                    {uploadHistory.map(upload => (
                      <div key={upload.id} className="history-item">
                        <div className="history-info">
                          <div className="history-main">
                            <Image size={16} />
                            <span className="object-name">{upload.objectName}</span>
                            <span className="file-count">({upload.filesCount} files)</span>
                          </div>
                          <div className="history-meta">
                            <span className="timestamp">{upload.timestamp}</span>
                            <code className="path">{upload.path}</code>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === 'training' && (
            <div className="tab-content">
              <h2 className="tab-title">
                <Send size={24} />
                <span>Model Training & Deploy to IoT</span>
              </h2>

              <div className="info-box">
                <h3>Deployment Information</h3>
                <p>
                  Train a face recognition model using uploaded images and deploy it to your IoT device.
                  The training will execute the notebook on JupyterHub server and deployment will use MLflow plugin.
                  Execute the simple_file_transfer.py script on JupyterHub server to deploy
                  the latest trained model to your IoT device using the MLflow plugin as per instructions.
                </p>
              </div>

              {/* Training Section */}
              <div className="training-section">
                <div className="form-group">
                  <label>Person Name for Training</label>
                  <input
                    type="text"
                    value={trainingPersonName}
                    onChange={(e) => setTrainingPersonName(e.target.value)}
                    placeholder="Enter person name (must match uploaded folder name)"
                    className="form-input"
                    disabled={isTraining}
                  />
                  <p className="input-help">
                    This should match the folder name used when uploading images (e.g., "john_doe")
                  </p>
                </div>

                {isTraining && (
                  <div className="progress-section">
                    <ProgressBar progress={trainingProgress} label="Training Progress" />
                    <p className="progress-text">
                        Generating execution script for training on JupyterHub server
                    </p>
                  </div>
                )}

                <button
                  onClick={handleStartTraining}
                  disabled={isTraining || !trainingPersonName.trim() || connectionStatus !== 'connected'}
                  className="btn btn-primary btn-large"
                >
                  {isTraining ? (
                    <>
                      <Loader className="animate-spin" size={20} />
                      <span>Training Model... ({trainingProgress}%)</span>
                    </>
                  ) : (
                    <>
                      <Brain size={20} />
                      <span>Start Model Training</span>
                    </>
                  )}
                </button>
              </div>

              {/* Deployment Section */}
              <div className="deployment-section">
                <h3>Deploy to IoT Device</h3>

                <div className="deployment-info-box">
                  <h4>Deployment Details</h4>
                  <p>Deploy through MLflow plugin from JupyterHub to your IoT device.</p>
                  <div className="deployment-grid">
                    <div className="deployment-info">
                        <h5>Source</h5>
                        <p>JupyterHub (akumar profile)</p>
                    </div>
                    <div className="deployment-info">
                        <h5>Target Device</h5>
                        <p>IoT Devices (192.168.0.100) </p>
                    </div>
                    <div className="deployment-info">
                        <h5>Model Type</h5>
                        <p>Random Forest Face Recognition</p>
                    </div>
                    <div className="deployment-info">
                        <h5>Deployment Method</h5>
                        <p>MLflow Plugin</p>
                    </div>
                  </div>
                </div>

                {/* JupyterHub Access */}
                <div className="jupyterhub-access">
                    <div className="access-info">
                        <p>Access your JupyterHub instance to monitor training progress and manage notebooks.</p>
                    </div>
                    <button
                        onClick={openJupyterHub}
                        className="btn btn-secondary"
                    >
                        <ExternalLink size={18} />
                        <span>Open JupyterHub ({JUPYTERHUB_URL})</span>
                    </button>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'stream' && <StreamTabContent />}
        </div>
      </div>
    </div>
  );
};

export default EdgeMLDashboard;