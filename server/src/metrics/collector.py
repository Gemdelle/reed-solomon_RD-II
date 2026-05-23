from redis_client import get_redis

from .models import MetricReport

_MAX_REPORTS = 10


async def store_report(report: MetricReport) -> None:
    r = get_redis()
    key = f"metrics:{report.peer_id}"
    await r.lpush(key, report.model_dump_json())
    await r.ltrim(key, 0, _MAX_REPORTS - 1)


async def get_average(peer_id: str) -> dict | None:
    r = get_redis()
    key = f"metrics:{peer_id}"
    items_raw = await r.lrange(key, 0, -1)
    if not items_raw:
        return None
    items = [MetricReport.model_validate_json(raw) for raw in items_raw]
    n = len(items)
    return {
        "rtt_ms": sum(item.rtt_ms for item in items) / n,
        "jitter_ms": sum(item.jitter_ms for item in items) / n,
        "loss_rate": sum(item.loss_rate for item in items) / n,
        "samples": n,
    }
