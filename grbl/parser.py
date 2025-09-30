"""
GRBL Response Parser - Single Responsibility: Parse GRBL protocol messages
"""
import re
from typing import Optional, Dict, List


class GRBLResponseParser:
    """Parses GRBL protocol responses - no dependencies, pure function"""
    
    # Flexible status pattern - handles various GRBL status formats
    # Can have MPos, WPos, or both; supports 3 or 4 axes
    STATUS_PATTERN = re.compile(r'\<([^|>]+)(?:\|([^>]+))?\>')
    POSITION_PATTERN = re.compile(r'([+-]?\d+\.?\d*)(?:,([+-]?\d+\.?\d*))*')
    ERROR_PATTERN = re.compile(r'error:(\d+)')
    
    def parse_status_response(self, response: str) -> Optional[Dict]:
        """Parse status response and extract position/state
        
        Handles multiple formats:
        - <Idle|WPos:x,y,z>
        - <Idle|MPos:x,y,z|WPos:x,y,z>
        - <Idle|WPos:x,y,z,a> (4-axis)
        """
        match = self.STATUS_PATTERN.search(response)
        if not match:
            return None
        
        state = match.group(1).split('|')[0]  # Get state, ignore sub-states
        fields_str = match.group(2) or match.group(1)  # Get fields after state
        
        # Parse fields
        mpos = None
        wpos = None
        
        # Split by pipe and parse each field
        fields = response[1:-1].split('|')  # Remove < > and split
        
        for field in fields:
            if field.startswith('MPos:'):
                coords_str = field[5:]  # Remove "MPos:"
                mpos = self._parse_coordinates(coords_str)
            elif field.startswith('WPos:'):
                coords_str = field[5:]  # Remove "WPos:"
                wpos = self._parse_coordinates(coords_str)
        
        # Build result - use MPos if available, otherwise WPos
        result = {'state': state}
        
        if mpos:
            result['machine_position'] = mpos
        elif wpos:
            result['machine_position'] = wpos  # Use WPos as machine position if MPos not available
        
        if wpos:
            result['work_position'] = wpos
        
        return result if 'machine_position' in result else None
    
    def _parse_coordinates(self, coords_str: str) -> Optional[List[float]]:
        """Parse coordinate string to list of floats"""
        try:
            coords = [float(x.strip()) for x in coords_str.split(',')]
            # Return first 3 coordinates (X, Y, Z) - ignore 4th axis for now
            return coords[:3]
        except (ValueError, AttributeError):
            return None
    
    def is_ok_response(self, response: str) -> bool:
        """Check if response indicates success"""
        return response.strip().lower() == 'ok'
    
    def is_error_response(self, response: str) -> bool:
        """Check if response indicates error"""
        return response.strip().lower().startswith('error:')
    
    def extract_error_code(self, response: str) -> Optional[str]:
        """Extract error code from error response"""
        match = self.ERROR_PATTERN.search(response)
        return match.group(1) if match else None
    
    def is_grbl_startup(self, response: str) -> bool:
        """Check if response is GRBL startup message"""
        return 'Grbl' in response and '[MSG:' not in response
    
    def is_async_message(self, response: str) -> bool:
        """Check if response is async message (alarms, messages)"""
        return response.startswith('ALARM:') or response.startswith('[MSG:')
