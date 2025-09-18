from fastapi import APIRouter, HTTPException
from ..schema.response import DetailResponse
from ..schema.config.telegram import StartInputBody, SetIntervalInputBody, BackupIntervalResponse
import cli_api

router = APIRouter()


@router.post('/start', response_model=DetailResponse, summary='Start Telegram Bot')
async def telegram_start_api(body: StartInputBody):
    """
    Starts the Telegram bot.

    Args:
        body (StartInputBody): The data containing the Telegram bot token, admin ID, and optional backup interval in hours.

    Returns:
        DetailResponse: The response containing the result of the action.
    """
    try:
        cli_api.start_telegram_bot(body.token, body.admin_id, body.backup_interval)
        return DetailResponse(detail='Telegram bot started successfully.')
    except Exception as e:
        raise HTTPException(status_code=400, detail=f'Error: {str(e)}')


@router.delete('/stop', response_model=DetailResponse, summary='Stop Telegram Bot')
async def telegram_stop_api():
    """
    Stops the Telegram bot.

    Returns:
        DetailResponse: The response containing the result of the action.
    """

    try:
        cli_api.stop_telegram_bot()
        return DetailResponse(detail='Telegram bot stopped successfully.')
    except Exception as e:
        raise HTTPException(status_code=400, detail=f'Error: {str(e)}')


@router.get('/backup-interval', response_model=BackupIntervalResponse, summary='Get Telegram Bot Backup Interval')
async def telegram_get_interval_api():
    """
    Gets the current automatic backup interval for the Telegram bot.

    Returns:
        BackupIntervalResponse: The response containing the current interval in hours.
    """
    try:
        interval = cli_api.get_telegram_bot_backup_interval()
        return BackupIntervalResponse(backup_interval=interval)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Error: {str(e)}')


@router.post('/backup-interval', response_model=DetailResponse, summary='Set Telegram Bot Backup Interval')
async def telegram_set_interval_api(body: SetIntervalInputBody):
    """
    Sets the automatic backup interval for the Telegram bot.

    Args:
        body (SetIntervalInputBody): The data containing the backup interval in hours.

    Returns:
        DetailResponse: The response containing the result of the action.
    """
    try:
        cli_api.set_telegram_bot_backup_interval(body.backup_interval)
        return DetailResponse(detail=f'Telegram bot backup interval set to {body.backup_interval} hours successfully.')
    except Exception as e:
        raise HTTPException(status_code=400, detail=f'Error: {str(e)}')