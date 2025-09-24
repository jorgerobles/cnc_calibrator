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
        for future in self._pending_commands.values():
            if not future.done():
                future.set_exception(ConnectionError("Communicator stopped"))
        self._pending_commands.clear()
        
        if self._reader_thread:
            self._reader_thread.join(timeout=1.0)
            self._reader_thread = None
    
    def send_command_sync(self, command: str, timeout: float = 5.0) -> List[str]:
        """Send command synchronously and wait for response"""
        future = self.send_command_async(command, timeout)
        return future.result(timeout=timeout)
    
    def send_command_async(self, command: str, timeout: float = 5.0) -> Future:
        """Send command asynchronously"""
        if not self._serial.is_open():
            raise ConnectionError("Serial not connected")
        
        future = Future()
        command_id = self._get_next_command_id()
        
        # Track the command
        self._pending_commands[command_id] = future
        
        # Set timeout handling
        def timeout_handler():
            time.sleep(timeout)
            if command_id in self._pending_commands and not future.done():
                del self._pending_commands[command_id]
                future.set_exception(TimeoutError(f"Command timeout: {command}"))
        
        threading.Thread(target=timeout_handler, daemon=True).start()
        
        try:
            # Send command with ID for tracking
            cmd_with_id = f"{command} ; ({command_id})"
            self._serial.write(f"{cmd_with_id}\n".encode())
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
    
    def set_status_callback(self, callback: Callable) -> None:
        """Set callback for status updates"""
        self._status_callback = callback
    
    def set_async_callback(self, callback: Callable) -> None:
        """Set callback for async messages"""
        self._async_callback = callback
    
    def _reader_loop(self) -> None:
        """Main reader loop - processes all incoming data"""
        responses_buffer = []
        
        while self._running and self._serial.is_open():
            try:
                line = self._serial.read_line(timeout=0.1)
                if not line:
                    continue
                
                # Handle different response types
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
                    
            except Exception as e:
                if self._running:  # Only log if we're supposed to be running
                    print(f"Reader error: {e}")
                break
    
    def _handle_command_completion(self, responses: List[str]) -> None:
        """Handle completed command responses"""
        if not self._pending_commands:
            return
            
        # For simplicity, complete the oldest pending command
        # In production, you'd extract command ID from response
        command_id = min(self._pending_commands.keys())
        future = self._pending_commands.pop(command_id)
        
        if not future.done():
            future.set_result(responses)
    
    def _get_next_command_id(self) -> int:
        """Get next command ID"""
        self._command_counter += 1
        return self._command_counter
