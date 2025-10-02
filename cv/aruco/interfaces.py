# cv/aruco/interfaces.py
from abc import ABC, abstractmethod
from typing import Tuple
import numpy as np
from .types import ArUcoDetectionResult


class IArUcoDetector(ABC):
    @abstractmethod
    def detect(self, frame: np.ndarray) -> ArUcoDetectionResult: pass
    
    @abstractmethod
    def set_marker_size(self, size_mm: float) -> None: pass
    
    @abstractmethod
    def set_calibration(self, camera_matrix: np.ndarray, dist_coeffs: np.ndarray) -> None: pass


class IArUcoRenderer(ABC):
    @abstractmethod
    def render(self, frame: np.ndarray, detection: ArUcoDetectionResult) -> np.ndarray: pass
    
    @abstractmethod
    def set_options(self, **options) -> None: pass


class IArUcoCalculator(ABC):
    @abstractmethod
    def calculate_distance_to_center(self, point: Tuple[float, float], camera_center: Tuple[float, float]) -> float: pass
    
    @abstractmethod
    def calculate_marker_pose(self, corners: np.ndarray, marker_size: float, camera_matrix: np.ndarray, dist_coeffs: np.ndarray) -> Tuple[np.ndarray, np.ndarray]: pass
