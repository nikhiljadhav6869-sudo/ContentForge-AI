"""Bounded document ingestion. HTTPS retrieval pins validated public DNS addresses."""

import hashlib
import http.client
import ipaddress
import socket
import ssl
from urllib.parse import urlsplit, urljoin
from bs4 import BeautifulSoup
from .config import settings
from .db import SourceDocument, SourcePassage

MAX_BYTES = 2 * 1024 * 1024
DEMO_SOURCES = [
    (
        "EV fundamentals · sample reference",
        "Battery electric vehicles produce no tailpipe emissions.\n\nElectric vehicles are not emission-free across their entire lifecycle. Manufacturing and electricity generation contribute to lifecycle emissions.\n\nCharging availability and electricity sources should be considered when evaluating electric vehicles.",
    ),
    (
        "India campaign brief · sample reference",
        "This educational campaign is intended for Indian college students.\n\nBattery electric vehicles produce no tailpipe emissions.\n\nPurchase price, access to charging, battery warranty and daily travel needs are useful comparison criteria. No nationwide cost or range statistic is provided in this sample document.",
    ),
]


def store_source(db, workspace_id, title, text, kind="text", url=""):
    text = text.replace("\x00", "").strip()[:100000]
    if len(text) < 20:
        raise ValueError("The document contains too little extractable text.")
    source = SourceDocument(
        workspace_id=workspace_id,
        title=title[:200],
        text=text,
        kind=kind,
        url=url,
        credibility="Illustrative sample reference; not independently verified"
        if kind == "demo"
        else "Source provenance stored; credibility not independently assessed",
        content_hash=hashlib.sha256(text.encode()).hexdigest(),
    )
    db.add(source)
    db.flush()
    for i in range(0, len(text), 1200):
        db.add(SourcePassage(source_id=source.id, text=text[i : i + 1200], ordinal=i // 1200))
    return source


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host, ip):
        super().__init__(host, timeout=12, context=ssl.create_default_context())
        self.ip = ip

    def connect(self):
        self.sock = self._context.wrap_socket(
            socket.create_connection((self.ip, 443), self.timeout), server_hostname=self.host
        )


def fetch_url(url):
    allowed = {h.strip() for h in settings.source_hosts.split(",") if h.strip()}
    for _ in range(4):
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.username
            or parsed.password
            or parsed.port not in (None, 443)
            or parsed.hostname not in allowed
        ):
            raise ValueError(
                "Use an HTTPS source on a server-approved source domain. Add trusted hosts in SOURCE_HOSTS."
            )
        addresses = {r[4][0] for r in socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)}
        if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
            raise ValueError("Private and reserved network destinations are blocked.")
        connection = PinnedHTTPSConnection(parsed.hostname, sorted(addresses)[0])
        try:
            connection.request(
                "GET",
                (parsed.path or "/") + ("?" + parsed.query if parsed.query else ""),
                headers={"User-Agent": "ContentForge/1.0 source reader", "Accept": "text/html,text/plain"},
            )
            response = connection.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                url = urljoin(url, response.getheader("Location", ""))
                continue
            if response.status != 200:
                raise ValueError(f"Source returned HTTP {response.status}.")
            mime = response.getheader("Content-Type", "").lower()
            if not any(x in mime for x in ("text/html", "text/plain")):
                raise ValueError("Only HTML and plain text URLs are supported. Upload PDFs separately.")
            raw = response.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise ValueError("Source exceeds the 2 MB limit.")
            soup = BeautifulSoup(raw, "html.parser")
            title = soup.title.get_text(" ", strip=True) if soup.title else parsed.hostname
            for element in soup(["script", "style", "nav", "footer", "header"]):
                element.decompose()
            return title, soup.get_text(" ", strip=True), url
        finally:
            connection.close()
    raise ValueError("Too many source redirects.")
