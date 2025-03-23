import io
from typing import Optional
import urllib.parse
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Flag to track if QR generation is available
QR_AVAILABLE = False

try:
    import qrcode
    QR_AVAILABLE = True
except ImportError:
    # QR code generation will be disabled if dependencies are missing
    pass

def get_vpn_config_url(username: str, password: str) -> str:
    """
    Generate a VPN configuration URL in the Hysteria2 format.
    
    Args:
        username: The VPN username
        password: The VPN password
        
    Returns:
        The configuration URL string
    """
    # Get configuration from environment variables
    server = os.environ.get('VPN_SERVER', '')
    port = os.environ.get('VPN_PORT', '')
    obfs_password = os.environ.get('OBFS_PASSWORD', '')
    pin_sha256 = os.environ.get('PIN_SHA256', '')
    insecure = os.environ.get('INSECURE', '1')
    sni = os.environ.get('SNI', 'example.com')
    
    # Format the URL (password is already URL-encoded with %3A)
    config_url = (
        f"hy2://{username}%3A{password}@{server}:{port}?"
        f"obfs=salamander&obfs-password={obfs_password}&"
        f"pinSHA256={pin_sha256}&insecure={insecure}&sni={sni}#{username}-IPv4"
    )
    
    return config_url

def generate_qr_code(data: str) -> Optional[bytes]:
    """
    Generate a QR code image from the given data.
    
    Args:
        data: The data to encode in the QR code
        
    Returns:
        The QR code image as bytes, or None if generation fails
    """
    if not QR_AVAILABLE:
        return None
        
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert the image to bytes
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        
        return img_bytes.getvalue()
    except Exception as e:
        print(f"Error generating QR code: {e}")
        return None
