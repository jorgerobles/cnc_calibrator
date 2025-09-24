"""
Movement Time Calculator - Calculates execution times for GRBL movements (4-axis support)
"""
import math
from typing import Tuple, Optional, List
from src.grbl_config import GRBLMachineConfig
from src.command_analyzer import ParsedCommand, CommandType


class MovementCalculator:
    """Calculates movement execution times based on machine physics (4-axis support)"""
    
    def __init__(self, machine_config: GRBLMachineConfig):
        self.config = machine_config
    
    def calculate_movement_time(self, parsed_cmd: ParsedCommand, current_position: Tuple[float, float, float, float]) -> float:
        """Calculate total movement time for a parsed command (4-axis)"""
        
        if parsed_cmd.command_type == CommandType.HOMING:
            return self._calculate_homing_time()
        
        elif parsed_cmd.command_type in [CommandType.RAPID_MOVE, CommandType.LINEAR_MOVE]:
            return self._calculate_linear_movement_time(parsed_cmd, current_position)
        
        elif parsed_cmd.command_type == CommandType.CIRCULAR_MOVE:
            return self._calculate_arc_movement_time(parsed_cmd, current_position)
        
        # For non-movement commands, return minimal time
        return 0.1
    
    def _calculate_linear_movement_time(self, parsed_cmd: ParsedCommand, current_pos: Tuple[float, float, float, float]) -> float:
        """Calculate time for linear movements (G0, G1) with 4-axis support"""
        if not parsed_cmd.target_position:
            return 0.1
        
        target = parsed_cmd.target_position
        
        # Calculate movement distances for each axis
        distances = self._calculate_axis_distances(current_pos, target)
        
        if max(distances) < 0.001:  # Negligible movement
            return 0.1
        
        # Determine feed rate
        if parsed_cmd.command_type == CommandType.RAPID_MOVE:
            # Use maximum machine rate for rapid moves
            max_rates = [self.config.max_rate_x, self.config.max_rate_y, 
                        self.config.max_rate_z, self.config.max_rate_a]
            feed_rate = min(max_rates)
        else:
            # Use commanded feed rate or default
            feed_rate = parsed_cmd.feed_rate or self.config.default_feed_rate
        
        # Calculate time for each axis based on its characteristics
        axis_times = []
        
        # Linear axes (X, Y, Z) - use linear distance
        linear_distance = self._euclidean_distance_3d(current_pos[:3], target[:3])
        if linear_distance > 0.001:
            max_accel_linear = min(self.config.acceleration_x, self.config.acceleration_y, self.config.acceleration_z)
            feed_rate_per_sec = feed_rate / 60.0
            linear_time = self._calculate_trapezoidal_profile(linear_distance, feed_rate_per_sec, max_accel_linear)
            axis_times.append(linear_time)
        
        # A-axis (rotary) - special handling
        a_distance = distances[3]
        if a_distance > 0.001:
            if self.config.has_rotary_a:
                # For rotary axis, use degrees-based calculation
                a_feed_rate = min(feed_rate, self.config.max_rate_a) / 60.0  # degrees/sec
                # Don't override low feed rates - let user specify slow rotation
                # a_feed_rate = max(a_feed_rate, 60.0)  # At least 1 degree/sec
                a_time = self._calculate_trapezoidal_profile(a_distance, a_feed_rate, self.config.acceleration_a)
            else:
                # Linear A-axis
                a_feed_rate = feed_rate / 60.0
                a_time = self._calculate_trapezoidal_profile(a_distance, a_feed_rate, self.config.acceleration_a)
            axis_times.append(a_time)
        
        # Total time is the longest axis time (axes move simultaneously)
        return max(axis_times) if axis_times else 0.1
    
    def _calculate_axis_distances(self, current_pos: Tuple[float, float, float, float], 
                                target_pos: Tuple[float, float, float, float]) -> List[float]:
        """Calculate distance for each axis individually"""
        distances = []
        
        # Linear axes (X, Y, Z)
        for i in range(3):
            distances.append(abs(target_pos[i] - current_pos[i]))
        
        # A-axis (handle rotary wrapping)
        if self.config.has_rotary_a:
            a_diff = abs(target_pos[3] - current_pos[3])
            # For rotary axis, find shortest path (consider 360° wrapping)
            # Special case: if difference is exactly 360° or 0°, it means full rotation
            if abs(a_diff - 360.0) < 0.001:
                a_distance = 360.0  # Full rotation requested
            else:
                a_distance = min(a_diff, 360.0 - a_diff)
        else:
            a_distance = abs(target_pos[3] - current_pos[3])
        
        distances.append(a_distance)
        return distances
    
    def _calculate_arc_movement_time(self, parsed_cmd: ParsedCommand, current_pos: Tuple[float, float, float, float]) -> float:
        """Calculate time for circular movements (G2, G3) with 4-axis support"""
        if not parsed_cmd.target_position or not parsed_cmd.arc_center:
            return 0.1
        
        # Calculate arc length for X-Y plane
        if parsed_cmd.arc_radius:
            radius = parsed_cmd.arc_radius
        else:
            # Calculate radius from center offset
            radius = math.sqrt(parsed_cmd.arc_center[0]**2 + parsed_cmd.arc_center[1]**2)
        
        # Calculate arc angle
        start_angle = math.atan2(
            current_pos[1] - (current_pos[1] + parsed_cmd.arc_center[1]),
            current_pos[0] - (current_pos[0] + parsed_cmd.arc_center[0])
        )
        end_angle = math.atan2(
            parsed_cmd.target_position[1] - (current_pos[1] + parsed_cmd.arc_center[1]),
            parsed_cmd.target_position[0] - (current_pos[0] + parsed_cmd.arc_center[0])
        )
        
        angle_diff = abs(end_angle - start_angle)
        if angle_diff > math.pi:
            angle_diff = 2 * math.pi - angle_diff
        
        arc_length = radius * angle_diff
        
        # Calculate linear motion in Z and A axes during arc
        z_distance = abs(parsed_cmd.target_position[2] - current_pos[2])
        a_distance = abs(parsed_cmd.target_position[3] - current_pos[3])
        if self.config.has_rotary_a:
            # Handle rotary A-axis wrapping
            a_distance = min(a_distance, 360.0 - a_distance)
        
        # Total motion is combination of arc and linear movements
        total_distance = max(arc_length, z_distance, a_distance)
        
        # Use feed rate for timing
        feed_rate = parsed_cmd.feed_rate or self.config.default_feed_rate
        feed_rate_per_sec = feed_rate / 60.0
        
        # Simplified calculation for arcs (no acceleration profile)
        return total_distance / feed_rate_per_sec
    
    def _calculate_homing_time(self) -> float:
        """Calculate time for homing cycle (4-axis)"""
        max_travels = [self.config.max_travel_x, self.config.max_travel_y, 
                      self.config.max_travel_z, self.config.max_travel_a]
        max_travel = max(max_travels)
        
        # Homing involves:
        # 1. Fast seek to limits
        # 2. Back off and slow approach  
        # 3. Repeat for each configured axis
        
        seek_time = max_travel / (self.config.homing_seek_rate / 60.0)
        fine_time = 10.0 / (self.config.homing_feed_rate / 60.0)  # Assume 10mm/deg fine approach
        
        # Number of axes to home, with safety margin
        total_time = (seek_time + fine_time) * self.config.num_axes
        
        return total_time
    
    def _calculate_trapezoidal_profile(self, distance: float, max_velocity: float, acceleration: float) -> float:
        """Calculate time using trapezoidal velocity profile"""
        
        # Time to reach max velocity
        accel_time = max_velocity / acceleration
        accel_distance = 0.5 * acceleration * accel_time**2
        
        # Check if we can reach max velocity
        if 2 * accel_distance >= distance:
            # Triangular profile (never reach max velocity)
            accel_time = math.sqrt(distance / acceleration)
            return 2 * accel_time  # Accelerate + decelerate
        else:
            # Trapezoidal profile
            const_velocity_distance = distance - 2 * accel_distance
            const_velocity_time = const_velocity_distance / max_velocity
            return 2 * accel_time + const_velocity_time
    
    def _euclidean_distance_3d(self, pos1: Tuple[float, float, float], pos2: Tuple[float, float, float]) -> float:
        """Calculate 3D Euclidean distance (X, Y, Z only)"""
        return math.sqrt(
            (pos2[0] - pos1[0])**2 +
            (pos2[1] - pos1[1])**2 +
            (pos2[2] - pos1[2])**2
        )
    
    def _euclidean_distance(self, pos1: Tuple[float, float, float], pos2: Tuple[float, float, float]) -> float:
        """Calculate 3D Euclidean distance (legacy method)"""
        return self._euclidean_distance_3d(pos1, pos2)


class SafetyMarginProvider:
    """Provides safety margins for timeout calculations"""
    
    def __init__(self):
        self.base_safety_factor = 2.0
        self.minimum_timeout = 1.0
        self.maximum_timeout = 300.0  # 5 minutes max
        
        # Command-specific factors
        self.command_factors = {
            CommandType.HOMING: 3.0,           # Homing can be unpredictable
            CommandType.RAPID_MOVE: 1.5,       # Usually fast
            CommandType.LINEAR_MOVE: 1.5,      # Reduced from 2.0 for more realistic timeouts
            CommandType.CIRCULAR_MOVE: 2.0,    # Reduced from 2.5
            CommandType.STATUS_QUERY: 1.0,     # Minimal overhead
            CommandType.SETTINGS: 1.0,         # Quick response
            CommandType.REALTIME: 1.0,         # Immediate
            CommandType.OTHER: 2.0             # Conservative default
        }
    
    def apply_safety_margin(self, calculated_time: float, command_type: CommandType) -> float:
        """Apply safety margin to calculated time"""
        
        # Get command-specific factor
        factor = self.command_factors.get(command_type, self.base_safety_factor)
        
        # Apply safety margin
        safe_time = calculated_time * factor
        
        # Enforce limits
        safe_time = max(safe_time, self.minimum_timeout)
        safe_time = min(safe_time, self.maximum_timeout)
        
        return safe_time
    
    def get_fixed_timeout(self, command_type: CommandType) -> Optional[float]:
        """Get fixed timeout for non-movement commands"""
        fixed_timeouts = {
            CommandType.STATUS_QUERY: 2.0,
            CommandType.SETTINGS: 5.0,
            CommandType.PARAMETERS: 3.0,
            CommandType.REALTIME: 1.0,
        }
        
        return fixed_timeouts.get(command_type)
