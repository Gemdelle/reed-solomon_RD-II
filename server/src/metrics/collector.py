from datetime import datetime, timezone

from redis_client import get_redis
from neo4j_client import get_neo4j

from .models import MetricReport

_MAX_REPORTS = 10


async def store_report(report: MetricReport) -> None:
    now = datetime.now(timezone.utc).isoformat()
    report = report.model_copy(update={"recorded_at": now})

    # 1. Store in Redis as a fast-access cache for the VERY latest state (optional, keeping for compatibility)
    r = get_redis()
    key = f"metrics:{report.peer_id}:{report.target_peer_id}"
    await r.set(key, report.model_dump_json(), ex=3600)  # Cache for 1 hour

    # 2. Update Neo4j graph with historical nodes
    driver = get_neo4j()

    # Query to create/update the relationship and create a historical Metric node
    # (a:Peer)-[:REPORTED]->(m:MetricSample {timestamp, rtt, ...})
    # And also update the direct CONNECTS_TO for routing efficiency

    async with driver.session() as session:
        if report.target_peer_id == "server":
            # Metrics towards server: Peer -> MetricSample
            query = (
                "MATCH (p:Peer {peer_id: $peer_id}) "
                "CREATE (p)-[:REPORTED_TO_SERVER]->(m:MetricSample { "
                "  rtt_ms: $rtt_ms, "
                "  jitter_ms: $jitter_ms, "
                "  loss_rate: $loss_rate, "
                "  timestamp: datetime($now) "
                "})"
            )
            await session.run(
                query,
                peer_id=report.peer_id,
                rtt_ms=report.rtt_ms,
                jitter_ms=report.jitter_ms,
                loss_rate=report.loss_rate,
                now=now
            )
        else:
            # P2P Metrics: (a)-[r:CONNECTS_TO]->(b) AND (a)-[:REPORTED_P2P]->(m)
            query = (
                "MATCH (a:Peer {peer_id: $src_id}), (b:Peer {peer_id: $dst_id}) "
                "MERGE (a)-[r:CONNECTS_TO]->(b) "
                "SET r.rtt_ms = $rtt_ms, "
                "    r.jitter_ms = $jitter_ms, "
                "    r.loss_rate = $loss_rate, "
                "    r.updated_at = datetime($now) "
                "CREATE (a)-[:REPORTED_P2P {target_id: $dst_id}]->(m:MetricSample { "
                "  rtt_ms: $rtt_ms, "
                "  jitter_ms: $jitter_ms, "
                "  loss_rate: $loss_rate, "
                "  timestamp: datetime($now) "
                "})"
            )
            await session.run(
                query,
                src_id=report.peer_id,
                dst_id=report.target_peer_id,
                rtt_ms=report.rtt_ms,
                jitter_ms=report.jitter_ms,
                loss_rate=report.loss_rate,
                now=now
            )


async def get_average(peer_id: str, target_id: str = "server", limit: int = 10) -> dict | None:
    """Fetch the average of the last 'limit' samples from Neo4j."""
    driver = get_neo4j()

    if target_id == "server":
        query = (
            "MATCH (p:Peer {peer_id: $peer_id})-[:REPORTED_TO_SERVER]->(m:MetricSample) "
            "RETURN m.rtt_ms as rtt, m.jitter_ms as jitter, m.loss_rate as loss "
            "ORDER BY m.timestamp DESC LIMIT $limit"
        )
    else:
        query = (
            "MATCH (p:Peer {peer_id: $peer_id})-[:REPORTED_P2P {target_id: $target_id}]->(m:MetricSample) "
            "RETURN m.rtt_ms as rtt, m.jitter_ms as jitter, m.loss_rate as loss "
            "ORDER BY m.timestamp DESC LIMIT $limit"
        )

    async with driver.session() as session:
        result = await session.run(query, peer_id=peer_id, target_id=target_id, limit=limit)
        records = await result.data()

        if not records:
            return None

        n = len(records)
        return {
            "rtt_ms": sum(r["rtt"] for r in records) / n,
            "jitter_ms": sum(r["jitter"] for r in records) / n,
            "loss_rate": sum(r["loss"] for r in records) / n,
            "samples": n,
        }

