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
from .events import GRBLEvents


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
        self._work_offsets = [0.0, 0.0, 0.0]  # Current work coordinate offset
        
        # Setup callbacks
        self._communicator.set_status_callback(self._handle_status_update)
        self._communicator.set_async_callback(self._handle_async_message)

    # IGRBLConnection Interface
    @logged(LogLevel.INFO)
    def connect(self, port: str, baudrate: int = 115200) -> bool:
        """Connect to GRBL controller"""
        try:
            self.info(f"Connecting to {port}:{baudrate}")
            
            if not self._serial.open(port, baudrate, timeout=0.5):
                self.error("Failed to open serial connection")
                return False
            
            # Start communicator
            self._communicator.start()
            
            # ESP32 boots fast - minimal wait
            time.sleep(0.3)
            self._serial.reset_input_buffer()
            
            # Test with status query - short timeout for fast ESP32
            try:
                status_data = self._communicator.query_status(timeout=0.5)
                if status_data and 'state' in status_data:
                    self._is_connected = True
                    self.current_status = status_data['state']
                    
                    # Clear Hold state if present (prevents command execution)
                    if self.current_status.startswith('Hold'):
                        self.info(f"Machine in {self.current_status} state - clearing hold")
                        self._communicator.send_realtime_command("~")  # Resume
                        time.sleep(0.1)  # Brief wait for state change
                        
                        # Verify hold cleared
                        status_data = self._communicator.query_status(timeout=0.5)
                        if status_data:
                            self.current_status = status_data['state']
                            self.debug(f"State after resume: {self.current_status}")
                    
                    # Clear Alarm state if present (prevents command execution)
                    if self.current_status == 'Alarm':
                        self.info(f"Machine in Alarm state - unlocking")
                        try:
                            response = self._communicator.send_command_sync("$X", timeout=2.0)
                            if any(self._parser.is_ok_response(r) for r in response):
                                time.sleep(0.2)
                                # Verify alarm cleared
                                status_data = self._communicator.query_status(timeout=0.5)
                                if status_data:
                                    self.current_status = status_data['state']
                                    self.info(f"State after unlock: {self.current_status}")
                            else:
                                self.warning("Unlock command did not return OK")
                        except Exception as e:
                            self.warning(f"Failed to unlock alarm: {e}")
                    
                    # Query work offsets to calculate MPos from WPos
                    self._update_work_offsets()
                    
                    # Get fresh status after work offset query to calculate proper MPos
                    final_status = self._communicator.query_status(timeout=0.5)
                    if final_status:
                        # Calculate MPos from WPos + offsets if needed
                        if 'machine_position' not in final_status and 'work_position' in final_status:
                            wpos = final_status['work_position']
                            final_status['machine_position'] = [
                                wpos[0] + self._work_offsets[0],
                                wpos[1] + self._work_offsets[1],
                                wpos[2] + self._work_offsets[2]
                            ]
                        
                        self.current_position = final_status.get('machine_position', [0.0, 0.0, 0.0])
                        self.current_status = final_status['state']
                    else:
                        # Fallback to initial status data
                        self.current_position = status_data.get('machine_position', [0.0, 0.0, 0.0])
                    
                    self.info(f"Connected successfully - Status: {self.current_status}, Position: {self.current_position}, Offsets: {self._work_offsets}")
                    self.emit(GRBLEvents.CONNECTED, True)
                    return True
                else:
                    raise Exception("No valid GRBL status response")
                    
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
        
        # Query status and get position - fast timeout for ESP32
        try:
            status_data = self._communicator.query_status(timeout=0.5)
            if status_data and 'machine_position' in status_data:
                self.current_position = status_data['machine_position']
                return self.current_position.copy()
            else:
                raise Exception("No status response")
        except Exception as e:
            raise Exception(f"Failed to get position: {e}")

    def get_status(self) -> str:
        """Get current machine status"""
        if not self.is_connected():
            return "Disconnected"
        
        try:
            status_data = self._communicator.query_status(timeout=0.5)
            if status_data and 'state' in status_data:
                self.current_status = status_data['state']
                return self.current_status
            else:
                return "Unknown"
        except:
            return "Unknown"

    # IGRBLMovement Interface
    def home(self) -> bool:
        """Perform homing cycle"""
        try:
            response = self._communicator.send_command_sync("$H", timeout=30.0)
            return any(self._parser.is_ok_response(r) for r in response)
        except Exception as e:
            self.error(f"Homing failed: {e}")
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
            self.error(f"Move failed: {e}")
            return False

    def jog_relative(self, x: float = 0, y: float = 0, z: float = 0, feed_rate: float = 1000) -> bool:
        """Jog relative to current position"""
        try:
            command = f"$J=G91 X{x:.3f} Y{y:.3f} Z{z:.3f} F{feed_rate}"
            response = self._communicator.send_command_sync(command, timeout=10.0)
            return any(self._parser.is_ok_response(r) for r in response)
        except Exception as e:
            self.error(f"Jog failed: {e}")
            return False

    def emergency_stop(self) -> bool:
        """Emergency stop"""
        try:
            self._communicator.send_realtime_command("!")
            return True
        except Exception as e:
            self.error(f"Emergency stop failed: {e}")
            return False

    def resume(self) -> bool:
        """Resume from hold"""
        try:
            self._communicator.send_realtime_command("~")
            return True
        except Exception as e:
            self.error(f"Resume failed: {e}")
            return False

    def reset(self) -> bool:
        """Soft reset GRBL"""
        try:
            self._communicator.send_realtime_command("")  # Ctrl-X
            time.sleep(2)
            return True
        except Exception as e:
            self.error(f"Reset failed: {e}")
            return False

    def unlock(self) -> bool:
        """Unlock GRBL from alarm state ($X command)"""
        try:
            response = self._communicator.send_command_sync("$X", timeout=2.0)
            return any(self._parser.is_ok_response(r) for r in response)
        except Exception as e:
            self.error(f"Unlock failed: {e}")
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
        
        # Calculate MPos from WPos if not provided
        if 'machine_position' not in status_data and 'work_position' in status_data:
            wpos = status_data['work_position']
            # MPos = WPos + WorkOffset
            status_data['machine_position'] = [
                wpos[0] + self._work_offsets[0],
                wpos[1] + self._work_offsets[1],
                wpos[2] + self._work_offsets[2]
            ]
        
        self.current_position = status_data.get('machine_position', self.current_position)
        self.current_status = status_data['state']
        
        # Emit events if changed
        if old_position != self.current_position:
            self.emit(GRBLEvents.POSITION_CHANGED, self.current_position)
        
        if old_status != self.current_status:
            self.emit(GRBLEvents.STATUS_CHANGED, self.current_status)
    
    def _update_work_offsets(self) -> None:
        """Query and update current work coordinate offsets"""
        try:
            # Query work coordinate system offsets - fast timeout
            response = self._communicator.send_command_sync("$#", timeout=1.0)
            
            self.debug(f"Work offset query response: {len(response)} lines")
            
            # Parse offset response - format: [G54:x,y,z] or [G54:x,y,z,a]
            for line in response:
                # Look for G54-G59 work coordinate systems
                if any(line.startswith(f'[G5{i}:') for i in range(4, 10)):
                    try:
                        # Extract coordinates from [G5x:x,y,z] or [G5x:x,y,z,a]
                        coords_str = line[line.index(':')+1:line.rindex(']')]
                        coords = [float(x.strip()) for x in coords_str.split(',')]
                        if len(coords) >= 3:
                            self._work_offsets = coords[:3]
                            self.info(f"Work offsets: {self._work_offsets}")
                            return
                    except (ValueError, IndexError) as e:
                        self.debug(f"Failed to parse work offset line '{line}': {e}")
                        continue
            
            self.warning("No work coordinate offsets found in response - using [0, 0, 0]")
            
        except TimeoutError:
            self.warning("Work offset query timed out - using [0, 0, 0]")
        except Exception as e:
            self.warning(f"Work offset query failed: {e} - using [0, 0, 0]")

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
        self._work_offsets = [0.0, 0.0, 0.0]
