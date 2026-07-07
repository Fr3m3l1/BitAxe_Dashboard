"""Bitcoin network context: live data from mempool.space (cached) and
an approximate historical difficulty table for the fun stats."""

import logging
import time

import requests
import urllib3.util.connection as _urllib3_conn

# Force IPv4: hosts with broken/blackholed IPv6 make urllib3 walk every
# AAAA record at full connect-timeout each (minutes of hanging). All APIs
# used here work over IPv4.
_urllib3_conn.HAS_IPV6 = False

logger = logging.getLogger(__name__)

_CACHE = {"ts": 0.0, "data": None}
_TTL = 600  # 10 min


def get_network_status() -> dict | None:
    """Current network difficulty, hashrate, tip height and retarget info.
    Serves a stale cache when the APIs are unreachable; None if never fetched."""
    if time.time() - _CACHE["ts"] < _TTL and _CACHE["data"]:
        return _CACHE["data"]
    try:
        height = requests.get("https://mempool.space/api/blocks/tip/height", timeout=(5, 10)).json()
        hr = requests.get("https://mempool.space/api/v1/mining/hashrate/3d", timeout=(5, 10)).json()
        adj = requests.get("https://mempool.space/api/v1/difficulty-adjustment", timeout=(5, 10)).json()
        data = {
            "height": int(height),
            "difficulty": float(hr["currentDifficulty"]),
            "network_hashrate": float(hr["currentHashrate"]),  # H/s
            "adjustment": {
                "progress_pct": adj.get("progressPercent"),
                "estimated_change_pct": adj.get("difficultyChange"),
                "remaining_blocks": adj.get("remainingBlocks"),
                "estimated_retarget_ts": (adj.get("estimatedRetargetDate") or 0) / 1000 or None,
            },
        }
        _CACHE.update(ts=time.time(), data=data)
        return data
    except (requests.RequestException, ValueError, KeyError, TypeError) as e:
        logger.warning("mempool.space fetch failed: %s", e)
    # Minimal fallback: difficulty only.
    try:
        diff = float(requests.get("https://blockchain.info/q/getdifficulty", timeout=(5, 10)).text)
        data = {"height": None, "difficulty": diff,
                "network_hashrate": diff * 2**32 / 600, "adjustment": None}
        _CACHE.update(ts=time.time(), data=data)
        return data
    except (requests.RequestException, ValueError) as e:
        logger.warning("blockchain.info fallback failed: %s", e)
    return _CACHE["data"]  # possibly stale, possibly None


# Approximate network difficulty at points in time (decimal year -> difficulty).
# Good to a few months — used only for "your best share would have solved a
# block back in ..." style stats.
DIFFICULTY_HISTORY = [
    (2009.0, 1.0),
    (2010.0, 1.8),
    (2010.5, 45.0),
    (2011.0, 1.4e4),
    (2011.5, 1.56e6),
    (2012.0, 1.1e6),
    (2012.5, 1.6e6),
    (2013.0, 3.2e6),
    (2013.5, 2.7e7),
    (2014.0, 1.4e9),
    (2014.5, 1.7e10),
    (2015.0, 4.4e10),
    (2015.5, 4.9e10),
    (2016.0, 1.0e11),
    (2016.5, 2.1e11),
    (2017.0, 3.2e11),
    (2017.5, 7.1e11),
    (2018.0, 1.9e12),
    (2018.5, 5.1e12),
    (2019.0, 5.6e12),
    (2019.5, 9.0e12),
    (2020.0, 1.4e13),
    (2020.5, 1.7e13),
    (2021.0, 2.0e13),
    (2021.5, 1.4e13),
    (2022.0, 2.4e13),
    (2022.5, 2.9e13),
    (2023.0, 3.4e13),
    (2023.5, 5.3e13),
    (2024.0, 7.3e13),
    (2024.5, 8.3e13),
    (2025.0, 1.1e14),
    (2025.5, 1.26e14),
    (2026.0, 1.5e14),
]


def era_of_difficulty(diff: float) -> float | None:
    """Latest (approximate) decimal year when the network difficulty was still
    at or below `diff` — i.e. when a share of this difficulty would have
    solved a block. None if it beats even today's table."""
    if diff < 1:
        return None
    # Not monotonic (2012 and 2021 dips), so take the latest matching entry.
    years = [year for year, d in DIFFICULTY_HISTORY if d <= diff]
    return max(years) if years else None
