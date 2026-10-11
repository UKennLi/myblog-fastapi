"""Public URLs come only from operator configuration, never request headers."""
from ipaddress import ip_address
import re
from urllib.parse import quote, urlsplit, urlunsplit


def normalize_site_url(value):
    if not value or not isinstance(value, str):
        return ""
    value = value.strip()
    if any(ord(char) < 33 for char in value) or "\\" in value:
        return ""
    try:
        parts = urlsplit(value)
        if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password:
            return ""
        if parts.query or parts.fragment or parts.port == 0:
            return ""
        host = parts.hostname.lower().rstrip(".")
        if host == "localhost" or host.endswith((".localhost", ".local")):
            return ""
        try:
            if not ip_address(host).is_global:
                return ""
        except ValueError:
            host = host.encode("idna").decode("ascii")
            if "." not in host or not re.search(r"[a-zA-Z]", host) or not all(re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?", label) for label in host.split(".")):
                return ""
        return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))
    except (ValueError, UnicodeError):
        return ""


def public_site_url(settings, options):
    return normalize_site_url(settings.public_site_url) or normalize_site_url(options.get("siteUrl"))


def public_url(base, path):
    return base + "/" + quote(path.lstrip("/"), safe="/-._~")
