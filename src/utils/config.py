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
    
    # VPN configuration parameters
    vpn_server = os.environ.get('VPN_SERVER')
    vpn_port = os.environ.get('VPN_PORT')
    obfs_password = os.environ.get('OBFS_PASSWORD')
    pin_sha256 = os.environ.get('PIN_SHA256')
    insecure = os.environ.get('INSECURE', '1')  # Default to 1 (true) if not set
    sni = os.environ.get('SNI')
    
    # Add Cryptomus configurations
    cryptomus_merchant_id = os.environ.get('CRYPTOMUS_MERCHANT_ID')
    cryptomus_api_key = os.environ.get('CRYPTOMUS_API_KEY')
    webhook_secret = os.environ.get('WEBHOOK_SECRET')
    
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
        "api_key": api_key,  # Can be None if not set
        "vpn_server": vpn_server,
        "vpn_port": vpn_port,
        "obfs_password": obfs_password,
        "pin_sha256": pin_sha256,
        "insecure": insecure,
        "sni": sni,
        
        # Payment configuration
        "cryptomus_merchant_id": cryptomus_merchant_id,
        "cryptomus_api_key": cryptomus_api_key,
        "webhook_secret": webhook_secret,
        
        # VPN package information
        "vpn_package": {
            "name": "Standard VPN Package",
            "traffic_limit": 100,  # GB
            "expiration_days": 90,
            "price": 2.5,
            "currency": "USD"
        }
    }


def is_admin(user_id: int) -> bool:
    """Check if a user ID is in the admin list."""
    try:
        config = load_config()
        admin_users: List[int] = config.get('admin_users', [])
        return user_id in admin_users
    except Exception:
        return False
