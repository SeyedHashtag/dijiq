import os
import subprocess
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def get_version():
    """Get the current version of Dijiq."""
    try:
        version_file = Path(__file__).parent.parent.parent / 'VERSION'
        if version_file.exists():
            return version_file.read_text().strip()
        return "Unknown"
    except Exception as e:
        logger.error(f"Error reading version file: {e}")
        return "Unknown"

def check_for_updates():
    """Check if updates are available for Dijiq."""
    try:
        # Get the installation path
        install_dir = Path(__file__).parent.parent.parent
        
        # Run git fetch to get latest changes
        subprocess.run(
            ["git", "fetch", "origin", "--quiet"], 
            cwd=str(install_dir),
            check=True,
            capture_output=True
        )
        
        # Get current version
        current_version = get_version()
        
        # Get remote version
        remote_version = subprocess.run(
            ["git", "show", "origin/main:VERSION"],
            cwd=str(install_dir),
            check=True,
            capture_output=True,
            text=True
        ).stdout.strip()
        
        # Compare versions
        from packaging import version
        local_ver = version.parse(current_version)
        remote_ver = version.parse(remote_version)
        
        return {
            "update_available": remote_ver > local_ver,
            "current_version": current_version,
            "latest_version": remote_version
        }
    except Exception as e:
        logger.error(f"Error checking for updates: {e}")
        return {
            "update_available": False,
            "current_version": get_version(),
            "latest_version": "Unknown",
            "error": str(e)
        }
