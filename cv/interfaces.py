# cv/interfaces.py
# Segregated interfaces for computer vision components
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Tuple

import numpy as np


class ICVConnection(ABC):
    """Interface for camera connection management"""
    
    @abstractmethod
    def connect(self) -> bool:
        """Connect to camera"""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from camera"""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if camera is connected"""
        pass


class ICVCapture(ABC):
    """Interface for frame capture"""
    
    @abstractmethod
    def capture_frame(self) -> Optional[np.ndarray]:
        """Capture a single frame from camera"""
        pass


class ICVHardware(ABC):
    """Interface for camera hardware enumeration and properties"""
    
    @abstractmethod
    def list_cameras(self) -> List[Dict[str, Any]]:
        """List available cameras"""
        pass
    
    @abstractmethod
    def set_resolution(self, width: int, height: int) -> bool:
        """Set camera resolution"""
        pass
    
    @abstractmethod
    def get_camera_info(self) -> Dict[str, Any]:
        """Get camera information"""
        pass


class ICVCalibration(ABC):
    """Interface for camera calibration management"""
    
    @abstractmethod
    def load_calibration(self, file_path: str) -> bool:
        """Load calibration from file"""
        pass
    
    @abstractmethod
    def save_calibration(self, file_path: str) -> bool:
        """Save calibration to file"""
        pass
    
    @abstractmethod
    def is_calibrated(self) -> bool:
        """Check if calibration is loaded"""
        pass
    
    @abstractmethod
    def get_calibration(self) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """Get camera matrix and distortion coefficients"""
        pass
