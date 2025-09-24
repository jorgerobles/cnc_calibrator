"""
GRBL Response Parser - Single Responsibility: Parse GRBL protocol messages
"""
import re
from typing import Optional, Dict, List


class GRBLResponseParser:
    """Parses GRBL protocol responses - no dependencies, pure function"""
    
    # GRBL status pattern: <State|MPos:0.000,0.000,0.000|WPos:0.000,0.000,0.000>
    STATUS_PATTERN = re.compile(r'\<([^|]+)\|MPos:([^|]+)\|WPos:([^>]+)>')
    POSITION_PATTERN = re.compile(r'([+-]?\d+\.?\d*),([+-]?\d+\.?\d*),([+-]?\d+\.?\d*)')
    ERROR_PATTERN = re.compile(r'error:(\d+)')
    
    def parse_status_response(self, response: str) -> Optional[Dict]:
        """Parse status response and extract position/state"""
        match = self.STATUS_PATTERN.search(response)
        if not match:
            return None
            
        state = match.group(1)
        mpos_str = match.group(2)
        wpos_str = match.group(3)
        
        try:
            # Parse machine position
            mpos_match = self.POSITION_PATTERN.match(mpos_str)
            wpos_match = self.POSITION_PATTERN.match(wpos_str)
            
            if mpos_match and wpos_match:
                return {
                    'state': state,
                    'machine_position': [float(mpos_match.group(i)) for i in range(1, 4)],
                    'work_position': [float(wpos_match.group(i)) for i in range(1, 4)]
                }
        except (ValueError, AttributeError):
            pass
            
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
