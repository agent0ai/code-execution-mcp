"""Minimal log placeholder for MCP code execution tool."""
from dataclasses import dataclass
from typing import Optional, Any

@dataclass
class LogItem:
    """Placeholder for log items - all methods are no-ops."""
    type: str = ""
    heading: str = ""
    content: str = ""
    kvps: dict = None

    def update(self, **kwargs):
        """No-op update method."""
        pass

class Log:
    """Placeholder log class - all methods are no-ops."""

    def __init__(self, agent=None):
        self.agent = agent
        self.items = []

    def log(self, type: str = "", heading: str = "", content: str = "", kvps: dict = None) -> LogItem:
        """Create a no-op log item."""
        item = LogItem(type=type, heading=heading, content=content, kvps=kvps or {})
        return item

    def update(self, item: Optional[LogItem] = None, **kwargs):
        """No-op update method."""
        pass

    def item(self, type: str = "", heading: str = "") -> Optional[LogItem]:
        """Return None - no items stored."""
        return None

    def reset(self):
        """No-op reset method."""
        pass
