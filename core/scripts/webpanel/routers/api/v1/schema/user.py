from typing import Optional, List
from pydantic import BaseModel, RootModel, Field


class UserInfoResponse(BaseModel):
    password: str
    max_download_bytes: int
    expiration_days: int
    account_creation_date: str
    blocked: bool
    unlimited_ip: bool = Field(False, alias='unlimited_user')
    status: Optional[str] = None
    upload_bytes: Optional[int] = None
    download_bytes: Optional[int] = None


class UserListResponse(RootModel):
    root: dict[str, UserInfoResponse]


class AddUserInputBody(BaseModel):
    username: str
    traffic_limit: int
    expiration_days: int
    password: Optional[str] = None
    creation_date: Optional[str] = None
    unlimited: bool = False


class EditUserInputBody(BaseModel):
    new_username: Optional[str] = None
    new_traffic_limit: Optional[int] = None
    new_expiration_days: Optional[int] = None
    renew_password: bool = False
    renew_creation_date: bool = False
    blocked: Optional[bool] = None
    unlimited_ip: Optional[bool] = None

class NodeUri(BaseModel):
    name: str
    uri: str

class UserUriResponse(BaseModel):
    username: str
    ipv4: Optional[str] = None
    ipv6: Optional[str] = None
    nodes: Optional[List[NodeUri]] = []
    normal_sub: Optional[str] = None
    error: Optional[str] = None