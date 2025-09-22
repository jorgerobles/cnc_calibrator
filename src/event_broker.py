"""
EventBroker - Enhanced with class decorator for automatic injection
Eliminates the need to manually pass event_broker instances around
UPDATED: event_handler decorator now supports arrays of events
"""

import threading
from enum import Enum, auto
from functools import wraps
from typing import Callable, Dict, List, Any, Optional, Type, Union


class EventPriority(Enum):
    """Event priority levels"""
    LOW = auto()
    NORMAL = auto()
    HIGH = auto()
    CRITICAL = auto()


class EventBroker:
    """
    General-purpose event broker for managing publish-subscribe patterns
    Supports typed events, priorities, and error handling
    """

    # Global registry for event brokers
    _instances: Dict[str, 'EventBroker'] = {}
    _default_broker: Optional['EventBroker'] = None

    def __init__(self, name: str = "default", enable_logging: bool = False):
        self.name = name
        self._subscribers: Dict[str, List[Dict[str, Any]]] = {}
        self._lock = threading.RLock()
        self._enable_logging = enable_logging
        self._logger: Optional[Callable[[str, str], None]] = None

        # Register this broker
        EventBroker._instances[name] = self
        if name == "default":
            EventBroker._default_broker = self

    @classmethod
    def get_broker(cls, name: str = "default") -> 'EventBroker':
        """Get or create a named event broker"""
        if name not in cls._instances:
            cls._instances[name] = EventBroker(name)
        return cls._instances[name]

    @classmethod
    def get_default(cls) -> 'EventBroker':
        """Get the default event broker"""
        if cls._default_broker is None:
            cls._default_broker = EventBroker("default")
        return cls._default_broker

    def set_logger(self, logger: Callable[[str, str], None]):
        """Set logger function for debugging"""
        self._logger = logger

    def _log(self, message: str, level: str = "info"):
        """Internal logging"""
        return
        # if self._enable_logging and self._logger:
        #     self._logger(f"EventBroker[{self.name}]: {message}", level)

    def subscribe(self, event_type: str, callback: Callable,
                  priority: EventPriority = EventPriority.NORMAL,
                  error_handler: Optional[Callable[[Exception], None]] = None) -> str:
        """Subscribe to an event"""
        import uuid
        subscription_id = str(uuid.uuid4())

        subscriber = {
            'id': subscription_id,
            'callback': callback,
            'priority': priority,
            'error_handler': error_handler
        }

        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []

            # Insert based on priority
            self._subscribers[event_type].append(subscriber)
            self._subscribers[event_type].sort(key=lambda x: x['priority'].value, reverse=True)

        self._log(f"Subscribed to '{event_type}' with priority {priority.name}")
        return subscription_id

    def unsubscribe(self, event_type: str, subscription_id: str = None, callback: Callable = None) -> bool:
        """Unsubscribe from an event"""
        with self._lock:
            if event_type not in self._subscribers:
                return False

            original_count = len(self._subscribers[event_type])

            if subscription_id:
                self._subscribers[event_type] = [
                    s for s in self._subscribers[event_type] if s['id'] != subscription_id
                ]
            elif callback:
                self._subscribers[event_type] = [
                    s for s in self._subscribers[event_type] if s['callback'] != callback
                ]

            success = len(self._subscribers[event_type]) < original_count
            if success:
                self._log(f"Unsubscribed from '{event_type}'")

            return success

    def publish(self, event_type: str, *args, **kwargs) -> int:
        """Publish an event to all subscribers"""
        with self._lock:
            if event_type not in self._subscribers:
                self._log(f"No subscribers for event '{event_type}'")
                return 0

            subscribers = self._subscribers[event_type].copy()

        successful_calls = 0
        self._log(f"Publishing '{event_type}' to {len(subscribers)} subscribers")

        for subscriber in subscribers:
            try:
                subscriber['callback'](*args, **kwargs)
                successful_calls += 1
            except Exception as e:
                error_msg = f"Error in subscriber for '{event_type}': {e}"
                self._log(error_msg, "error")

                if subscriber['error_handler']:
                    try:
                        subscriber['error_handler'](e)
                    except Exception as handler_error:
                        self._log(f"Error in error handler: {handler_error}", "error")

        return successful_calls

    def has_subscribers(self, event_type: str) -> bool:
        """Check if event type has any subscribers"""
        with self._lock:
            return event_type in self._subscribers and len(self._subscribers[event_type]) > 0


def event_aware(broker_name: str = "default"):
    """
    Class decorator that automatically injects EventBroker functionality
    """

    def decorator(cls: Type) -> Type:
        # Store original __init__
        original_init = cls.__init__

        @wraps(original_init)
        def new_init(self, *args, **kwargs):
            # Get or create the named broker
            self._event_broker = EventBroker.get_broker(broker_name)
            self._subscriptions: List[tuple] = []

            # Call original __init__
            original_init(self, *args, **kwargs)

        # Replace __init__
        cls.__init__ = new_init

        # Add event methods to class
        def emit(self, event_type: str, *args, **kwargs) -> int:
            """Emit an event"""
            return self._event_broker.publish(event_type, *args, **kwargs)

        def listen(self, event_type: str, callback: Callable,
                   priority: EventPriority = EventPriority.NORMAL,
                   error_handler: Optional[Callable[[Exception], None]] = None) -> str:
            """Subscribe to an event and track the subscription"""
            subscription_id = self._event_broker.subscribe(
                event_type, callback, priority, error_handler
            )
            self._subscriptions.append((event_type, subscription_id))
            return subscription_id

        def stop_listening(self, event_type: str, subscription_id: str = None, callback: Callable = None) -> bool:
            """Unsubscribe from an event"""
            success = self._event_broker.unsubscribe(event_type, subscription_id, callback)
            if success:
                self._subscriptions = [
                    (et, sid) for et, sid in self._subscriptions
                    if not (et == event_type and (sid == subscription_id or callback))
                ]
            return success

        # Add methods to class
        cls.emit = emit
        cls.listen = listen
        cls.stop_listening = stop_listening

        return cls

    return decorator


def event_handler(event_types: Union[str, List[str]], priority: EventPriority = EventPriority.NORMAL):
    """
    Method decorator for automatic event subscription
    """
    # Normalize to list
    if isinstance(event_types, str):
        event_types = [event_types]

    def decorator(func: Callable) -> Callable:
        # Store event types on the function for auto-registration
        func._event_types = event_types
        func._event_priority = priority
        
        # Keep backward compatibility: set _event_type to first event
        func._event_type = func._event_types[0]

        return func

    return decorator
