#!/usr/bin/env python3

import typing
import click
import cli_api
import json


def pretty_print(data: typing.Any):
    if isinstance(data, dict):
        print(json.dumps(data, indent=4))
        return

    print(data)


@click.group()
def cli():
    pass

# region dijiq


@cli.command('backup-dijiq')
def backup_dijiq():
    try:
        cli_api.backup_dijiq()
        click.echo('dijiq configuration backed up successfully.')
    except Exception as e:
        click.echo(f'{e}', err=True)

@cli.command('restore-dijiq')
@click.argument('backup_file_path', type=click.Path(exists=True, file_okay=True, dir_okay=False, readable=True))
def restore_dijiq(backup_file_path):
    """Restores dijiq configuration from a backup ZIP file."""
    try:
        cli_api.restore_dijiq(backup_file_path)
        click.echo('dijiq configuration restored successfully.')
    except Exception as e:
        click.echo(f'{e}', err=True)

# endregion

# region User


@cli.command('list-users')
def list_users():
    try:
        res = cli_api.list_users()
        if res:
            pretty_print(res)
        else:
            click.echo('No users found.')
    except Exception as e:
        click.echo(f'{e}', err=True)


@cli.command('get-user')
@click.option('--username', '-u', required=True, help='Username for the user to get', type=str)
def get_user(username: str):
    try:
        if res := cli_api.get_user(username):
            pretty_print(res)
    except Exception as e:
        click.echo(f'{e}', err=True)


@cli.command('add-user')
@click.option('--username', '-u', required=True, help='Username for the new user', type=str)
@click.option('--traffic-limit', '-t', required=True, help='Traffic limit for the new user in GB', type=int)
@click.option('--expiration-days', '-e', required=True, help='Expiration days for the new user', type=int)
@click.option('--password', '-p', required=False, help='Password for the user', type=str)
@click.option('--creation-date', '-c', required=False, help='Creation date for the user (YYYY-MM-DD)', type=str)
def add_user(username: str, traffic_limit: int, expiration_days: int, password: str, creation_date: str):
    try:
        cli_api.add_user(username, traffic_limit, expiration_days, password, creation_date)
        click.echo(f"User '{username}' added successfully.")
    except Exception as e:
        click.echo(f'{e}', err=True)


@cli.command('edit-user')
@click.option('--username', '-u', required=True, help='Username for the user to edit', type=str)
@click.option('--new-username', '-nu', required=False, help='New username for the user', type=str)
@click.option('--new-traffic-limit', '-nt', required=False, help='Traffic limit for the new user in GB', type=int)
@click.option('--new-expiration-days', '-ne', required=False, help='Expiration days for the new user', type=int)
@click.option('--renew-password', '-rp', is_flag=True, help='Renew password for the user')
@click.option('--renew-creation-date', '-rc', is_flag=True, help='Renew creation date for the user')
@click.option('--blocked', '-b', is_flag=True, help='Block the user')
def edit_user(username: str, new_username: str, new_traffic_limit: int, new_expiration_days: int, renew_password: bool, renew_creation_date: bool, blocked: bool):
    try:
        cli_api.edit_user(username, new_username, new_traffic_limit, new_expiration_days,
                          renew_password, renew_creation_date, blocked)
        click.echo(f"User '{username}' updated successfully.")
    except Exception as e:
        click.echo(f'{e}', err=True)


@cli.command('reset-user')
@click.option('--username', '-u', required=True, help='Username for the user to Reset', type=str)
def reset_user(username: str):
    try:
        cli_api.reset_user(username)
        click.echo(f"User '{username}' reset successfully.")
    except Exception as e:
        click.echo(f'{e}', err=True)


@cli.command('remove-user')
@click.option('--username', '-u', required=True, help='Username for the user to remove', type=str)
def remove_user(username: str):
    try:
        cli_api.remove_user(username)
        click.echo(f"User '{username}' removed successfully.")
    except Exception as e:
        click.echo(f'{e}', err=True)


@cli.command('show-user-uri')
@click.option('--username', '-u', required=True, help='Username for the user to show the URI', type=str)
@click.option('--qrcode', '-qr', is_flag=True, help='Generate QR code for the URI')
@click.option('--ipv', '-ip', type=click.IntRange(4, 6), default=4, help='IP version (4 or 6)')
@click.option('--all', '-a', is_flag=True, help='Show both IPv4 and IPv6 URIs and generate QR codes for both if requested')
@click.option('--singbox', '-s', is_flag=True, help='Generate Singbox sublink if Singbox service is active')
@click.option('--normalsub', '-n', is_flag=True, help='Generate Normal sublink if normalsub service is active')
def show_user_uri(username: str, qrcode: bool, ipv: int, all: bool, singbox: bool, normalsub: bool):
    try:
        res = cli_api.show_user_uri(username, qrcode, ipv, all, singbox, normalsub)
        if res:
            click.echo(res)
        else:
            click.echo(f"URI for user '{username}' could not be generated.")
    except Exception as e:
        click.echo(f'{e}', err=True)
# endregion

# region Server


@cli.command('server-info')
def server_info():
    try:
        res = cli_api.server_info()
        if res:
            pretty_print(res)
        else:
            click.echo('Server information not available.')
    except Exception as e:
        click.echo(f'{e}', err=True)


@cli.command('ip-address')
@click.option('--edit', is_flag=True, help='Edit IP addresses manually.')
@click.option('-4', '--ipv4', type=str, help='Specify the new IPv4 address.')
@click.option('-6', '--ipv6', type=str, help='Specify the new IPv6 address.')
def ip_address(edit: bool, ipv4: str, ipv6: str):
    '''
    Manage IP addresses in .configs.env.
    - Use without options to add auto-detected IPs.
    - Use --edit with -4 or -6 to manually update IPs.
    '''
    try:
        if not edit:
            cli_api.add_ip_address()
            click.echo('IP addresses added successfully.')
            return

        if not ipv4 and not ipv6:
            raise click.UsageError('Error: You must specify either -4 or -6')

        cli_api.edit_ip_address(ipv4, ipv6)
        click.echo('IP address configuration updated successfully.')
    except Exception as e:
        click.echo(f'{e}', err=True)

# endregion

# region Advanced Menu


@cli.command('telegram')
@click.option('--action', '-a', required=True, help='Action to perform: start or stop', type=click.Choice(['start', 'stop'], case_sensitive=False))
@click.option('--token', '-t', required=False, help='Token for running the telegram bot', type=str)
@click.option('--adminid', '-aid', required=False, help='Telegram admins ID for running the telegram bot', type=str)
@click.option('--api-url', '-url', required=False, help='URL for the API', type=str)
@click.option('--api-key', '-key', required=False, help='Authentication key for the API', type=str)
def telegram(action: str, token: str, adminid: str, api_url: str, api_key: str):
    try:
        if action == 'start':
            if not token or not adminid:
                raise click.UsageError('Error: Both --token and --adminid are required for the start action.')
            if not api_url or not api_key:
                raise click.UsageError('Error: Both --api-url and --api-key are required for the start action.')
            cli_api.start_telegram_bot(token, adminid, api_url, api_key)
            click.echo(f'Telegram bot started successfully.')
        elif action == 'stop':
            cli_api.stop_telegram_bot()
            click.echo(f'Telegram bot stopped successfully.')
    except Exception as e:
        click.echo(f'{e}', err=True)


@cli.command('get-services-status')
def get_services_status():
    try:
        if services_status := cli_api.get_services_status():
            for service, status in services_status.items():
                click.echo(f"{service}: {'Active' if status else 'Inactive'}")
        else:
            click.echo('Error: Services status not available.')
    except Exception as e:
        click.echo(f'{e}', err=True)


@cli.command('show-version')
def show_version():
    """Displays the currently installed version of the panel."""
    try:
        if version_info := cli_api.show_version():
             click.echo(version_info)
        else:
            click.echo("Error retrieving version")
    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}", err=True)


@cli.command('check-version')
def check_version():
    """Checks if the current version is up-to-date and displays changelog if not."""
    try:
        if version_info := cli_api.check_version():
            click.echo(version_info)
        else:
            click.echo("Error retrieving version")
    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}", err=True)

# endregion


if __name__ == '__main__':
    cli()
