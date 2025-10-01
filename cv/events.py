# cv/events.py
# Event definitions for camera manager

class CameraEvents:
    """Event contracts for camera manager"""
    CONNECTED = "camera.connected"
    DISCONNECTED = "camera.disconnected"
    FRAME_CAPTURED = "camera.frame_captured"
    ERROR = "camera.error"
    RESOLUTION_CHANGED = "camera.resolution_changed"
