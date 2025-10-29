from fastapi import APIRouter, HTTPException
from ..schema.response import DetailResponse
import json
import os
from scripts.db.database import db

from ..schema.config.ip import (
    EditInputBody, 
    StatusResponse,
    AddNodeBody,
    DeleteNodeBody,
    NodeListResponse,
    NodesTrafficPayload
)
import cli_api

router = APIRouter()


@router.get('/get', response_model=StatusResponse, summary='Get Local Server IP Status')
async def get_ip_api():
    """
    Retrieves the current status of the main server's IP addresses.

    Returns:
        StatusResponse: A response model containing the current IP address details.
    """
    try:

        ipv4, ipv6 = cli_api.get_ip_address()
        return StatusResponse(ipv4=ipv4, ipv6=ipv6)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f'Error: {str(e)}')


@router.get('/add', response_model=DetailResponse, summary='Detect and Add Local Server IP')
async def add_ip_api():
    """
    Adds the auto-detected IP addresses to the .configs.env file.

    Returns:
        A DetailResponse with a message indicating the IP addresses were added successfully.
    """
    try:
        cli_api.add_ip_address()
        return DetailResponse(detail='IP addresses added successfully.')
    except Exception as e:
        raise HTTPException(status_code=400, detail=f'Error: {str(e)}')


@router.post('/edit', response_model=DetailResponse, summary='Edit Local Server IP')
async def edit_ip_api(body: EditInputBody):
    """
    Edits the main server's IP addresses in the .configs.env file.

    Args:
        body: An instance of EditInputBody containing the new IPv4 and/or IPv6 addresses.
    """
    try:
        # if not body.ipv4 and not body.ipv6:
        #     raise HTTPException(status_code=400, detail='Error: You must specify either ipv4 or ipv6')
        cli_api.edit_ip_address(str(body.ipv4), str(body.ipv6))
        return DetailResponse(detail='IP address edited successfully.')
    except Exception as e:
        raise HTTPException(status_code=400, detail=f'Error: {str(e)}')


@router.get('/nodes', response_model=NodeListResponse, summary='Get All External Nodes')
async def get_all_nodes():
    """
    Retrieves the list of all configured external nodes.

    Returns:
        A list of node objects, each containing a name and an IP.
    """
    if not os.path.exists(cli_api.NODES_JSON_PATH):
        return []
    try:
        with open(cli_api.NODES_JSON_PATH, 'r') as f:
            content = f.read()
            if not content:
                return []
            return json.loads(content)
    except (json.JSONDecodeError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"Failed to read or parse nodes file: {e}")


@router.post('/nodes/add', response_model=DetailResponse, summary='Add External Node')
async def add_node(body: AddNodeBody):
    """
    Adds a new external node to the configuration.

    Args:
        body: Request body containing the full details of the node.
    """
    try:
        cli_api.add_node(
            name=body.name, 
            ip=body.ip, 
            port=body.port, 
            sni=body.sni, 
            pinSHA256=body.pinSHA256, 
            obfs=body.obfs,
            insecure=body.insecure
        )
        return DetailResponse(detail=f"Node '{body.name}' added successfully.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post('/nodes/delete', response_model=DetailResponse, summary='Delete External Node')
async def delete_node(body: DeleteNodeBody):
    """
    Deletes an external node from the configuration by its name.

    Args:
        body: Request body containing the name of the node to delete.
    """
    try:
        cli_api.delete_node(body.name)
        return DetailResponse(detail=f"Node '{body.name}' deleted successfully.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post('/nodestraffic', response_model=DetailResponse, summary='Receive and Aggregate Traffic from Node')
async def receive_node_traffic(body: NodesTrafficPayload):
    """
    Receives traffic delta from a node and adds it to the user's total in the database.
    Authentication is handled by the AuthMiddleware.
    """
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection is not available.")
    
    updated_count = 0
    for user_traffic in body.users:
        try:
            db_user = db.get_user(user_traffic.username)
            if not db_user:
                continue

            new_upload = db_user.get('upload_bytes', 0) + user_traffic.upload_bytes
            new_download = db_user.get('download_bytes', 0) + user_traffic.download_bytes

            update_data = {
                'upload_bytes': new_upload,
                'download_bytes': new_download,
                'status': user_traffic.status,
            }
            
            if not db_user.get('account_creation_date') and user_traffic.account_creation_date:
                update_data['account_creation_date'] = user_traffic.account_creation_date

            db.update_user(user_traffic.username, update_data)
            updated_count += 1
            
        except Exception as e:
            print(f"Error updating traffic for user {user_traffic.username}: {e}")

    return DetailResponse(detail=f"Successfully processed and aggregated traffic for {updated_count} users.")