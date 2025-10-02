# cv/aruco/types.py
from dataclasses import dataclass
from typing import Optional, Tuple, List
import numpy as np


@dataclass
class ArUcoMarker:
    marker_id: int
    corners: np.ndarray
    center: Tuple[float, float]
    distance_to_camera_center: float
    distance_to_camera_center_mm: Optional[float] = None
    rvec: Optional[np.ndarray] = None
    tvec: Optional[np.ndarray] = None
    distance_z_mm: Optional[float] = None
    area: float = 0.0
    confidence: float = 1.0


@dataclass
class ArUcoDetectionResult:
    frame_shape: Tuple[int, int]
    camera_center: Tuple[float, float]
    markers: List[ArUcoMarker]
    timestamp: float
    has_calibration: bool
