"""
Timeout Calculator Service - Smart timeout calculation for GRBL commands
"""
from typing import List, Tuple, Optional
from core.logger import log_aware, logged, LogLevel
from ..config import GRBLMachineConfig, GRBLConfigParser
from .command_analyzer import CommandAnalyzer
from .movement_calculator import MovementCalculator, SafetyMarginProvider


@log_aware("TimeoutCalc")
class TimeoutCalculator:
    """Calculates smart timeouts based on command analysis and machine configuration"""
    
    def __init__(self, machine_config: Optional[GRBLMachineConfig] = None):
        self.config = machine_config or GRBLMachineConfig()
        self.config_parser = GRBLConfigParser()
        self.command_analyzer = CommandAnalyzer()
        self.movement_calculator = MovementCalculator(self.config)
        self.safety_provider = SafetyMarginProvider()
        
        # Adaptive learning
        self.timeout_history = []
        self.max_history = 100
        
        self.debug(f"Initialized with config: max_rates=({self.config.max_rate_x}, {self.config.max_rate_y}, {self.config.max_rate_z}, {self.config.max_rate_a})")
    
    @logged(LogLevel.DEBUG, log_args=True, log_result=True)
    def calculate_timeout(self, command: str, current_position: Tuple[float, float, float, float] = (0, 0, 0, 0)) -> float:
        """Calculate optimal timeout for a GRBL command (4-axis support)"""
        
        # Parse the command
        parsed_cmd = self.command_analyzer.parse_command(command, current_position)
        
        # Check for fixed timeouts first
        fixed_timeout = self.safety_provider.get_fixed_timeout(parsed_cmd.command_type)
        if fixed_timeout:
            return fixed_timeout
        
        # Calculate movement time
        calculated_time = self.movement_calculator.calculate_movement_time(parsed_cmd, current_position)
        
        # Apply safety margin
        safe_timeout = self.safety_provider.apply_safety_margin(calculated_time, parsed_cmd.command_type)
        
        self.debug(f"Command '{command}' -> calculated: {calculated_time:.2f}s, safe: {safe_timeout:.2f}s")
        
        return safe_timeout
    
    def update_machine_config(self, settings_response: List[str]) -> None:
        """Update machine configuration from GRBL $$ response"""
        try:
            new_config = self.config_parser.parse_settings(settings_response)
            self.config = new_config
            self.movement_calculator = MovementCalculator(self.config)
            
            self.info(f"Updated machine config from GRBL settings")
            self.debug(f"New max rates: X={self.config.max_rate_x}, Y={self.config.max_rate_y}, Z={self.config.max_rate_z}, A={self.config.max_rate_a}")
            
        except Exception as e:
            self.error(f"Failed to parse machine config: {e}")
    
    def record_execution_time(self, command: str, predicted_time: float, actual_time: float) -> None:
        """Record actual execution time for adaptive learning"""
        self.timeout_history.append({
            'command': command,
            'predicted': predicted_time,
            'actual': actual_time,
            'accuracy': actual_time / predicted_time if predicted_time > 0 else 1.0
        })
        
        # Limit history size
        if len(self.timeout_history) > self.max_history:
            self.timeout_history.pop(0)
        
        # Adaptive adjustment
        if len(self.timeout_history) >= 10:
            recent_accuracy = [h['accuracy'] for h in self.timeout_history[-10:]]
            avg_accuracy = sum(recent_accuracy) / len(recent_accuracy)
            
            if avg_accuracy > 1.2:  # Consistently over-predicting
                self.safety_provider.base_safety_factor *= 0.95
                self.debug(f"Reduced safety factor to {self.safety_provider.base_safety_factor:.2f}")
            elif avg_accuracy < 0.8:  # Consistently under-predicting
                self.safety_provider.base_safety_factor *= 1.05
                self.debug(f"Increased safety factor to {self.safety_provider.base_safety_factor:.2f}")
    
    def get_statistics(self) -> dict:
        """Get timeout calculation statistics"""
        if not self.timeout_history:
            return {'total_commands': 0}
        
        accuracies = [h['accuracy'] for h in self.timeout_history]
        
        return {
            'total_commands': len(self.timeout_history),
            'avg_accuracy': sum(accuracies) / len(accuracies),
            'min_accuracy': min(accuracies),
            'max_accuracy': max(accuracies),
            'current_safety_factor': self.safety_provider.base_safety_factor
        }


class TimeoutCalculatorService:
    """Service wrapper that decorates GRBLController with smart timeout calculation"""
    
    def __init__(self, grbl_controller, timeout_calculator: Optional[TimeoutCalculator] = None):
        self._grbl = grbl_controller
        self._timeout_calc = timeout_calculator or TimeoutCalculator()
        self._config_initialized = False
        
        # Initialize machine config when connected
        if hasattr(grbl_controller, 'listen'):
            grbl_controller.listen('grbl.connected', self._on_connected)
    
    def _on_connected(self, success: bool) -> None:
        """Initialize machine configuration when GRBL connects"""
        if success and not self._config_initialized:
            try:
                settings = self._grbl.send_command("$$", custom_timeout=5.0)
                self._timeout_calc.update_machine_config(settings)
                self._config_initialized = True
            except Exception as e:
                # Fallback to default config
                print(f"Could not initialize machine config: {e}")
    
    # Enhanced command methods with smart timeouts (4-axis support)
    def send_command(self, command: str, custom_timeout: Optional[float] = None) -> List[str]:
        """Send command with smart timeout calculation (4-axis)"""
        if custom_timeout:
            return self._grbl.send_command(command, custom_timeout)
        
        # Get current 4-axis position (extend 3-axis to 4-axis if needed)
        current_pos = getattr(self._grbl, 'current_position', [0, 0, 0])
        if len(current_pos) == 3:
            current_pos = current_pos + [0.0]  # Add A-axis if not present
        elif len(current_pos) != 4:
            current_pos = [0.0, 0.0, 0.0, 0.0]  # Default 4-axis position
        
        # Calculate smart timeout
        timeout = self._timeout_calc.calculate_timeout(command, tuple(current_pos))
        
        # Track execution time for learning
        import time
        start_time = time.time()
        try:
            result = self._grbl.send_command(command, timeout)
            execution_time = time.time() - start_time
            self._timeout_calc.record_execution_time(command, timeout, execution_time)
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            self._timeout_calc.record_execution_time(command, timeout, execution_time)
            raise
    
    def send_command_async(self, command: str, custom_timeout: Optional[float] = None):
        """Send command asynchronously with smart timeout (4-axis)"""
        if custom_timeout:
            return self._grbl.send_command_async(command, custom_timeout)
        
        # Get current 4-axis position
        current_pos = getattr(self._grbl, 'current_position', [0, 0, 0])
        if len(current_pos) == 3:
            current_pos = current_pos + [0.0]
        elif len(current_pos) != 4:
            current_pos = [0.0, 0.0, 0.0, 0.0]
        
        timeout = self._timeout_calc.calculate_timeout(command, tuple(current_pos))
        return self._grbl.send_command_async(command, timeout)
    
    def get_timeout_statistics(self) -> dict:
        """Get timeout calculation statistics"""
        return self._timeout_calc.get_statistics()
    
    # Delegate all other methods to the wrapped controller
    def __getattr__(self, name):
        return getattr(self._grbl, name)


# Factory function for convenience
def create_smart_grbl_controller(grbl_controller, machine_config: Optional[GRBLMachineConfig] = None):
    """Factory function to create a GRBLController with smart timeout calculation"""
    timeout_calc = TimeoutCalculator(machine_config)
    return TimeoutCalculatorService(grbl_controller, timeout_calc)
