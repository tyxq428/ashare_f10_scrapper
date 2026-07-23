from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit


def normalize_responses_endpoint(value: str) -> str:
    endpoint = value.strip()
    parsed = urlsplit(endpoint)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("endpoint must be an absolute HTTPS URL")

    path = parsed.path.rstrip("/")
    if path.endswith("/responses"):
        normalized_path = path
    elif path.endswith("/v1"):
        normalized_path = f"{path}/responses"
    elif path:
        normalized_path = f"{path}/v1/responses"
    else:
        normalized_path = "/v1/responses"

    return urlunsplit((parsed.scheme, parsed.netloc, normalized_path, parsed.query, ""))
