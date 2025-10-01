class GRBLEvents:
    """GRBL event type constants"""

    # Connection events
    WORK_OFFSETS_UPDATED = 'grbl.work_offsets_updated'
    ASYNC_MESSAGE = 'grbl.async_message'
    CONNECTED = "grbl.connected"
    DISCONNECTED = "grbl.disconnected"

    # Command events
    COMMAND_SENT = "grbl.command_sent"

    # Response events
    RESPONSE_RECEIVED = "grbl.response_received"

    # Status events
    STATUS_CHANGED = "grbl.status_changed"
    POSITION_CHANGED = "grbl.position_changed"
    HOMING_POSITION = "grbl.homing_position"

    # Error events
    ERROR = "grbl.error"

    # Debug events
    DEBUG_INFO = "grbl.debug_info"