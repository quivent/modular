"""Reading the world: release feeds, webhooks, and the model scan. Nothing here edits a file."""
import hashlib, hmac, json, urllib.parse, urllib.request
import xml.etree.ElementTree as ET

ATOM = "{http://www.w3.org/2005/Atom}"


def get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "modular-librarian"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def releases(repo, fetch=get):
    """Newest-first release tags of a GitHub repository, from its public Atom feed.

    The tag comes from the entry's link (titles carry a description). Pre-releases count: some projects
    publish nothing else, and how often an engine is re-read is the cooldown's job.
    """
    root = ET.fromstring(fetch(f"https://github.com/{repo}/releases.atom"))
    tags = []
    for e in root.findall(ATOM + "entry"):
        href = (e.find(ATOM + "link").get("href") if e.find(ATOM + "link") is not None else "") or ""
        tag = href.rsplit("/releases/tag/", 1)[-1] if "/releases/tag/" in href else (e.findtext(ATOM + "title") or "").strip()
        if tag:
            tags.append(urllib.parse.unquote(tag))
    return tags


def from_webhook(payload, beat):
    """A GitHub `release` webhook, as an event. None if it is not a published, final release of something we watch."""
    if payload.get("action") not in ("published", "released") or not payload.get("release"):
        return None
    if payload["release"].get("draft"):
        return None
    repo = (payload.get("repository") or {}).get("full_name", "").lower()
    for engine, spec in beat["engines"].items():
        if spec["repo"].lower() == repo:
            return {"engine": engine, "release": payload["release"].get("tag_name")}
    return None


def signed(secret, body, header):
    """True when a webhook body carries the right GitHub signature for the shared secret."""
    want = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(want, header or "")
