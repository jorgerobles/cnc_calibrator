# cv/aruco/events.py
# Events emitted by ArUco detection system


class ArUcoEvents:
    MARKERS_DETECTED = "aruco.markers_detected"
    NO_MARKERS = "aruco.no_markers"
    DETECTION_ERROR = "aruco.detection_error"
    MARKER_ENTERED = "aruco.marker_entered"
    MARKER_EXITED = "aruco.marker_exited"
    MARKER_MOVED = "aruco.marker_moved"
