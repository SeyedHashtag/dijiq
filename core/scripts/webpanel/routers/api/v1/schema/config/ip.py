from pydantic import BaseModel, field_validator, ValidationInfo
from ipaddress import IPv4Address, IPv6Address, ip_address
import re

def validate_ip_or_domain(v: str) -> str | None:
    if v is None or v.strip() in ['', 'None']:
        return None
        
    v_stripped = v.strip()
    
    try:
        ip_address(v_stripped)
        return v_stripped
    except ValueError:
        domain_regex = re.compile(
            r'^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9][a-z0-9-]{0,61}[a-z0-9]$', 
            re.IGNORECASE
        )
        if domain_regex.match(v_stripped):
            return v_stripped
        raise ValueError(f"'{v_stripped}' is not a valid IP address or domain name.")

class StatusResponse(BaseModel):
    ipv4: str | None = None
    ipv6: str | None = None

    @field_validator('ipv4', 'ipv6', mode='before')
    def check_local_server_ip(cls, v: str | None):
        return validate_ip_or_domain(v)

class EditInputBody(StatusResponse):
    pass

class Node(BaseModel):
    name: str
    ip: str

    @field_validator('ip', mode='before')
    def check_node_ip(cls, v: str | None):
        if not v or not v.strip():
            raise ValueError("IP or Domain field cannot be empty.")
        return validate_ip_or_domain(v)

class AddNodeBody(Node):
    pass

class DeleteNodeBody(BaseModel):
    name: str

NodeListResponse = list[Node]