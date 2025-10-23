from pydantic import BaseModel, field_validator, Field
from ipaddress import ip_address
import re
from typing import Optional

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
    port: Optional[int] = Field(default=None, ge=1, le=65535)
    sni: Optional[str] = None
    pinSHA256: Optional[str] = None
    obfs: Optional[str] = None
    insecure: Optional[bool] = False

    @field_validator('ip', mode='before')
    def check_node_ip(cls, v: str | None):
        if not v or not v.strip():
            raise ValueError("IP or Domain field cannot be empty.")
        return validate_ip_or_domain(v)

    @field_validator('sni', mode='before')
    def validate_sni_format(cls, v: str | None):
        if v is None or not v.strip():
            return None
        
        v_stripped = v.strip()
        
        if "://" in v_stripped:
            raise ValueError("SNI must not contain a protocol (e.g., http://).")

        try:
            ip_address(v_stripped)
            raise ValueError("SNI cannot be an IP address.")
        except ValueError as e:
            if "SNI cannot be an IP address" in str(e):
                raise e

        domain_regex = re.compile(
            r'^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9][a-z0-9-]{0,61}[a-z0-9]$', 
            re.IGNORECASE
        )
        if not domain_regex.match(v_stripped):
            raise ValueError(f"'{v_stripped}' is not a valid domain name for SNI.")
            
        return v_stripped

    @field_validator('pinSHA256', mode='before')
    def validate_pin_format(cls, v: str | None):
        if v is None or not v.strip():
            return None
        
        v_stripped = v.strip().upper()
        pin_regex = re.compile(r'^([0-9A-F]{2}:){31}[0-9A-F]{2}$')
        
        if not pin_regex.match(v_stripped):
            raise ValueError("Invalid SHA256 pin format.")
            
        return v_stripped

class AddNodeBody(Node):
    pass

class DeleteNodeBody(BaseModel):
    name: str

NodeListResponse = list[Node]