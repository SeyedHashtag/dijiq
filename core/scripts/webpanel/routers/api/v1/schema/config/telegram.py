from pydantic import BaseModel
from typing import Optional


class StartInputBody(BaseModel):
    token: str
    admin_id: str
    backup_interval: Optional[int] = None


class SetIntervalInputBody(BaseModel):
    backup_interval: int


class BackupIntervalResponse(BaseModel):
    backup_interval: Optional[int] = None