import urllib.parse
from typing import Dict, Any

def generate_hy2_config(username: str, password: str, config: Dict[str, Any]) -> str:
    """
    Generate a Hysteria2 configuration string.
    
    Args:
        username: VPN username
        password: VPN password
        config: Dictionary containing VPN server configuration
        
    Returns:
        Hysteria2 configuration string
    """
    # URL encode the password to handle special characters
    encoded_password = urllib.parse.quote(password)
    
    # Get server parameters from config
    server = config.get('vpn_server', '')
    port = config.get('vpn_port', '')
    obfs_password = config.get('obfs_password', '')
    pin_sha256 = config.get('pin_sha256', '')
    insecure = config.get('insecure', '1')
    sni = config.get('sni', '')
    
    # Build the configuration string
    config_string = (
        f"hy2://{username}%3A{encoded_password}@{server}:{port}"
        f"?obfs=salamander&obfs-password={obfs_password}"
        f"&pinSHA256={pin_sha256}&insecure={insecure}&sni={sni}"
        f"#{username}-IPv4"
    )
    
    return config_string
