from fastapi import APIRouter, HTTPException
import cli_api
from .schema.server import ServerStatusResponse, ServerServicesStatusResponse, VersionCheckResponse, VersionInfoResponse

router = APIRouter()


@router.get('/status', response_model=ServerStatusResponse)
async def server_status_api():
    """
    Retrieve the server status.

    This endpoint provides information about the current server status,
    including uptime, CPU usage, RAM usage, online users, and traffic statistics.

    Returns:
        ServerStatusResponse: A response model containing server status details.

    Raises:
        HTTPException: If the server information is not available (404) or
                       if there is an error processing the request (400).
    """

    try:
        if res := cli_api.server_info():
            return __parse_server_status(res)
        raise HTTPException(status_code=404, detail='Server information not available.')
    except Exception as e:
        raise HTTPException(status_code=400, detail=f'Error: {str(e)}')


def __parse_server_status(server_info: str) -> ServerStatusResponse:
    """
    Parse the server information provided by cli_api.server_info()
    and return a ServerStatusResponse instance.

    Args:
        server_info (str): The output of cli_api.server_info() as a string.

    Returns:
        ServerStatusResponse: A response model containing server status details.

    Raises:
        ValueError: If the server information is invalid or incomplete.
    """
    data = {
        'uptime': 'N/A',
        'boot_time': 'N/A',
        'cpu_usage': '0%',
        'total_ram': '0MB',
        'ram_usage': '0MB',
        'online_users': 0,
        'upload_speed': '0 B/s',
        'download_speed': '0 B/s',
        'tcp_connections': 0,
        'udp_connections': 0,
        'reboot_uploaded_traffic': '0 B',
        'reboot_downloaded_traffic': '0 B',
        'reboot_total_traffic': '0 B',
        'user_uploaded_traffic': '0 B',
        'user_downloaded_traffic': '0 B',
        'user_total_traffic': '0 B'
    }

    current_section = 'general'

    for line in server_info.splitlines():
        line = line.strip()
        if not line:
            continue

        if 'Traffic Since Last Reboot' in line:
            current_section = 'reboot'
            continue
        elif 'User Traffic (All Time)' in line:
            current_section = 'user'
            continue
            
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip()

        if not key or not value:
            continue
        
        try:
            if 'uptime' in key:
                uptime_part, _, boottime_part = value.partition('(')
                data['uptime'] = uptime_part.strip()
                data['boot_time'] = boottime_part.replace('since ', '').replace(')', '').strip()
            elif 'cpu usage' in key:
                data['cpu_usage'] = value
            elif 'used ram' in key:
                parts = value.split('/')
                if len(parts) == 2:
                    data['ram_usage'] = parts[0].strip()
                    data['total_ram'] = parts[1].strip()
            elif 'online users' in key:
                data['online_users'] = int(value)
            elif 'upload speed' in key:
                data['upload_speed'] = value
            elif 'download speed' in key:
                data['download_speed'] = value
            elif 'tcp connections' in key:
                data['tcp_connections'] = int(value)
            elif 'udp connections' in key:
                data['udp_connections'] = int(value)
            elif 'total uploaded' in key or 'uploaded traffic' in key:
                if current_section == 'reboot':
                    data['reboot_uploaded_traffic'] = value
                elif current_section == 'user':
                    data['user_uploaded_traffic'] = value
            elif 'total downloaded' in key or 'downloaded traffic' in key:
                if current_section == 'reboot':
                    data['reboot_downloaded_traffic'] = value
                elif current_section == 'user':
                    data['user_downloaded_traffic'] = value
            elif 'combined traffic' in key or 'total traffic' in key:
                if current_section == 'reboot':
                    data['reboot_total_traffic'] = value
                elif current_section == 'user':
                    data['user_total_traffic'] = value
        except (ValueError, IndexError) as e:
            raise ValueError(f'Error parsing line \'{line}\': {e}')

    try:
        return ServerStatusResponse(**data)
    except Exception as e:
        raise ValueError(f'Invalid or incomplete server info: {e}')


@router.get('/services/status', response_model=ServerServicesStatusResponse)
async def server_services_status_api():
    """
    Retrieve the status of various services.

    This endpoint provides information about the status of different services,
    including Hysteria2, TelegramBot, Singbox, and Normal-SUB.

    Returns:
        ServerServicesStatusResponse: A response model containing service status details.

    Raises:
        HTTPException: If the services status is not available (404) or
                       if there is an error processing the request (400).
    """

    try:
        if res := cli_api.get_services_status():
            return __parse_services_status(res)
        raise HTTPException(status_code=404, detail='Services status not available.')
    except Exception as e:
        raise HTTPException(status_code=400, detail=f'Error: {str(e)}')


def __parse_services_status(services_status: dict[str, bool]) -> ServerServicesStatusResponse:
    '''
    Parse the services status provided by cli_api.get_services_status()
    and return a ServerServicesStatusResponse instance.
    '''
    parsed_services_status: dict[str, bool] = {}
    for service, status in services_status.items():
        if 'hysteria-server' in service:
            parsed_services_status['hysteria_server'] = status
        elif 'hysteria-ip-limit' in service:
            parsed_services_status['hysteria_iplimit'] = status
        elif 'hysteria-webpanel' in service:
            parsed_services_status['hysteria_webpanel'] = status
        elif 'telegram-bot' in service:
            parsed_services_status['hysteria_telegram_bot'] = status
        elif 'hysteria-normal-sub' in service:
            parsed_services_status['hysteria_normal_sub'] = status
        elif 'wg-quick' in service:
            parsed_services_status['hysteria_warp'] = status
    return ServerServicesStatusResponse(**parsed_services_status)

@router.get('/version', response_model=VersionInfoResponse)
async def get_version_info():
    """Retrieves the current version of the panel."""
    try:
        version_output = cli_api.show_version()
        if version_output:
            current_version = version_output.split(": ")[1].strip()
            return VersionInfoResponse(current_version=current_version)
        raise HTTPException(status_code=404, detail="Version information not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/version/check', response_model=VersionCheckResponse)
async def check_version_info():
    """Checks for updates and retrieves version information."""
    try:
        check_output = cli_api.check_version()
        if check_output:
            lines = check_output.splitlines()
            current_version = lines[0].split(": ")[1].strip()

            if len(lines) > 1 and "Latest Version" in lines[1]:
                latest_version = lines[1].split(": ")[1].strip()
                is_latest = current_version == latest_version
                changelog_start_index = 3 
                changelog = "\n".join(lines[changelog_start_index:]).strip()
                return VersionCheckResponse(is_latest=is_latest, current_version=current_version,
                                             latest_version=latest_version, changelog=changelog)
            else:
                return VersionCheckResponse(
                    is_latest=True,
                    current_version=current_version,
                    latest_version=current_version,
                    changelog="Panel is up-to-date."
                )

        raise HTTPException(status_code=404, detail="Version information not found")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))