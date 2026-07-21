from __future__ import annotations

import re
from typing import Any

from ashare_f10.models import SecurityIdentity

_CODE_RE = re.compile(r"^\d{6}$")


def parse_security(code: str) -> SecurityIdentity:
    normalized = re.sub(r"\D", "", code.strip())
    if not _CODE_RE.fullmatch(normalized):
        raise ValueError("股票代码必须是6位数字")

    if normalized.startswith(("4", "8", "92")):
        exchange = "BJ"
        market_id = 0
    elif normalized.startswith(("0", "1", "2", "3")):
        exchange = "SZ"
        market_id = 0
    else:
        exchange = "SH"
        market_id = 1

    return SecurityIdentity(
        code=normalized,
        exchange=exchange,
        secucode=f"{normalized}.{exchange}",
        page_code=f"{exchange}{normalized}",
        market_id=market_id,
        market_id_code=f"{market_id}.{normalized}",
    )


def replace_security_tokens(value: Any, identity: SecurityIdentity) -> Any:
    """Replace the verified 688521 sample identifiers in nested request templates."""
    if isinstance(value, dict):
        return {k: replace_security_tokens(v, identity) for k, v in value.items()}
    if isinstance(value, list):
        return [replace_security_tokens(v, identity) for v in value]
    if not isinstance(value, str):
        return value

    result = value
    replacements = (
        ("688521.SH", identity.secucode),
        ("SH688521", identity.page_code),
        ("1.688521", identity.market_id_code),
        ("688521", identity.code),
    )
    for old, new in replacements:
        result = result.replace(old, new)

    # Some POST APIs use a separate market parameter.
    if result == "1" and identity.market_id == 0:
        return "0"
    return result
