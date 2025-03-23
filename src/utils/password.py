import random
import string

def generate_random_password(length=32):
    """
    Generate a random password with the specified length.
    
    The password will contain a mix of uppercase letters, lowercase letters, and numbers.
    
    Args:
        length: The length of the password to generate (default: 32)
        
    Returns:
        A random password string
    """
    characters = string.ascii_uppercase + string.ascii_lowercase + string.digits
    return ''.join(random.choice(characters) for _ in range(length))
