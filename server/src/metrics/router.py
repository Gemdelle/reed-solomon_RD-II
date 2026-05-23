from fastapi import APIRouter

from redis_client import get_redis
from .collector import get_average, store_report
from .models import MetricReport, RecommendationResponse
from .recommender import compute_recommendation

router = APIRouter()

_DEFAULT_REDUNDANCY = 0.25
_DEFAULT_QUALITY = "unknown"


@router.post("/report")
async def report_metrics(report: MetricReport) -> dict:
    await store_report(report)
    return {"status": "ok"}


@router.get("/recommendation/{peer_id}", response_model=RecommendationResponse)
async def get_recommendation(peer_id: str) -> RecommendationResponse:
    avg = await get_average(peer_id)

    r = get_redis()
    peer_data = await r.hgetall(f"peer:{peer_id}")
    network_hint = peer_data.get("network_hint", "auto") or "auto"

    if not avg:
        return RecommendationResponse(
            peer_id=peer_id,
            redundancy_level=_DEFAULT_REDUNDANCY,
            quality=_DEFAULT_QUALITY,
            based_on_samples=0,
            profile_name="unknown",
        )

    level, quality, profile_name = compute_recommendation(
        rtt_ms=avg["rtt_ms"],
        jitter_ms=avg["jitter_ms"],
        loss_rate=avg["loss_rate"],
        network_hint=network_hint,
    )
    return RecommendationResponse(
        peer_id=peer_id,
        redundancy_level=level,
        quality=quality,
        based_on_samples=avg["samples"],
        profile_name=profile_name,
    )
