import os
import subprocess
from enum import Enum
from datetime import datetime
import json
from typing import Any
from dotenv import dotenv_values

import traffic

DEBUG = False
SCRIPT_DIR = '/etc/dijiq/core/scripts'
CONFIG_FILE = '/etc/dijiq/config.json'
CONFIG_ENV_FILE = '/etc/dijiq/.configs.env'


class Command(Enum):
    '''Contains path to command's script'''
    GET_USER = os.path.join(SCRIPT_DIR, 'dijiq', 'get_user.sh')
    ADD_USER = os.path.join(SCRIPT_DIR, 'dijiq', 'add_user.sh')
    EDIT_USER = os.path.join(SCRIPT_DIR, 'dijiq', 'edit_user.sh')
    RESET_USER = os.path.join(SCRIPT_DIR, 'dijiq', 'reset_user.sh')
    REMOVE_USER = os.path.join(SCRIPT_DIR, 'dijiq', 'remove_user.sh')
    SHOW_USER_URI = os.path.join(SCRIPT_DIR, 'dijiq', 'show_user_uri.sh')
    IP_ADD = os.path.join(SCRIPT_DIR, 'dijiq', 'ip.sh')
    UPDATE_GEO = os.path.join(SCRIPT_DIR, 'dijiq', 'update_geo.py')
    LIST_USERS = os.path.join(SCRIPT_DIR, 'dijiq', 'list_users.sh')
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

# region User


def list_users() -> dict[str, dict[str, Any]] | None:
    '''
    Lists all users.
    '''
    if res := run_cmd(['bash', Command.LIST_USERS.value]):
        return json.loads(res)


def get_user(username: str) -> dict[str, Any] | None:
    '''
    Retrieves information about a specific user.
    '''
    if res := run_cmd(['bash', Command.GET_USER.value, '-u', str(username)]):
        return json.loads(res)


def add_user(username: str, traffic_limit: int, expiration_days: int, password: str | None, creation_date: str | None):
    '''
    Adds a new user with the given parameters.
    '''
    if not password:
        password = generate_password()
    if not creation_date:
        creation_date = datetime.now().strftime('%Y-%m-%d')
    run_cmd(['bash', Command.ADD_USER.value, username, str(traffic_limit), str(expiration_days), password, creation_date])


def edit_user(username: str, new_username: str | None, new_traffic_limit: int | None, new_expiration_days: int | None, renew_password: bool, renew_creation_date: bool, blocked: bool):
    '''
    Edits an existing user's details.
    '''
    if not username:
        raise InvalidInputError('Error: username is required')
    if not any([new_username, new_traffic_limit, new_expiration_days, renew_password, renew_creation_date, blocked is not None]):  # type: ignore
        raise InvalidInputError('Error: at least one option is required')
    if new_traffic_limit is not None and new_traffic_limit <= 0:
        raise InvalidInputError('Error: traffic limit must be greater than 0')
    if new_expiration_days is not None and new_expiration_days <= 0:
        raise InvalidInputError('Error: expiration days must be greater than 0')
    if renew_password:
        password = generate_password()
    else:
        password = ''
    if renew_creation_date:
        creation_date = datetime.now().strftime('%Y-%m-%d')
    else:
        creation_date = ''
    command_args = [
        'bash',
        Command.EDIT_USER.value,
        username,
        new_username or '',
        str(new_traffic_limit) if new_traffic_limit is not None else '',
        str(new_expiration_days) if new_expiration_days is not None else '',
        password,
        creation_date,
        'true' if blocked else 'false'
    ]
    run_cmd(command_args)


def reset_user(username: str):
    '''
    Resets a user's configuration.
    '''
    run_cmd(['bash', Command.RESET_USER.value, username])


def remove_user(username: str):
    '''
    Removes a user by username.
    '''
    run_cmd(['bash', Command.REMOVE_USER.value, username])


# TODO: it's better to return json
def show_user_uri(username: str, qrcode: bool, ipv: int, all: bool, singbox: bool, normalsub: bool) -> str | None:
    '''
    Displays the URI for a user, with options for QR code and other formats.
    '''
    command_args = ['bash', Command.SHOW_USER_URI.value, '-u', username]
    if qrcode:
        command_args.append('-qr')
    if all:
        command_args.append('-a')
    else:
        command_args.extend(['-ip', str(ipv)])
    if singbox:
        command_args.append('-s')
    if normalsub:
        command_args.append('-n')
    return run_cmd(command_args)

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


def start_telegram_bot(token: str, adminid: str):
    '''Starts the Telegram bot.'''
    if not token or not adminid:
        raise InvalidInputError('Error: Both --token and --adminid are required for the start action.')
    run_cmd(['bash', Command.INSTALL_TELEGRAMBOT.value, 'start', token, adminid])


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
