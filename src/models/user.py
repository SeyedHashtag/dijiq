from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class VpnUser:
    username: str
    traffic_limit: int
    expiration_days: int
    password: str
    creation_date: Optional[str] = None
    
    def to_dict(self):
        """Convert the user object to a dictionary for API request."""
        return {
            "username": self.username,
            "traffic_limit": self.traffic_limit,
            "expiration_days": self.expiration_days,
            "password": self.password,
            "creation_date": self.creation_date or datetime.now().isoformat()
        }
