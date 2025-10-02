# cv/manager.py
# Camera Manager - Lean hardware management with explicit decorator application
import cv2
import numpy as np
from typing import Optional, Dict, Any, List

from .interfaces import ICVConnection, ICVCapture, ICVHardware
from .events import CameraEvents
from .utils import get_optimal_camera_backend


class CameraManagerCore(ICVConnection, ICVCapture, ICVHardware):
    """
    Core camera manager - pure hardware management
    No decorators applied - base implementation
    """
    
    def __init__(self, camera_id: int = 0, resolution: tuple = (640, 480)):
        self.camera_id = camera_id
        self.resolution = resolution
        self.cap = None
        self._is_connected = False

    @property
    def is_connected(self) -> bool:
        """Check if camera is currently connected"""
        return self._is_connected and self.cap is not None and self.cap.isOpened()

    def list_cameras(self) -> List[Dict[str, Any]]:
        """List available cameras by testing indices 0-9"""
        cameras = []
        
        for i in range(10):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    backend = self._get_backend_name(cap)
                    cameras.append({
                        'index': i,
                        'name': f'Camera {i}',
                        'backend': backend,
                        'width': int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                        'height': int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    })
                cap.release()
        
        return cameras

    def _get_backend_name(self, cap) -> str:
        """Get backend name from capture object"""
        try:
            backend = cap.getBackendName()
            return backend if backend else "Unknown"
        except:
            return "Unknown"

    def connect(self) -> bool:
        """Connect to camera with platform-optimized backend"""
        try:
            optimal_backend = get_optimal_camera_backend()
            
            # Try optimal backend first
            self.cap = cv2.VideoCapture(self.camera_id, optimal_backend)
            
            # Fallback to default if optimal fails
            if not self.cap.isOpened():
                self.cap = cv2.VideoCapture(self.camera_id)
            
            success = self.cap.isOpened()
            
            if success:
                # Set resolution
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
                
                # Optimize for speed
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                
                # Test capture
                ret, test_frame = self.cap.read()
                if not ret:
                    success = False
                    self._is_connected = False
                    self.cap.release()
                    self.cap = None
                else:
                    self._is_connected = True
            
            # Emit event if available
            if hasattr(self, 'emit'):
                self.emit(CameraEvents.CONNECTED, success)
            
            return success
            
        except Exception as e:
            error_msg = f"Failed to connect to camera {self.camera_id}: {e}"
            if hasattr(self, 'emit'):
                self.emit(CameraEvents.ERROR, error_msg)
                self.emit(CameraEvents.CONNECTED, False)
            self._is_connected = False
            return False

    def disconnect(self) -> None:
        """Disconnect camera"""
        if self.cap:
            self.cap.release()
            self.cap = None
        
        was_connected = self._is_connected
        self._is_connected = False
        
        if was_connected and hasattr(self, 'emit'):
            self.emit(CameraEvents.DISCONNECTED)

    def capture_frame(self) -> Optional[np.ndarray]:
        """Capture a single frame"""
        if not self.cap or not self._is_connected:
            return None
        
        try:
            ret, frame = self.cap.read()
            if ret and frame is not None:
                if hasattr(self, 'emit'):
                    self.emit(CameraEvents.FRAME_CAPTURED, frame.copy())
                return frame
            else:
                if self._is_connected:
                    if hasattr(self, 'emit'):
                        self.emit(CameraEvents.ERROR, "Failed to capture frame")
                    self._is_connected = False
                    if hasattr(self, 'emit'):
                        self.emit(CameraEvents.DISCONNECTED)
                return None
        except Exception as e:
            error_msg = f"Error capturing frame: {e}"
            if hasattr(self, 'emit'):
                self.emit(CameraEvents.ERROR, error_msg)
            return None

    def set_resolution(self, width: int, height: int) -> bool:
        """Set camera resolution"""
        self.resolution = (width, height)
        
        if self.is_connected:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            
            # Verify resolution was set
            actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            if hasattr(self, 'emit'):
                self.emit(CameraEvents.RESOLUTION_CHANGED, actual_width, actual_height)
            
            return (actual_width, actual_height) == (width, height)
        
        return True  # Will be applied on next connect

    def set_camera_id(self, camera_id: int):
        """Change camera ID (requires reconnection)"""
        was_connected = self.is_connected
        if was_connected:
            self.disconnect()
        
        self.camera_id = camera_id
        
        if was_connected:
            self.connect()

    def get_camera_info(self) -> Dict[str, Any]:
        """Get camera information"""
        info = {
            "camera_id": self.camera_id,
            "connected": self.is_connected,
            "resolution": self.resolution
        }
        
        if self.is_connected and self.cap:
            try:
                info.update({
                    "width": int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                    "height": int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                    "fps": self.cap.get(cv2.CAP_PROP_FPS),
                    "backend": self._get_backend_name(self.cap)
                })
            except Exception as e:
                if hasattr(self, 'emit'):
                    self.emit(CameraEvents.ERROR, f"Error getting camera info: {e}")
        
        return info


# ============================================================================
# EXPLICIT DECORATOR APPLICATION
# ============================================================================

from core.event_broker import event_aware
from .calibration import calibration_aware

# CameraManager: Base manager with event system only
CameraManager = event_aware()(CameraManagerCore)

# CalibratedCameraManager: Full manager with event system + calibration
CalibratedCameraManager = calibration_aware()(CameraManager)
