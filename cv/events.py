# cv/events.py
# Event definitions for camera manager

class CameraEvents:
    """Event contracts for camera manager"""
    # Hardware events
    CONNECTED = "camera.connected"
    DISCONNECTED = "camera.disconnected"
    FRAME_CAPTURED = "camera.frame_captured"
    ERROR = "camera.error"
    RESOLUTION_CHANGED = "camera.resolution_changed"
    
    # Calibration events
    CALIBRATION_LOADED = "camera.calibration_loaded"
    CALIBRATION_SAVED = "camera.calibration_saved"
