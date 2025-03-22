import json
import os
from typing import Dict, Any, List


def load_config() -> Dict[str, Any]:
    """
    Load configuration from config.json file.
    
    Returns:
        Dictionary with configuration values
    """
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                              'config.json')
    
    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"Configuration file not found at {config_path}. "
            "Please copy config.example.json to config.json and update the values."
        )
    
    with open(config_path, 'r') as f:
        return json.load(f)


def is_admin(user_id: int) -> bool:
    """Check if a user ID is in the admin list."""
    try:
        config = load_config()
        admin_users: List[int] = config.get('admin_users', [])
        return user_id in admin_users
    except Exception:
        return False
