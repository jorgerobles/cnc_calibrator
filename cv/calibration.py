# cv/calibration.py
# Calibration decorator for camera manager
import numpy as np
from functools import wraps
from typing import Optional, Tuple


def calibration_aware():
    """
    Decorator that injects calibration capabilities into a class.
    Similar to @event_aware pattern used in the project.
    
    Injected attributes:
        - camera_matrix: np.ndarray or None
        - dist_coeffs: np.ndarray or None
        - _calibration_file: str or None
    
    Injected methods:
        - load_calibration(file_path: str) -> bool
        - save_calibration(file_path: str) -> bool
        - is_calibrated() -> bool
        - get_calibration() -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]
        - get_calibration_info() -> dict
    
    Usage:
        CalibratedCamera = calibration_aware()(CameraManager)
    """
    
    def decorator(cls):
        # Store original __init__
        original_init = cls.__init__
        
        @wraps(original_init)
        def new_init(self, *args, **kwargs):
            # Inject calibration attributes
            self.camera_matrix = None
            self.dist_coeffs = None
            self._calibration_file = None
            
            # Call original __init__
            original_init(self, *args, **kwargs)
        
        # Replace __init__
        cls.__init__ = new_init
        
        # Inject calibration methods
        def load_calibration(self, file_path: str) -> bool:
            """Load camera calibration from .npz file"""
            try:
                data = np.load(file_path)
                self.camera_matrix = data["camera_matrix"]
                self.dist_coeffs = data["dist_coeffs"]
                self._calibration_file = file_path
                
                # Emit event if event system available
                if hasattr(self, 'emit'):
                    from .events import CameraEvents
                    self.emit(CameraEvents.CALIBRATION_LOADED, file_path)
                
                return True
            except Exception as e:
                if hasattr(self, 'emit'):
                    from .events import CameraEvents
                    self.emit(CameraEvents.ERROR, f"Failed to load calibration: {e}")
                return False
        
        def save_calibration(self, file_path: str) -> bool:
            """Save camera calibration to .npz file"""
            if not self.is_calibrated():
                if hasattr(self, 'emit'):
                    from .events import CameraEvents
                    self.emit(CameraEvents.ERROR, "No calibration data to save")
                return False
            
            try:
                np.savez(file_path,
                        camera_matrix=self.camera_matrix,
                        dist_coeffs=self.dist_coeffs)
                self._calibration_file = file_path
                
                # Emit event if event system available
                if hasattr(self, 'emit'):
                    from .events import CameraEvents
                    self.emit(CameraEvents.CALIBRATION_SAVED, file_path)
                
                return True
            except Exception as e:
                if hasattr(self, 'emit'):
                    from .events import CameraEvents
                    self.emit(CameraEvents.ERROR, f"Failed to save calibration: {e}")
                return False
        
        def is_calibrated(self) -> bool:
            """Check if camera calibration is loaded"""
            return (self.camera_matrix is not None and 
                   self.dist_coeffs is not None)
        
        def get_calibration(self) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
            """Get camera calibration matrices"""
            return self.camera_matrix, self.dist_coeffs
        
        def get_calibration_info(self) -> dict:
            """Get calibration information"""
            info = {
                'calibrated': self.is_calibrated(),
                'file': self._calibration_file
            }
            
            if self.is_calibrated():
                info['matrix_shape'] = self.camera_matrix.shape
                info['distortion_count'] = self.dist_coeffs.shape[1] if self.dist_coeffs.ndim > 1 else self.dist_coeffs.shape[0]
            
            return info
        
        # Inject methods into class
        cls.load_calibration = load_calibration
        cls.save_calibration = save_calibration
        cls.is_calibrated = is_calibrated
        cls.get_calibration = get_calibration
        cls.get_calibration_info = get_calibration_info
        
        return cls
    
    return decorator
