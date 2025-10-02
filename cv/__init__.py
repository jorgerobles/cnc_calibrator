# cv/__init__.py
# Computer Vision module exports
from .manager import CameraManager, CalibratedCameraManager
from .events import CameraEvents
from .interfaces import ICVConnection, ICVCapture, ICVHardware, ICVCalibration
from .calibration import calibration_aware

__all__ = [
    'CameraManager',            # Base camera manager with events
    'CalibratedCameraManager',  # Camera manager with events + calibration
    'CameraEvents',
    'ICVConnection',
    'ICVCapture', 
    'ICVHardware',
    'ICVCalibration',
    'calibration_aware'
]
