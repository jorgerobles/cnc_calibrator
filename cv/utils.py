# cv/utils.py
# Utility functions for camera management
import cv2
import platform


def get_optimal_camera_backend():
    """Get the optimal camera backend for current platform"""
    system = platform.system().lower()

    if system == "windows":
        return cv2.CAP_DSHOW
    elif system == "linux":
        return cv2.CAP_V4L2
    elif system == "darwin":  # macOS
        return cv2.CAP_AVFOUNDATION
    else:
        return cv2.CAP_ANY
