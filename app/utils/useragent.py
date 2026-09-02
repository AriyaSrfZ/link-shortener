"""
Parses a raw User-Agent header into browser / OS / device-type fields
for the click log, using the `user-agents` library.
"""

from user_agents import parse as ua_parse


def parse_user_agent(raw: str) -> dict:
    if not raw:
        return {"browser": None, "os": None, "device_type": None}

    ua = ua_parse(raw)

    if ua.is_bot:
        device_type = "bot"
    elif ua.is_mobile:
        device_type = "mobile"
    elif ua.is_tablet:
        device_type = "tablet"
    elif ua.is_pc:
        device_type = "desktop"
    else:
        device_type = "unknown"

    browser = f"{ua.browser.family} {ua.browser.version_string}".strip()
    os_name = f"{ua.os.family} {ua.os.version_string}".strip()

    return {
        "browser": browser or None,
        "os": os_name or None,
        "device_type": device_type,
    }
