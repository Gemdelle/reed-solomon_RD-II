from datetime import datetime

from pydantic import BaseModel, Field


class DeviceTokenCreate(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    peer_id: str | None = None          # informational — the intended PEER_ID
    ttl_seconds: int | None = None      # None = indefinite; e.g. 86400 = 1 day


class DeviceTokenInfo(BaseModel):
    id: str
    label: str
    peer_id: str | None = None
    org_id: str
    created_by: str
    created_at: datetime
    expires_at: datetime | None = None
    token_preview: str                  # "rd_xK3mAb9..." — safe to display always
    token: str | None = None            # full value — only returned on POST, never again
