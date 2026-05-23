from datetime import datetime
from pydantic import BaseModel


class InviteCreate(BaseModel):
    org_id: str = "default"
    ttl_seconds: int = 3600


class InviteInfo(BaseModel):
    token: str
    issued_by: str
    org_id: str
    expires_at: datetime
