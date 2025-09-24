"""
GRBL Command Analyzer - Parses G-code commands to extract movement parameters
"""
import re
import math
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class CommandType(Enum):
    """Types of GRBL commands"""
    RAPID_MOVE = "G0"           # Rapid positioning
    LINEAR_MOVE = "G1"          # Linear interpolation  
    CIRCULAR_MOVE = "G2_G3"     # Circular interpolation
    HOMING = "$H"               # Homing cycle
    STATUS_QUERY = "?"          # Status query
    SETTINGS = "$$"             # Settings query  
    PARAMETERS = "$#"           # Parameters query
    RESET = "RESET"             # Soft reset
    REALTIME = "REALTIME"       # Realtime commands (!, ~, ?)
    OTHER = "OTHER"             # Other commands


@dataclass
class ParsedCommand:
    """Parsed G-code command with extracted parameters"""
    command_type: CommandType
    target_position: Optional[Tuple[float, float, float, float]] = None  # X, Y, Z, A
    feed_rate: Optional[float] = None
    arc_center: Optional[Tuple[float, float]] = None
    arc_radius: Optional[float] = None
    is_clockwise: bool = False
    raw_command: str = ""


class CommandAnalyzer:
    """Analyzes GRBL commands to extract movement and timing parameters"""
    
    def __init__(self):
        # Regex patterns for command parsing (updated for 4-axis)
        self.position_pattern = re.compile(r'([XYZA])([-+]?\d*\.?\d+)', re.IGNORECASE)
        self.feed_pattern = re.compile(r'F([-+]?\d*\.?\d+)', re.IGNORECASE)
        self.arc_center_pattern = re.compile(r'([IJ])([-+]?\d*\.?\d+)', re.IGNORECASE)
        self.arc_radius_pattern = re.compile(r'R([-+]?\d*\.?\d+)', re.IGNORECASE)
    
    def parse_command(self, command: str, current_position: Tuple[float, float, float, float] = (0, 0, 0, 0)) -> ParsedCommand:
        """Parse a GRBL command into structured data"""
        command = command.strip().upper()
        
        # Handle realtime commands
        if command == '?':
            return ParsedCommand(
                command_type=CommandType.STATUS_QUERY,
                raw_command=command
            )
        elif command in ['!', '~', chr(0x18)]:
            return ParsedCommand(
                command_type=CommandType.REALTIME,
                raw_command=command
            )
        
        # Handle system commands
        if command == '$H':
            return ParsedCommand(
                command_type=CommandType.HOMING,
                raw_command=command
            )
        
        if command == '$$':
            return ParsedCommand(
                command_type=CommandType.SETTINGS,
                raw_command=command
            )
        
        if command == '$#':
            return ParsedCommand(
                command_type=CommandType.PARAMETERS,
                raw_command=command
            )
        
        # Handle G-code commands
        if command.startswith('G0'):
            return self._parse_movement_command(command, CommandType.RAPID_MOVE, current_position)
        elif command.startswith('G1'):
            return self._parse_movement_command(command, CommandType.LINEAR_MOVE, current_position)
        elif command.startswith('G2'):
            return self._parse_arc_command(command, True, current_position)  # Clockwise
        elif command.startswith('G3'):
            return self._parse_arc_command(command, False, current_position)  # Counter-clockwise
        
        # Default to OTHER
        return ParsedCommand(
            command_type=CommandType.OTHER,
            raw_command=command
        )
    
    def _parse_movement_command(self, command: str, cmd_type: CommandType, current_pos: Tuple[float, float, float, float]) -> ParsedCommand:
        """Parse linear movement commands (G0, G1) with 4-axis support"""
        target_pos = list(current_pos)
        feed_rate = None
        
        # Extract position coordinates for all 4 axes
        for match in self.position_pattern.finditer(command):
            axis = match.group(1).upper()
            value = float(match.group(2))
            
            if axis == 'X':
                target_pos[0] = value
            elif axis == 'Y':
                target_pos[1] = value
            elif axis == 'Z':
                target_pos[2] = value
            elif axis == 'A':
                target_pos[3] = value
        
        # Extract feed rate
        feed_match = self.feed_pattern.search(command)
        if feed_match:
            feed_rate = float(feed_match.group(1))
        
        return ParsedCommand(
            command_type=cmd_type,
            target_position=tuple(target_pos),
            feed_rate=feed_rate,
            raw_command=command
        )
    
    def _parse_arc_command(self, command: str, is_clockwise: bool, current_pos: Tuple[float, float, float, float]) -> ParsedCommand:
        """Parse circular movement commands (G2, G3) with 4-axis support"""
        target_pos = list(current_pos)
        arc_center = [0.0, 0.0]
        arc_radius = None
        feed_rate = None
        
        # Extract target position (including A-axis)
        for match in self.position_pattern.finditer(command):
            axis = match.group(1).upper()
            value = float(match.group(2))
            
            if axis == 'X':
                target_pos[0] = value
            elif axis == 'Y':
                target_pos[1] = value
            elif axis == 'Z':
                target_pos[2] = value
            elif axis == 'A':
                target_pos[3] = value
        
        # Extract arc center (I, J parameters)
        for match in self.arc_center_pattern.finditer(command):
            axis = match.group(1).upper()
            value = float(match.group(2))
            
            if axis == 'I':
                arc_center[0] = value
            elif axis == 'J':
                arc_center[1] = value
        
        # Extract arc radius (R parameter)
        radius_match = self.arc_radius_pattern.search(command)
        if radius_match:
            arc_radius = float(radius_match.group(1))
        
        # Extract feed rate
        feed_match = self.feed_pattern.search(command)
        if feed_match:
            feed_rate = float(feed_match.group(1))
        
        return ParsedCommand(
            command_type=CommandType.CIRCULAR_MOVE,
            target_position=tuple(target_pos),
            feed_rate=feed_rate,
            arc_center=tuple(arc_center),
            arc_radius=arc_radius,
            is_clockwise=is_clockwise,
            raw_command=command
        )
    
    def calculate_4d_distance(self, start_pos: Tuple[float, float, float, float], 
                            end_pos: Tuple[float, float, float, float], 
                            has_rotary_a: bool = True) -> float:
        """Calculate distance for 4-axis movement (linear + rotary)"""
        # Linear distance (X, Y, Z)
        linear_distance = math.sqrt(
            (end_pos[0] - start_pos[0])**2 +
            (end_pos[1] - start_pos[1])**2 +
            (end_pos[2] - start_pos[2])**2
        )
        
        # A-axis distance
        if has_rotary_a:
            # For rotary axis, consider shortest angular path
            a_diff = abs(end_pos[3] - start_pos[3])
            a_distance = min(a_diff, 360.0 - a_diff)  # Shortest rotation
        else:
            # Linear A-axis
            a_distance = abs(end_pos[3] - start_pos[3])
        
        # For combined moves, use the dominant motion
        # This is a simplification - real kinematics are more complex
        return max(linear_distance, a_distance)
    
    def calculate_distance(self, start_pos: Tuple[float, float, float], end_pos: Tuple[float, float, float]) -> float:
        """Calculate Euclidean distance between two 3D points (legacy method)"""
        return math.sqrt(
            (end_pos[0] - start_pos[0])**2 +
            (end_pos[1] - start_pos[1])**2 +
            (end_pos[2] - start_pos[2])**2
        )
    
    def calculate_arc_length(self, start_pos: Tuple[float, float, float], end_pos: Tuple[float, float, float], 
                           center: Tuple[float, float], radius: Optional[float] = None) -> float:
        """Calculate arc length for circular movements"""
        if radius is None:
            # Calculate radius from center to start point
            radius = math.sqrt((start_pos[0] - center[0])**2 + (start_pos[1] - center[1])**2)
        
        # Calculate angle between start and end points
        start_angle = math.atan2(start_pos[1] - center[1], start_pos[0] - center[0])
        end_angle = math.atan2(end_pos[1] - center[1], end_pos[0] - center[0])
        
        angle_diff = abs(end_angle - start_angle)
        if angle_diff > math.pi:
            angle_diff = 2 * math.pi - angle_diff
        
        return radius * angle_diff
