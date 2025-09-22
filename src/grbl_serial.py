"""
Serial Connection Implementation - Abstraction over pyserial
"""
import serial
import threading
import time
from typing import Optional


class SerialConnection:
    """Simple serial communication wrapper with thread safety"""
    
    def __init__(self):
        self._connection: Optional[serial.Serial] = None
        self._lock = threading.Lock()
    
    def open(self, port: str, baudrate: int, timeout: float = 1.0) -> bool:
        """Open serial connection"""
        try:
            with self._lock:
                if self._connection and self._connection.is_open:
                    self._connection.close()
                
                self._connection = serial.Serial(
                    port=port,
                    baudrate=baudrate,
                    timeout=timeout,
                    write_timeout=timeout,
                    bytesize=8,
                    parity='N',
                    stopbits=1
                )
                return self._connection.is_open
        except Exception:
            return False
    
    def close(self) -> None:
        """Close serial connection"""
        with self._lock:
            if self._connection:
                try:
                    self._connection.close()
                except:
                    pass
                finally:
                    self._connection = None
    
    def is_open(self) -> bool:
        """Check if connection is open"""
        with self._lock:
            return self._connection is not None and self._connection.is_open
    
    def write(self, data: bytes) -> int:
        """Write data to serial port"""
        with self._lock:
            if not self._connection or not self._connection.is_open:
                raise ConnectionError("Serial port not open")
            return self._connection.write(data)
    
    def read_line(self, timeout: Optional[float] = None) -> Optional[str]:
        """Read a line from serial port"""
        with self._lock:
            if not self._connection or not self._connection.is_open:
                return None
            
            old_timeout = self._connection.timeout
            if timeout is not None:
                self._connection.timeout = timeout
            
            try:
                line = self._connection.readline()
                if line:
                    return line.decode('utf-8', errors='ignore').strip()
                return None
            except:
                return None
            finally:
                self._connection.timeout = old_timeout
    
    def reset_input_buffer(self) -> None:
        """Clear input buffer"""
        with self._lock:
            if self._connection and self._connection.is_open:
                self._connection.reset_input_buffer()
    
    def in_waiting(self) -> int:
        """Number of bytes waiting to be read"""
        with self._lock:
            if self._connection and self._connection.is_open:
                return self._connection.in_waiting
            return 0
