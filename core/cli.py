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

# region Server


@cli.command('server-info')
@click.option(
    '--section',
    type=click.Choice(['overview', 'business', 'customers', 'tech', 'traffic', 'alerts', 'full'], case_sensitive=False),
    default='full',
    show_default=True,
    help='Render a specific server info dashboard section.',
)
def server_info(section):
    try:
        res = cli_api.server_info(section=section)
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
@click.option('--api-url', '-u', required=False, help='API URL for the API client', type=str)
@click.option('--api-key', '-k', required=False, help='API key for the API client', type=str)
@click.option('--server', multiple=True, help='VPN server in id=url,token[,weight,enabled] format. Can be repeated.', type=str)
def telegram(action: str, token: str, adminid: str, api_url: str, api_key: str, server):
    try:
        if action == 'start':
            if not token or not adminid or ((not api_url or not api_key) and not server):
                raise click.UsageError('Error: --token and --adminid are required. Provide --api-url/--api-key or at least one --server.')
            cli_api.start_telegram_bot(token, adminid, api_url, api_key, servers=server)
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
