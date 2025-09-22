"""
Global Logging Service with Decorator Support
"""
import threading
from functools import wraps
from typing import Callable, Optional, Any
from datetime import datetime
import inspect


class LogLevel:
    DEBUG = 'DEBUG'
    INFO = 'INFO'
    WARNING = 'WARNING'
    ERROR = 'ERROR'


class Logger:
    """Global logger service"""
    
    _instance: Optional['Logger'] = None
    _lock = threading.Lock()
    
    def __init__(self):
        self._enabled = True
        self._level = LogLevel.INFO
        self._output_handler: Optional[Callable[[str], None]] = None
        
    @classmethod
    def get_instance(cls) -> 'Logger':
        """Get singleton logger instance"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = Logger()
        return cls._instance
    
    def set_output_handler(self, handler: Callable[[str], None]):
        """Set custom output handler (e.g., GUI logger)"""
        self._output_handler = handler
    
    def set_level(self, level: str):
        """Set minimum log level"""
        self._level = level
    
    def log(self, message: str, level: str = LogLevel.INFO, component: str = None):
        """Log a message"""
        if not self._enabled:
            return
            
        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        component_str = f'[{component}]' if component else ''
        formatted_msg = f'{timestamp} {level} {component_str} {message}'
        
        if self._output_handler:
            self._output_handler(formatted_msg)
        else:
            print(formatted_msg)
    
    def debug(self, message: str, component: str = None):
        self.log(message, LogLevel.DEBUG, component)
    
    def info(self, message: str, component: str = None):
        self.log(message, LogLevel.INFO, component)
    
    def warning(self, message: str, component: str = None):
        self.log(message, LogLevel.WARNING, component)
    
    def error(self, message: str, component: str = None):
        self.log(message, LogLevel.ERROR, component)


# Global logger instance
logger = Logger.get_instance()


def logged(level: str = LogLevel.INFO, log_args: bool = False, log_result: bool = False):
    """
    Decorator to automatically log method calls
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get class name if method
            instance = args[0] if args and hasattr(args[0], '__class__') else None
            component = instance.__class__.__name__ if instance else func.__module__
            
            # Build log message
            func_name = func.__name__
            msg_parts = [f'{func_name}()']
            
            if log_args and (args[1:] or kwargs):  # Skip 'self' argument
                args_str = ', '.join(str(arg) for arg in args[1:])
                kwargs_str = ', '.join(f'{k}={v}' for k, v in kwargs.items())
                params = ', '.join(filter(None, [args_str, kwargs_str]))
                msg_parts = [f'{func_name}({params})']
            
            logger.log(' '.join(msg_parts), level, component)
            
            try:
                result = func(*args, **kwargs)
                
                if log_result:
                    logger.log(f'{func_name}() -> {result}', level, component)
                
                return result
                
            except Exception as e:
                logger.error(f'{func_name}() failed: {e}', component)
                raise
                
        return wrapper
    return decorator


def log_aware(component_name: str = None):
    """
    Class decorator that adds logging methods to a class
    """
    def decorator(cls):
        # Store original __init__
        original_init = cls.__init__
        
        @wraps(original_init)
        def new_init(self, *args, **kwargs):
            self._component_name = component_name or cls.__name__
            original_init(self, *args, **kwargs)
        
        # Replace __init__
        cls.__init__ = new_init
        
        # Add logging methods
        def log(self, message: str, level: str = LogLevel.INFO):
            logger.log(message, level, self._component_name)
        
        def debug(self, message: str):
            logger.debug(message, self._component_name)
        
        def info(self, message: str):
            logger.info(message, self._component_name)
        
        def warning(self, message: str):
            logger.warning(message, self._component_name)
        
        def error(self, message: str):
            logger.error(message, self._component_name)
        
        # Add methods to class
        cls.log = log
        cls.debug = debug
        cls.info = info
        cls.warning = warning
        cls.error = error
        
        return cls
    return decorator
