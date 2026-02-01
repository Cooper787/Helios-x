"""Message Bus

Handles inter-component communication within the Helios system.
"""

import logging
from typing import Dict, List, Callable, Any
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)


class MessageBus:
    """Asynchronous message bus for inter-component communication."""

    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = {}
        self.message_history: List[Dict[str, Any]] = []
        logger.info("MessageBus initialized")

    def subscribe(self, topic: str, callback: Callable) -> bool:
        """Subscribe to a specific topic."""
        try:
            if topic not in self.subscribers:
                self.subscribers[topic] = []
            self.subscribers[topic].append(callback)
            logger.info(f"Subscribed to topic: {topic}")
            return True
        except Exception as e:
            logger.error(f"Failed to subscribe to topic {topic}: {e}")
            return False

    def unsubscribe(self, topic: str, callback: Callable) -> bool:
        """Unsubscribe from a specific topic."""
        try:
            if topic in self.subscribers and callback in self.subscribers[topic]:
                self.subscribers[topic].remove(callback)
                logger.info(f"Unsubscribed from topic: {topic}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to unsubscribe from topic {topic}: {e}")
            return False

    async def publish(self, topic: str, message: Dict[str, Any]) -> bool:
        """Publish a message to a specific topic."""
        try:
            message["timestamp"] = datetime.now().isoformat()
            message["topic"] = topic
            self.message_history.append(message)

            if topic in self.subscribers:
                for callback in self.subscribers[topic]:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(message)
                        else:
                            callback(message)
                    except Exception as e:
                        logger.error(f"Error in callback for topic {topic}: {e}")

            logger.info(f"Published message to topic: {topic}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish message to topic {topic}: {e}")
            return False

    def get_history(self, topic: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve message history, optionally filtered by topic."""
        if topic:
            history = [msg for msg in self.message_history if msg.get("topic") == topic]
        else:
            history = self.message_history
        return history[-limit:]
