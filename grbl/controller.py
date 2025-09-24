"""
Refactored GRBL Controller - Following SOLID Principles
Orchestrates components, maintains same interface as original
"""
import time
from concurrent.futures import Future
from typing import List, Optional
from core.event_broker import event_aware
from core.logger import log_aware, logged, LogLevel
from .interfaces import IGRBLStatus, IGRBLConnection, IGRBLMovement, IGRBLCommunication
from .serial import SerialConnection
from .parser import GRBLResponseParser
from .communicator import GRBLCommunicator


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


@event_aware()
@log_aware("GRBL")
class GRBLController(IGRBLConnection, IGRBLStatus, IGRBLMovement, IGRBLCommunication):
    """Refactored GRBL Controller following SOLID principles"""

    def __init__(self, serial_conn: Optional[SerialConnection] = None, 
                 parser: Optional[GRBLResponseParser] = None):
        # Dependency injection (with defaults for single implementer)
        self._serial = serial_conn or SerialConnection()
        self._parser = parser or GRBLResponseParser()
        self._communicator = GRBLCommunicator(self._serial, self._parser)
        
        # State tracking
        self._is_connected = False
        self.current_position = [0.0, 0.0, 0.0]
        self.current_status = "Unknown"
        
        # Setup callbacks
        self._communicator.set_status_callback(self._handle_status_update)
        self._communicator.set_async_callback(self._handle_async_message)

    # IGRBLConnection Interface
    @logged(LogLevel.INFO)
    def connect(self, port: str, baudrate: int = 115200) -> bool:
        """Connect to GRBL controller"""
        try:
            self.info(f"Connecting to {port}:{baudrate}")
            
            if not self._serial.open(port, baudrate, timeout=2.0):
                self.error("Failed to open serial connection")
                return False
            
            # Start communicator
            self._communicator.start()
            
            # Wait for GRBL startup and test communication
            time.sleep(2)
            self._serial.reset_input_buffer()
            
            # Test with status query
            try:
                response = self._communicator.send_command_sync("?", timeout=3.0)
                if response and any('>' in r for r in response):
                    self._is_connected = True
                    self.info("Connected successfully")
                    self.emit(GRBLEvents.CONNECTED, True)
                    return True
                else:
                    raise Exception("No valid GRBL response")
                    
            except Exception as e:
                self.error(f"Communication test failed: {e}")
                self._cleanup_connection()
                return False
                
        except Exception as e:
            self.error(f"Connection failed: {e}")
            self._cleanup_connection()
            return False

    @logged(LogLevel.INFO)
    def disconnect(self) -> None:
        """Disconnect from GRBL controller"""
        self.info("Disconnecting...")
        was_connected = self._is_connected
        
        self._cleanup_connection()
        
        if was_connected:
            self.emit(GRBLEvents.DISCONNECTED)
            self.info("Disconnected")

    def is_connected(self) -> bool:
        """Check if connected to GRBL"""
        return self._is_connected and self._serial.is_open()

    # IGRBLStatus Interface  
    def get_position(self) -> List[float]:
        """Get current machine position"""
        if not self.is_connected():
            raise Exception("GRBL not connected")
        
        # Force status update
        try:
            self._communicator.send_command_sync("?", timeout=2.0)
            return self.current_position.copy()
        except Exception as e:
            raise Exception(f"Failed to get position: {e}")

    def get_status(self) -> str:
        """Get current machine status"""
        if not self.is_connected():
            return "Disconnected"
        
        try:
            self._communicator.send_command_sync("?", timeout=2.0)
            return self.current_status
        except:
            return "Unknown"

    # IGRBLMovement Interface
    def home(self) -> bool:
        """Perform homing cycle"""
        try:
            response = self._communicator.send_command_sync("$H", timeout=30.0)
            return any(self._parser.is_ok_response(r) for r in response)
        except Exception as e:
            self._log(f"Homing failed: {e}")
            return False

    def move_to(self, x: float, y: float, z: float, feed_rate: float = None) -> bool:
        """Move to absolute position"""
        try:
            if feed_rate:
                command = f"G0 X{x:.3f} Y{y:.3f} Z{z:.3f} F{feed_rate}"
            else:
                command = f"G0 X{x:.3f} Y{y:.3f} Z{z:.3f}"
            
            response = self._communicator.send_command_sync(command, timeout=30.0)
            return any(self._parser.is_ok_response(r) for r in response)
        except Exception as e:
            self._log(f"Move failed: {e}")
            return False

    def jog_relative(self, x: float = 0, y: float = 0, z: float = 0, feed_rate: float = 1000) -> bool:
        """Jog relative to current position"""
        try:
            command = f"$J=G91 X{x:.3f} Y{y:.3f} Z{z:.3f} F{feed_rate}"
            response = self._communicator.send_command_sync(command, timeout=10.0)
            return any(self._parser.is_ok_response(r) for r in response)
        except Exception as e:
            self._log(f"Jog failed: {e}")
            return False

    def emergency_stop(self) -> bool:
        """Emergency stop"""
        try:
            self._communicator.send_realtime_command("!")
            return True
        except Exception as e:
            self._log(f"Emergency stop failed: {e}")
            return False

    def resume(self) -> bool:
        """Resume from hold"""
        try:
            self._communicator.send_realtime_command("~")
            return True
        except Exception as e:
            self._log(f"Resume failed: {e}")
            return False

    def reset(self) -> bool:
        """Soft reset GRBL"""
        try:
            self._communicator.send_realtime_command("")  # Ctrl-X
            time.sleep(2)
            return True
        except Exception as e:
            self._log(f"Reset failed: {e}")
            return False

    # IGRBLCommunication Interface
    def send_command(self, command: str, timeout: float = None) -> List[str]:
        """Send command synchronously"""
        if not self.is_connected():
            raise Exception("GRBL not connected")
        
        timeout = timeout or 5.0
        return self._communicator.send_command_sync(command, timeout)

    def send_command_async(self, command: str, timeout: float = None) -> Future:
        """Send command asynchronously"""
        if not self.is_connected():
            raise Exception("GRBL not connected")
        
        timeout = timeout or 5.0
        return self._communicator.send_command_async(command, timeout)

    def send_realtime_command(self, command: str) -> None:
        """Send realtime command"""
        if not self.is_connected():
            raise Exception("GRBL not connected")
        
        self._communicator.send_realtime_command(command)

    # Additional methods for compatibility - REMOVED old logging methods
    # Logging now handled by @log_aware decorator

    # Private methods
    def _handle_status_update(self, status_data: dict) -> None:
        """Handle status updates from communicator"""
        old_position = self.current_position.copy()
        old_status = self.current_status
        
        self.current_position = status_data['machine_position']
        self.current_status = status_data['state']
        
        # Emit events if changed
        if old_position != self.current_position:
            self.emit(GRBLEvents.POSITION_CHANGED, self.current_position)
        
        if old_status != self.current_status:
            self.emit(GRBLEvents.STATUS_CHANGED, self.current_status)

    def _handle_async_message(self, message: str) -> None:
        """Handle async messages from GRBL"""
        if message.startswith('ALARM:'):
            self.emit(GRBLEvents.ERROR, message)
        else:
            self.emit(GRBLEvents.ASYNC_MESSAGE, message)

    def _cleanup_connection(self) -> None:
        """Clean up connection resources"""
        self._is_connected = False
        self._communicator.stop()
        self._serial.close()
        self.current_position = [0.0, 0.0, 0.0]
        self.current_status = "Disconnected"
