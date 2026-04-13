"""
STEP 7 — Threat Intelligence Check
Extracts URLs and IP addresses from text and checks them against a local
known-bad blocklist. No external API calls are made.
"""

import re
from dataclasses import dataclass, field

# ── Regex extractors ──────────────────────────────────────────────────────────

_RE_URL = re.compile(
    r"https?://[^\s\"'<>\]\[)(\u0000-\u001f]+",
    re.IGNORECASE
)
_RE_IPV4 = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"
)

# ── Local blocklist ───────────────────────────────────────────────────────────
# A curated list of known malicious/C&C domains and IPs.
# Sources: abuse.ch, Feodo Tracker, common phishing domains, etc.

_BLOCKED_DOMAINS: set[str] = {
    # Malware C&C / exploit kit domains
    "malware-traffic-analysis.net",
    "urlhaus.abuse.ch",
    "feodotracker.abuse.ch",
    "bazaar.abuse.ch",
    "dridex.biz",
    "emotet.blue",
    "trickbot.cc",
    "qakbot.net",

    # Phishing frameworks / known bad
    "phishtank.com",
    "openphish.com",
    "evilginx.io",
    "gophish.io",
    "ngrok.io",           # often abused for tunneling C&C
    "serveo.net",         # often abused
    "pagekite.me",        # often abused

    # Tor / anonymization exit nodes commonly used in attacks
    "torproject.org",

    # Pastebin-like sites used for payload hosting
    "pastebin.com",
    "paste.ee",
    "hastebin.com",
    "ghostbin.com",
    "rentry.co",

    # Free hosting often abused for malware
    "000webhostapp.com",
    "infinityfreeapp.com",
    "weeblysite.com",
    "weebly.com",
    "sites.google.com",  # used in sophisticated phishing

    # Lookalike / typosquat examples
    "g00gle.com",
    "micosoft.com",
    "paypa1.com",
    "arnazon.com",
}

_BLOCKED_IPS: set[str] = {
    # RFC 5737 test/documentation IPs (should not appear in real docs)
    # plus commonly abused infrastructure
    "192.0.2.1",
    "198.51.100.1",
    "203.0.113.1",
    # Add real C&C IPs from threat feeds here as needed
}


@dataclass
class ThreatIntelResult:
    alert: bool = False
    urls_found: list[str] = field(default_factory=list)
    ips_found: list[str] = field(default_factory=list)
    malicious_indicators: list[str] = field(default_factory=list)


def _domain_from_url(url: str) -> str:
    """Extract the hostname from a URL string."""
    try:
        # Strip scheme
        without_scheme = url.split("://", 1)[1]
        # Strip path/query
        host = without_scheme.split("/")[0].split("?")[0].split("#")[0]
        # Strip port
        host = host.split(":")[0]
        return host.lower()
    except Exception:
        return ""


def check(text: str) -> ThreatIntelResult:
    """
    Extract URLs and IPs from text and check against the local blocklist.
    Returns a ThreatIntelResult.
    """
    result = ThreatIntelResult()

    # Extract URLs
    urls = _RE_URL.findall(text)
    result.urls_found = list(set(urls))

    # Extract IPv4 addresses
    ips = _RE_IPV4.findall(text)
    result.ips_found = list(set(ips))

    # Check domains
    for url in result.urls_found:
        domain = _domain_from_url(url)
        if not domain:
            continue
        # Check exact match and subdomain match
        if domain in _BLOCKED_DOMAINS:
            result.malicious_indicators.append(f"[BLOCKED DOMAIN] {domain} in: {url[:80]}")
        else:
            # Check if it's a subdomain of a blocked domain
            for blocked in _BLOCKED_DOMAINS:
                if domain.endswith("." + blocked):
                    result.malicious_indicators.append(
                        f"[BLOCKED SUBDOMAIN] {domain} (parent: {blocked}) in: {url[:80]}"
                    )
                    break

    # Check IPs
    for ip in result.ips_found:
        if ip in _BLOCKED_IPS:
            result.malicious_indicators.append(f"[BLOCKED IP] {ip}")

    result.alert = len(result.malicious_indicators) > 0
    return result
