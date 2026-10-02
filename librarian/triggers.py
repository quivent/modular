"""What wakes the librarian. Every trigger ends up as the same thing: an event naming an engine to re-read.

  release   an engine's repository published a new release (its Atom feed, or a GitHub webhook)
  page      a documentation page the extractor reads has changed (a conditional request, then a content hash)
  models    Hugging Face reports a model changed (its webhook), or the daily scan is due

The pages to watch are not listed anywhere by hand: the extractor records the pages it read in each data file.
"""
import datetime as dt

from . import feeds


def sources_of(lib, engine):
    """The pages that produced an engine's data."""
    try:
        data = lib.load(engine)
    except Exception:
        return []
    return data.get("sources") or [data["source"]]


def cooling(lib, beat, engine, now=None):
    last = lib.state()["ran"].get(engine)
    hours = beat["engines"][engine].get("cooldown_hours", beat.get("default_cooldown_hours", 24))
    if not last:
        return False
    return (now or dt.datetime.now()) - dt.datetime.fromisoformat(last) < dt.timedelta(hours=hours)


def poll(lib, beat, fetch=feeds.get, probe=feeds.probe, now=None):
    """Look at every engine's release feed and documentation pages; return the engines that need re-reading."""
    state = lib.state()
    events = []
    for engine, spec in beat["engines"].items():
        if cooling(lib, beat, engine, now):
            continue
        release, changed, fingerprints = None, False, {}
        try:
            tags = feeds.releases(spec["repo"], fetch)
            release = tags[0] if tags else None
        except Exception as e:
            lib.note(kind="feed-error", engine=engine, error=str(e)[:200])
        for url in sources_of(lib, engine):
            try:
                moved, fp = probe(url, state["fingerprints"].get(url) or {})
            except Exception as e:
                lib.note(kind="page-error", engine=engine, url=url, error=str(e)[:200])
                continue
            changed = changed or moved
            fingerprints[url] = fp
        if release and release != state["seen"].get(engine):
            events.append({"engine": engine, "release": release, "why": "release", "fingerprints": fingerprints})
        elif changed:
            events.append({"engine": engine, "release": None, "why": "page", "fingerprints": fingerprints})
    return events


def process(lib, events, log=print):
    """Hand events to the desk. A page's fingerprint is kept once the read it caused has been dealt with."""
    for e in events:
        result = lib.handle(e["engine"], e.get("release"))
        log(result["said"])
        if result["outcome"] not in ("deferred", "unreadable"):
            lib.remember(e.get("fingerprints") or {})


def models_due(lib, hours):
    ran = lib.state()["models"].get("ran", "")
    return ran < (dt.datetime.now() - dt.timedelta(hours=hours)).isoformat()


def facts_due(lib, hours=24):
    ran = lib.state()["facts"].get("ran", "")
    return ran < (dt.datetime.now() - dt.timedelta(hours=hours)).isoformat()
