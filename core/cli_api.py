import os
import subprocess
from enum import Enum
from datetime import datetime
import json
from typing import Any
from dotenv import dotenv_values

DEBUG = False
SCRIPT_DIR = '/etc/dijiq/core/scripts'
CONFIG_ENV_FILE = '/etc/dijiq/.configs.env'


class Command(Enum):
    '''Contains path to command's script'''
    IP_ADD = os.path.join(SCRIPT_DIR, 'dijiq', 'ip.sh')
    SERVER_INFO = os.path.join(SCRIPT_DIR, 'dijiq', 'server_info.sh')
    BACKUP_DIJIQ = os.path.join(SCRIPT_DIR, 'dijiq', 'backup.sh')
    RESTORE_DIJIQ = os.path.join(SCRIPT_DIR, 'dijiq', 'restore.sh')
    INSTALL_TELEGRAMBOT = os.path.join(SCRIPT_DIR, 'telegrambot', 'runbot.sh')
    SERVICES_STATUS = os.path.join(SCRIPT_DIR, 'services_status.sh')
    VERSION = os.path.join(SCRIPT_DIR, 'dijiq', 'version.py')

# region Custom Exceptions


class dijiqError(Exception):
    '''Base class for dijiq-related exceptions.'''
    pass


class CommandExecutionError(dijiqError):
    '''Raised when a command execution fails.'''
    pass


class InvalidInputError(dijiqError):
    '''Raised when the provided input is invalid.'''
    pass


class PasswordGenerationError(dijiqError):
    '''Raised when password generation fails.'''
    pass


class ScriptNotFoundError(dijiqError):
    '''Raised when a required script is not found.'''
    pass

# region Utils


def run_cmd(command: list[str]) -> str | None:
    '''
    Runs a command and returns the output.
    Could raise subprocess.CalledProcessError
    '''
    if (DEBUG) and not (Command.GET_USER.value in command or Command.LIST_USERS.value in command):
        print(' '.join(command))
    try:
        result = subprocess.check_output(command, stderr=subprocess.STDOUT, shell=False)
        if result:
            result = result.decode().strip()
            return result
    except subprocess.CalledProcessError as e:
        if DEBUG:
            raise CommandExecutionError(f'Command execution failed: {e}\nOutput: {e.output.decode()}')
        else:
            return None
    return None


def generate_password() -> str:
    '''
    Generates a random password using pwgen for user.
    Could raise subprocess.CalledProcessError
    '''
    try:
        return subprocess.check_output(['pwgen', '-s', '32', '1'], shell=False).decode().strip()
    except subprocess.CalledProcessError as e:
        raise PasswordGenerationError(f'Failed to generate password: {e}')

# endregion

# region APIs

# region dijiq


def backup_dijiq():
    '''Backups dijiq configuration.  Raises an exception on failure.'''
    try:
        run_cmd(['bash', Command.BACKUP_DIJIQ.value])
    except subprocess.CalledProcessError as e:
        raise Exception(f"Backup failed: {e}")
    except Exception as ex:
        raise


def restore_dijiq(backup_file_path: str):
    '''Restores dijiq configuration from the given backup file.'''
    try:
        run_cmd(['bash', Command.RESTORE_DIJIQ.value, backup_file_path])
    except subprocess.CalledProcessError as e:
        raise Exception(f"Restore failed: {e}")
    except Exception as ex:
        raise


def get_dijiq_config_file() -> dict[str, Any]:
    with open(CONFIG_FILE, 'r') as f:
        return json.loads(f.read())


def set_dijiq_config_file(data: dict[str, Any]):
    content = json.dumps(data, indent=4)

    with open(CONFIG_FILE, 'w') as f:
        f.write(content)
# endregion

# region Server


def traffic_status():
    '''Fetches traffic status.'''
    traffic.traffic_status()


# TODO: it's better to return json
def server_info() -> str | None:
    '''Retrieves server information.'''
    return run_cmd(['bash', Command.SERVER_INFO.value])


def get_ip_address() -> tuple[str | None, str | None]:
    '''
    Retrieves the IP address from the .configs.env file.
    '''
    env_vars = dotenv_values(CONFIG_ENV_FILE)

    return env_vars.get('IP4'), env_vars.get('IP6')


def add_ip_address():
    '''
    Adds IP addresses from the environment to the .configs.env file.
    '''
    run_cmd(['bash', Command.IP_ADD.value, 'add'])


def edit_ip_address(ipv4: str, ipv6: str):
    '''
    Edits the IP address configuration based on provided IPv4 and/or IPv6 addresses.

    :param ipv4: The new IPv4 address to be configured. If provided, the IPv4 address will be updated.
    :param ipv6: The new IPv6 address to be configured. If provided, the IPv6 address will be updated.
    :raises InvalidInputError: If neither ipv4 nor ipv6 is provided.
    '''

    if not ipv4 and not ipv6:
        raise InvalidInputError('Error: --edit requires at least one of --ipv4 or --ipv6.')
    if ipv4:
        run_cmd(['bash', Command.IP_ADD.value, 'edit', '-4', ipv4])
    if ipv6:
        run_cmd(['bash', Command.IP_ADD.value, 'edit', '-6', ipv6])


# endregion

# region Advanced Menu


def start_telegram_bot(token: str, adminid: str, api_url: str, api_key: str, sub_url: str):
    '''Starts the Telegram bot.'''
    if not token or not adminid or not api_url or not api_key or not sub_url:
        raise InvalidInputError('Error: All parameters (token, adminid, api_url, api_key, sub_url) are required for the start action.')
    run_cmd(['bash', Command.INSTALL_TELEGRAMBOT.value, 'start', token, adminid, api_url, api_key, sub_url])


def stop_telegram_bot():
    '''Stops the Telegram bot.'''
    run_cmd(['bash', Command.INSTALL_TELEGRAMBOT.value, 'stop'])


def get_services_status() -> dict[str, bool] | None:
    '''Gets the status of all project services.'''
    if res := run_cmd(['bash', Command.SERVICES_STATUS.value]):
        return json.loads(res)

def show_version() -> str | None:
    """Displays the currently installed version of the panel."""
    return run_cmd(['python3', Command.VERSION.value, 'show-version'])


def check_version() -> str | None:
    """Checks if the current version is up-to-date and displays changelog if not."""
    return run_cmd(['python3', Command.VERSION.value, 'check-version'])
# endregion
