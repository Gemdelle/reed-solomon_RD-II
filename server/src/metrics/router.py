from fastapi import APIRouter, Depends

from auth.deps import CallerInfo, extract_auth
from neo4j_client import get_neo4j
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
    # 1. Get averages from Neo4j (towards server)
    avg = await get_average(peer_id, target_id="server")

    # 2. Get network hint from Neo4j Peer node
    driver = get_neo4j()
    network_hint = "auto"
    query = "MATCH (p:Peer {peer_id: $peer_id}) RETURN p.network_hint as hint"
    async with driver.session() as session:
        result = await session.run(query, peer_id=peer_id)
        record = await result.single()
        if record:
            network_hint = record["hint"] or "auto"

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


@router.get("/history/{peer_id}")
async def get_metric_history(peer_id: str, target_id: str = "server", limit: int = 50) -> dict:
    """Return the last N raw metric samples for a peer (oldest-first) from Neo4j."""
    driver = get_neo4j()
    
    if target_id == "server":
        query = (
            "MATCH (p:Peer {peer_id: $peer_id})-[:REPORTED_TO_SERVER]->(m:MetricSample) "
            "RETURN m.rtt_ms as rtt_ms, m.jitter_ms as jitter_ms, "
            "       m.loss_rate as loss_rate, toString(m.timestamp) as recorded_at "
            "ORDER BY m.timestamp DESC LIMIT $limit"
        )
    else:
        query = (
            "MATCH (p:Peer {peer_id: $peer_id})-[:REPORTED_P2P {target_id: $target_id}]->(m:MetricSample) "
            "RETURN m.rtt_ms as rtt_ms, m.jitter_ms as jitter_ms, "
            "       m.loss_rate as loss_rate, toString(m.timestamp) as recorded_at "
            "ORDER BY m.timestamp DESC LIMIT $limit"
        )

    async with driver.session() as session:
        result = await session.run(query, peer_id=peer_id, target_id=target_id, limit=limit)
        records = await result.data()
        # Records are newest-first due to DESC, reverse to get oldest-first
        samples = list(reversed(records))
        return {"peer_id": peer_id, "target_id": target_id, "samples": samples}


@router.get("/network-graph")
async def get_network_graph(
    caller: CallerInfo = Depends(extract_auth),
) -> dict:
    """Return all P2P CONNECTS_TO edges for the caller's org (from Neo4j)."""
    driver = get_neo4j()
    query = (
        "MATCH (a:Peer {org_id: $org_id})-[r:CONNECTS_TO]->(b:Peer {org_id: $org_id}) "
        "RETURN a.peer_id AS source, b.peer_id AS target, "
        "       r.rtt_ms AS rtt_ms, r.jitter_ms AS jitter_ms, "
        "       r.loss_rate AS loss_rate, toString(r.updated_at) AS updated_at"
    )
    edges = []
    async with driver.session() as session:
        result = await session.run(query, org_id=caller.org_id)
        async for record in result:
            edges.append({
                "source": record["source"],
                "target": record["target"],
                "rtt_ms": record["rtt_ms"],
                "jitter_ms": record["jitter_ms"],
                "loss_rate": record["loss_rate"],
                "updated_at": record["updated_at"],
            })
    return {"edges": edges}
