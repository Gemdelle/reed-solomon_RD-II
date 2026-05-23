"""
Maps averaged network metrics to a recommended RS redundancy level.

Quality bands are conservative: cheaper to send extra parity packets
than to fail a transfer and have the user retry.

Network profiles (from NETWORK_HINT) enforce a minimum redundancy floor
appropriate for the link type, regardless of recent metric quality.
"""

_QUALITY_TABLE: list[tuple[str, float, float, float, float]] = [
    # quality,     loss_max, rtt_max_ms, jitter_max_ms, redundancy
    ("excellent",  0.01,     50.0,       5.0,           0.05),
    ("good",       0.05,     150.0,      20.0,          0.10),
    ("fair",       0.15,     500.0,      80.0,          0.25),
    ("poor",       0.30,     1000.0,     200.0,         0.40),
    ("critical",   1.0,      float("inf"), float("inf"), 0.50),
]

PROFILES: dict[str, dict] = {
    "lan":       {"min_redundancy": 0.05, "label": "LAN"},
    "wifi":      {"min_redundancy": 0.10, "label": "Wi-Fi"},
    "cellular":  {"min_redundancy": 0.20, "label": "Cellular"},
    "satellite": {"min_redundancy": 0.35, "label": "Satellite"},
}

_QUALITY_TO_PROFILE_LABEL: dict[str, str] = {
    "excellent": "LAN",
    "good":      "Wi-Fi",
    "fair":      "Cellular",
    "poor":      "Satellite",
    "critical":  "Satellite",
}


def compute_recommendation(
    rtt_ms: float,
    jitter_ms: float,
    loss_rate: float,
    network_hint: str = "auto",
) -> tuple[float, str, str]:
    """Return (redundancy_level, quality, profile_name)."""
    level, quality = 0.50, "critical"
    for q, loss_max, rtt_max, jitter_max, lvl in _QUALITY_TABLE:
        if loss_rate <= loss_max and rtt_ms <= rtt_max and jitter_ms <= jitter_max:
            level, quality = lvl, q
            break

    profile = PROFILES.get(network_hint)
    if profile:
        level = max(level, profile["min_redundancy"])
        profile_name = profile["label"]
    else:
        profile_name = _QUALITY_TO_PROFILE_LABEL.get(quality, "Auto")

    return level, quality, profile_name
