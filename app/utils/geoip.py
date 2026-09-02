"""
Offline IP -> country lookup using geoip2fast, which bundles its own
database file (no MaxMind license or network call needed). Country-level
data only; city is not reliably available in the free dataset, so it is
left blank rather than guessed.

The GeoIP2Fast instance is created once at import time and reused - it
loads its database into memory, so building it per-request would be
wasteful.
"""

from geoip2fast import GeoIP2Fast

_geo = GeoIP2Fast()


def lookup_country(ip_address: str) -> dict:
    if not ip_address:
        return {"country": None, "city": None}

    try:
        result = _geo.lookup(ip_address)
    except Exception:
        return {"country": None, "city": None}

    if not result or result.is_private or not result.country_name:
        return {"country": None, "city": None}

    return {"country": result.country_name, "city": None}
