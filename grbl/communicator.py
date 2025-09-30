"""
GRBL Communicator - Handles async request/response with queues
"""
import threading
import time
import queue
from concurrent.futures import Future
from typing import List, Optional, Callable
from .serial import SerialConnection
from .parser import GRBLResponseParser


class GRBLCommunicator:
    """Manages GRBL communication with async response handling"""
    
    def __init__(self, serial_conn: SerialConnection, parser: GRBLResponseParser):
        self._serial = serial_conn
        self._parser = parser
        
        # Threading
        self._reader_thread: Optional[threading.Thread] = None
        self._running = False
        
        # Queues for async handling
        self._response_queue = queue.Queue()
        self._pending_commands = {}  # command_id -> Future
        self._command_counter = 0
        
        # Callbacks for async messages
        self._status_callback: Optional[Callable] = None
        self._async_callback: Optional[Callable] = None
        
    def start(self) -> None:
        """Start async response reader thread"""
        if self._running:
            return
            
        self._running = True
        self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader_thread.start()
    
    def stop(self) -> None:
        """Stop async response reader"""
        self._running = False
        
        # Cancel all pending commands
        for cmd_info in self._pending_commands.values():
            if not cmd_info['future'].done():
                cmd_info['future'].set_exception(ConnectionError("Communicator stopped"))
        self._pending_commands.clear()
        
        if self._reader_thread:
            self._reader_thread.join(timeout=1.0)
            self._reader_thread = None
    
    def send_command_sync(self, command: str, timeout: float = 5.0) -> List[str]:
        """Send command synchronously and wait for response"""
        future = self.send_command_async(command, timeout)
        try:
            return future.result(timeout=timeout)
        except TimeoutError as e:
            # Timeout already handled by reader loop
            raise
    
    def send_command_async(self, command: str, timeout: float = 5.0) -> Future:
        """Send command asynchronously"""
        if not self._serial.is_open():
            raise ConnectionError("Serial not connected")
        
        future = Future()
        command_id = self._get_next_command_id()
        
        # Track the command
        self._pending_commands[command_id] = {
            'future': future,
            'timeout': time.time() + timeout,
            'command': command
        }
        
        try:
            # Send command without ID injection to avoid interfering with GRBL
            self._serial.write(f"{command}\n".encode())
            return future
        except Exception as e:
            if command_id in self._pending_commands:
                del self._pending_commands[command_id]
            future.set_exception(e)
            return future
    
    def send_realtime_command(self, command: str) -> None:
        """Send realtime command (no response expected)"""
        if not self._serial.is_open():
            raise ConnectionError("Serial not connected")
        self._serial.write(command.encode())
    
    def query_status(self, timeout: float = 2.0) -> Optional[dict]:
        """Query status with realtime command and wait for status response"""
        if not self._serial.is_open():
            raise ConnectionError("Serial not connected")
        
        # Use threading event for efficient waiting
        status_event = threading.Event()
        status_data_holder = {'data': None}
        
        def status_handler(status_data):
            status_data_holder['data'] = status_data
            status_event.set()
        
        # Temporarily override status callback
        old_callback = self._status_callback
        self._status_callback = status_handler
        
        try:
            # Send realtime status query (no newline, no command ID)
            self._serial.write(b'?')
            
            # Wait efficiently for status response - returns immediately when set
            if status_event.wait(timeout=timeout):
                return status_data_holder['data']
            
            return None
        finally:
            # Restore original callback
            self._status_callback = old_callback
    
    def set_status_callback(self, callback: Callable) -> None:
        """Set callback for status updates"""
        self._status_callback = callback
    
    def set_async_callback(self, callback: Callable) -> None:
        """Set callback for async messages"""
        self._async_callback = callback
    
    def _reader_loop(self) -> None:
        """Main reader loop - processes all incoming data with minimal latency"""
        responses_buffer = []
        last_timeout_check = time.time()
        
        while self._running and self._serial.is_open():
            try:
                # Check if data is available before blocking read
                if self._serial.in_waiting() > 0:
                    # Data available - read immediately with short timeout
                    line = self._serial.read_line(timeout=0.05)
                    
                    if line:
                        # Process data immediately when it arrives
                        if self._parser.is_ok_response(line):
                            self._handle_command_completion(responses_buffer + [line])
                            responses_buffer.clear()
                            
                        elif self._parser.is_error_response(line):
                            self._handle_command_completion(responses_buffer + [line])
                            responses_buffer.clear()
                            
                        elif line.startswith('<') and line.endswith('>'):
                            # Status response - handle immediately
                            if self._status_callback:
                                status_data = self._parser.parse_status_response(line)
                                if status_data:
                                    self._status_callback(status_data)
                                    
                        elif self._parser.is_async_message(line):
                            # Async message - handle immediately  
                            if self._async_callback:
                                self._async_callback(line)
                                
                        else:
                            # Regular response - buffer until completion
                            responses_buffer.append(line)
                else:
                    # No data available - small sleep to prevent CPU spinning
                    time.sleep(0.001)  # 1ms
                    
                    # Check timeouts periodically (every 100ms)
                    current_time = time.time()
                    if current_time - last_timeout_check >= 0.1:
                        self._check_timeouts()
                        last_timeout_check = current_time
                    
            except Exception as e:
                if self._running:
                    print(f"Reader error: {e}")
                break
    
    def _check_timeouts(self) -> None:
        """Check for and handle timed out commands"""
        if not self._pending_commands:
            return
            
        current_time = time.time()
        timed_out = []
        
        for cmd_id, cmd_info in self._pending_commands.items():
            if current_time > cmd_info['timeout'] and not cmd_info['future'].done():
                timed_out.append(cmd_id)
        
        for cmd_id in timed_out:
            cmd_info = self._pending_commands.pop(cmd_id, None)
            if cmd_info and not cmd_info['future'].done():
                cmd_info['future'].set_exception(
                    TimeoutError(f"Command timeout: {cmd_info['command']}")
                )
    
    def _handle_command_completion(self, responses: List[str]) -> None:
        """Handle completed command responses"""
        if not self._pending_commands:
            return
            
        # Complete the oldest pending command (FIFO)
        command_id = min(self._pending_commands.keys())
        cmd_info = self._pending_commands.pop(command_id)
        
        if not cmd_info['future'].done():
            cmd_info['future'].set_result(responses)
    
    def _get_next_command_id(self) -> int:
        """Get next command ID"""
        self._command_counter += 1
        return self._command_counter
