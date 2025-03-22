import os
from typing import Dict, Any, List
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def load_config() -> Dict[str, Any]:
    """
    Load configuration from environment variables.
    
    Returns:
        Dictionary with configuration values
        
    Raises:
        EnvironmentError: If required environment variables are not set
    """
    telegram_token = os.environ.get('TELEGRAM_TOKEN')
    vpn_api_url = os.environ.get('VPN_API_URL')
    admin_users_str = os.environ.get('ADMIN_USERS')
    api_key = os.environ.get('API_KEY')
    
    # Check if all required environment variables are set
    if not telegram_token:
        raise EnvironmentError("TELEGRAM_TOKEN environment variable is not set")
    
    if not vpn_api_url:
        raise EnvironmentError("VPN_API_URL environment variable is not set")
    
    if not admin_users_str:
        raise EnvironmentError("ADMIN_USERS environment variable is not set")
    
    # Parse admin users from comma-separated string to list of integers
    try:
        admin_users = [int(id.strip()) for id in admin_users_str.split(',')]
    except ValueError:
        raise EnvironmentError("ADMIN_USERS must be a comma-separated list of numeric Telegram user IDs")
    
    return {
        "telegram_token": telegram_token,
        "vpn_api_url": vpn_api_url,
        "admin_users": admin_users,
        "api_key": api_key  # Can be None if not set
    }


def is_admin(user_id: int) -> bool:
    """Check if a user ID is in the admin list."""
    try:
        config = load_config()
        admin_users: List[int] = config.get('admin_users', [])
        return user_id in admin_users
    except Exception:
        return False
