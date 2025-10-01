"""
Smart Timeout Controller - Decorator for GRBLController with dynamic timeout calculation
Implements same interfaces as GRBLController but calculates timeouts intelligently
"""
import time
from typing import List, Optional
from concurrent.futures import Future

from core.logger import log_aware, logged, LogLevel
from core.event_broker import event_aware, event_handler, EventPriority
from .controller import GRBLController, GRBLEvents
from .interfaces import IGRBLConnection, IGRBLStatus, IGRBLMovement, IGRBLCommunication
from .timeout import TimeoutCalculator


@event_aware()
@log_aware("SmartTimeout")
class SmartTimeoutController(IGRBLConnection, IGRBLStatus, IGRBLMovement, IGRBLCommunication):
    """
    Decorator for GRBLController that adds intelligent timeout calculation.
    Maintains same interface but calculates timeouts dynamically when not specified.
    """
    
    def __init__(self, controller: GRBLController, 
                 timeout_calculator: Optional[TimeoutCalculator] = None):
        self._controller = controller
        self._timeout_calc = timeout_calculator or TimeoutCalculator()
        self._config_initialized = False
        self._controller.listen(GRBLEvents.CONNECTED, self._on_connected)
        self.info("Smart timeout controller initialized")
    
    @event_handler(GRBLEvents.CONNECTED, priority=EventPriority.HIGH)
    def _on_connected(self, success: bool) -> None:
        if not success or self._config_initialized:
            return
        try:
            self.info("Auto-configuring timeout calculator from machine settings...")
            settings = self._controller.send_command("$$", timeout=5.0)
            self._timeout_calc.update_machine_config(settings)
            self._config_initialized = True
            self.info("Machine configuration loaded successfully")
        except Exception as e:
            self.warning(f"Could not load machine config, using defaults: {e}")
    
    def connect(self, port: str, baudrate: int = 115200) -> bool:
        return self._controller.connect(port, baudrate)
    
    def disconnect(self) -> None:
        self._config_initialized = False
        self._controller.disconnect()
    
    def is_connected(self) -> bool:
        return self._controller.is_connected()
    
    def get_position(self) -> List[float]:
        return self._controller.get_position()
    
    def get_status(self) -> str:
        return self._controller.get_status()
    
    @logged(LogLevel.INFO)
    def home(self) -> bool:
        timeout = self._timeout_calc.calculate_timeout("$H", self._get_current_position_4axis())
        self.debug(f"Homing with calculated timeout: {timeout:.1f}s")
        start_time = time.time()
        try:
            result = self._execute_with_timeout("$H", timeout)
            self._record_execution("$H", timeout, time.time() - start_time)
            return result
        except Exception as e:
            self._record_execution("$H", timeout, time.time() - start_time)
            raise
    
    @logged(LogLevel.INFO)
    def move_to(self, x: float, y: float, z: float, feed_rate: float = None) -> bool:
        if feed_rate:
            command = f"G0 X{x:.3f} Y{y:.3f} Z{z:.3f} F{feed_rate}"
        else:
            command = f"G0 X{x:.3f} Y{y:.3f} Z{z:.3f}"
        timeout = self._timeout_calc.calculate_timeout(command, self._get_current_position_4axis())
        self.debug(f"Move to ({x:.1f}, {y:.1f}, {z:.1f}) with timeout: {timeout:.1f}s")
        start_time = time.time()
        try:
            result = self._execute_with_timeout(command, timeout)
            self._record_execution(command, timeout, time.time() - start_time)
            return result
        except Exception as e:
            self._record_execution(command, timeout, time.time() - start_time)
            raise
    
    @logged(LogLevel.INFO)
    def jog_relative(self, x: float = 0, y: float = 0, z: float = 0, feed_rate: float = 1000) -> bool:
        command = f"$J=G91 X{x:.3f} Y{y:.3f} Z{z:.3f} F{feed_rate}"
        timeout = self._timeout_calc.calculate_timeout(command, self._get_current_position_4axis())
        self.debug(f"Jog relative ({x:.1f}, {y:.1f}, {z:.1f}) with timeout: {timeout:.1f}s")
        start_time = time.time()
        try:
            result = self._execute_with_timeout(command, timeout)
            self._record_execution(command, timeout, time.time() - start_time)
            return result
        except Exception as e:
            self._record_execution(command, timeout, time.time() - start_time)
            raise
    
    def emergency_stop(self) -> bool:
        return self._controller.emergency_stop()
    
    def resume(self) -> bool:
        return self._controller.resume()
    
    def reset(self) -> bool:
        return self._controller.reset()
    
    def unlock(self) -> bool:
        return self._controller.unlock()
    
    @logged(LogLevel.DEBUG, log_args=True)
    def send_command(self, command: str, timeout: float = None) -> List[str]:
        if timeout is None:
            timeout = self._timeout_calc.calculate_timeout(command, self._get_current_position_4axis())
            self.debug(f"Calculated timeout for '{command}': {timeout:.1f}s")
        start_time = time.time()
        try:
            result = self._controller.send_command(command, timeout)
            self._record_execution(command, timeout, time.time() - start_time)
            return result
        except Exception as e:
            self._record_execution(command, timeout, time.time() - start_time)
            raise
    
    @logged(LogLevel.DEBUG, log_args=True)
    def send_command_async(self, command: str, timeout: float = None) -> Future:
        if timeout is None:
            timeout = self._timeout_calc.calculate_timeout(command, self._get_current_position_4axis())
            self.debug(f"Calculated timeout for async '{command}': {timeout:.1f}s")
        return self._controller.send_command_async(command, timeout)
    
    def send_realtime_command(self, command: str) -> None:
        self._controller.send_realtime_command(command)
    
    def get_timeout_statistics(self) -> dict:
        return self._timeout_calc.get_statistics()
    
    def reset_timeout_statistics(self) -> None:
        self._timeout_calc.timeout_history.clear()
        self.info("Timeout statistics reset")
    
    def _get_current_position_4axis(self) -> tuple:
        pos = self._controller.current_position
        if len(pos) == 3:
            return (pos[0], pos[1], pos[2], 0.0)
        elif len(pos) == 4:
            return tuple(pos)
        else:
            return (0.0, 0.0, 0.0, 0.0)
    
    def _execute_with_timeout(self, command: str, timeout: float) -> bool:
        response = self._controller.send_command(command, timeout)
        return any(self._controller._parser.is_ok_response(r) for r in response)
    
    def _record_execution(self, command: str, predicted: float, actual: float) -> None:
        try:
            self._timeout_calc.record_execution_time(command, predicted, actual)
        except Exception as e:
            self.debug(f"Failed to record execution time: {e}")
    
    def __getattr__(self, name):
        return getattr(self._controller, name)
