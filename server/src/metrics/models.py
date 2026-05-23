from pydantic import BaseModel, Field


class MetricReport(BaseModel):
    peer_id: str
    rtt_ms: float = Field(ge=0)
    jitter_ms: float = Field(ge=0)
    loss_rate: float = Field(ge=0.0, le=1.0)
    bandwidth_mbps: float | None = None


class RecommendationResponse(BaseModel):
    peer_id: str
    redundancy_level: float
    quality: str
    based_on_samples: int
    profile_name: str = "unknown"
