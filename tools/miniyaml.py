"""A small YAML reader for the subset the vLLM recipes use. Standard library only.

Supported: block maps and lists (any consistent indentation), "- key: value" list items that open a map, plain,
single- and double-quoted scalars, numbers, true/false/null, empty flow collections ([] and {}), one-line flow lists
of scalars, comments, and block scalars (| and >). Anything else raises ValueError: a recipe it cannot read is
skipped and reported, never guessed at.
"""
import re


_ANCHORS = {}


def load(text):
    _ANCHORS.clear()
    lines = []
    for raw in text.split("\n"):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lines.append((len(raw) - len(raw.lstrip(" ")), raw.strip(), raw))
    value, at = _block(lines, 0, lines[0][0] if lines else 0)
    if at != len(lines):
        raise ValueError(f"unread content near: {lines[at][1][:60]}")
    return value


def _strip_comment(s):
    """Remove a trailing ' # comment' that is outside quotes."""
    quote = None
    for i, ch in enumerate(s):
        if quote:
            if ch == quote and s[i - 1] != "\\":
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "#" and (i == 0 or s[i - 1] == " "):
            return s[:i].rstrip()
    return s


def _scalar(s):
    s = _strip_comment(s).strip()
    if s == "" or s in ("null", "~"):
        return None
    if s == "true":
        return True
    if s == "false":
        return False
    if s == "[]":
        return []
    if s == "{}":
        return {}
    if s[0] == '"':
        if s[-1] != '"' or len(s) < 2:
            raise ValueError("unterminated string: " + s[:40])
        return bytes(s[1:-1], "utf-8").decode("unicode_escape") if "\\" in s else s[1:-1]
    if s[0] == "'":
        if s[-1] != "'" or len(s) < 2:
            raise ValueError("unterminated string: " + s[:40])
        return s[1:-1].replace("''", "'")
    if s[0] == "[":
        if s[-1] != "]":
            raise ValueError("unsupported flow list: " + s[:40])
        inner = s[1:-1].strip()
        return [_scalar(p) for p in _split_flow(inner)] if inner else []
    if s[0] == "{":
        if s[-1] != "}":
            raise ValueError("unsupported flow map: " + s[:40])
        out = {}
        for part in _split_flow(s[1:-1].strip()):
            kv = _key(part)
            if kv is None:
                raise ValueError("unsupported flow map: " + s[:40])
            out[kv[0]] = _scalar(kv[1])
        return out
    if s[0] == "*":
        if s[1:] not in _ANCHORS:
            raise ValueError("unknown alias: " + s)
        import copy
        return copy.deepcopy(_ANCHORS[s[1:]])
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    if re.fullmatch(r"-?\d+\.\d+", s):
        return float(s)
    return s


def _split_flow(inner):
    parts, depth, quote, cur = [], 0, None, ""
    for ch in inner:
        if quote:
            cur += ch
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
            cur += ch
        elif ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    return [p.strip() for p in parts if p.strip()]


def _key(text):
    """Split 'key: value' at the first unquoted colon followed by a space or the end."""
    quote = None
    for i, ch in enumerate(text):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == ":" and (i + 1 == len(text) or text[i + 1] == " "):
            k = text[:i].strip()
            if k[:1] in "\"'" and k[-1:] == k[:1]:
                k = k[1:-1]
            return k, text[i + 1 :].strip()
    return None


def _block(lines, at, indent):
    first = lines[at][1]
    if first.startswith("- ") or first == "-":
        return _list(lines, at, indent)
    return _map(lines, at, indent)


def _map(lines, at, indent):
    out = {}
    while at < len(lines) and lines[at][0] == indent and not lines[at][1].startswith("- "):
        kv = _key(lines[at][1])
        if kv is None:
            raise ValueError("expected 'key: value': " + lines[at][1][:60])
        key, rest = kv
        rest = _strip_comment(rest)
        anchor = None
        if rest.startswith("&"):  # a name for this block, so it can be repeated with *name
            anchor, _, rest = rest[1:].partition(" ")
            rest = rest.strip()
        at += 1
        if rest in ("|", ">", "|-", ">-", "|+", ">+"):
            body = []
            while at < len(lines) and lines[at][0] > indent:
                body.append(lines[at][1])
                at += 1
            out[key] = ("\n" if rest[0] == "|" else " ").join(body)
        elif rest == "":
            if at < len(lines) and (lines[at][0] > indent or (lines[at][0] == indent and lines[at][1].startswith("- "))):
                out[key], at = _block(lines, at, lines[at][0])
            else:
                out[key] = None
        else:
            out[key] = _scalar(rest)
        if anchor:
            _ANCHORS[anchor] = out[key]
    return out, at


def _list(lines, at, indent):
    out = []
    while at < len(lines) and lines[at][0] == indent and (lines[at][1].startswith("- ") or lines[at][1] == "-"):
        item = lines[at][1][1:].strip()
        if item == "":
            at += 1
            if at < len(lines) and lines[at][0] > indent:
                value, at = _block(lines, at, lines[at][0])
                out.append(value)
            else:
                out.append(None)
        elif _key(item) is not None and not item.startswith(('"', "'")):
            # "- key: value" opens a map whose further keys are indented to the key's column
            col = indent + 2
            lines[at] = (col, item, lines[at][2])
            value, at = _map(lines, at, col)
            out.append(value)
        else:
            out.append(_scalar(item))
            at += 1
    return out, at
