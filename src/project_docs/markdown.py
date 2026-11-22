"""Line-oriented Markdown scanning: frontmatter offset, code blocks, comments and links.

Not a CommonMark parser: it recognizes only what the rules need and skips text it cannot
classify, so ambiguous input never produces a diagnostic.
"""

import re
from dataclasses import dataclass

_FRONTMATTER_KEY_RE = re.compile(r"^[A-Za-z_][\w.-]*[ \t]*:(?:[ \t]|$)")
# Fences may sit in list items or block quotes, so any indentation and `>` prefix is allowed.
_FENCE_OPEN_RE = re.compile(r"^[ \t>]*(`{3,}|~{3,})(.*)$")
_FENCE_CLOSE_RE = re.compile(r"^[ \t>]*(`{3,}|~{3,})[ \t]*$")
_INLINE_TOKEN_RE = re.compile(r"<!--|`+")
_BACKTICKS_RE = re.compile(r"`+")
_LABEL = r"\[((?:[^\[\]]|\[[^\[\]]*\])*)\]"
_TITLE = r"""(?:[ \t]+(?:"[^"]*"|'[^']*'|\([^()]*\)))?"""
_INLINE_LINK_RE = re.compile(
    _LABEL + r"\(\s*(<[^<>]*>|(?:[^()\s]|\([^()\s]*\))+)" + _TITLE + r"\s*\)"
)
_REF_DEF_RE = re.compile(r"^ {0,3}\[([^\]^][^\]]*)\]:[ \t]*(<[^<>]*>|\S+)" + _TITLE + r"[ \t]*$")
_REF_USE_RE = re.compile(_LABEL + r"\[([^\[\]]*)\]")
_HREF_RE = re.compile(r"""<a\s[^>]*?\bhref\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.IGNORECASE)
_IMPORT_RE = re.compile(r"(?<!\S)@([^\s`'\"<>()\[\]]+)")


@dataclass(frozen=True)
class Link:
    """A link occurrence on one line.

    Attributes:
        line: 1-based line number.
        kind: ``inline``, ``ref_def``, ``ref_use``, ``html`` or ``import`` (``@path``).
        target: Raw link destination.
        start: Column where the link syntax starts.
        end: Column just past the link syntax.
        in_code: Whether the line belongs to an indented code block.
    """

    line: int
    kind: str
    target: str
    start: int
    end: int
    in_code: bool


@dataclass
class Parsed:
    """Scan result for one document.

    Attributes:
        body_start: 0-based index of the first body line (after any frontmatter).
        body: ``(line_no, text, in_code)`` per body line. ``text`` is None for fenced
            code (including fence lines); otherwise it is the raw line with code spans
            and HTML comments blanked to spaces, so columns match the raw line.
        links: Links found in non-fenced body lines.
    """

    body_start: int
    body: list[tuple[int, str | None, bool]]
    links: list[Link]


def frontmatter_end(lines: list[str]) -> int:
    """Return the index of the first body line after top-of-file YAML frontmatter.

    The block counts as frontmatter only if it holds at least one top-level
    ``key: value`` line; ``# ...`` lines inside it are YAML comments. Without any key,
    the opening ``---`` is a thematic break and the body starts at line 1.

    Args:
        lines: Document lines without line terminators.

    Returns:
        0-based index of the first body line.
    """
    if not lines or lines[0].rstrip() != "---":
        return 0
    end = next((i for i in range(1, len(lines)) if lines[i].rstrip() in ("---", "...")), None)
    if end is None or not any(_FRONTMATTER_KEY_RE.match(raw) for raw in lines[1:end]):
        return 0
    return end + 1


def _blank_inline(line: str, in_comment: bool) -> tuple[str, bool]:
    """Blank HTML comments and code spans in one left-to-right pass.

    Backticks inside a comment and ``<!--`` inside a code span are literal text. An
    unclosed comment carries over to the next line.
    """
    chars = list(line)
    pos = 0
    while True:
        if in_comment:
            end = line.find("-->", pos)
            stop = len(line) if end == -1 else end + 3
            chars[pos:stop] = " " * (stop - pos)
            if end == -1:
                return "".join(chars), True
            pos, in_comment = stop, False
        token = _INLINE_TOKEN_RE.search(line, pos)
        if token is None:
            return "".join(chars), False
        if token.group() == "<!--":
            chars[token.start() : token.end()] = "    "
            pos, in_comment = token.end(), True
            continue
        width = token.end() - token.start()
        closing = next(
            (m for m in _BACKTICKS_RE.finditer(line, token.end()) if m.end() - m.start() == width),
            None,
        )
        if closing is None:
            pos = token.end()
        else:
            chars[token.start() : closing.end()] = " " * (closing.end() - token.start())
            pos = closing.end()


def _indent(line: str) -> int:
    expanded = line.expandtabs(4)
    return len(expanded) - len(expanded.lstrip())


def _label_key(label: str) -> str:
    return " ".join(label.split()).casefold()


def parse(lines: list[str]) -> Parsed:
    """Scan a Markdown document.

    Fences may be indented or quoted and close only with the same character, at least
    the same length and no info string. Otherwise, a line indented by four or more
    spaces is indented code when the previous line is blank or is itself indented
    code; list context is not tracked.

    Args:
        lines: Document lines without line terminators (BOM already removed).

    Returns:
        Body offset, per-line body text and extracted links.
    """
    body_start = frontmatter_end(lines)
    body: list[tuple[int, str | None, bool]] = []
    fence: tuple[str, int] | None = None
    in_comment = False
    prev_blank, prev_code = True, False
    for idx in range(body_start, len(lines)):
        raw = lines[idx]
        if fence is not None:
            close = _FENCE_CLOSE_RE.match(raw)
            if close and close.group(1)[0] == fence[0] and len(close.group(1)) >= fence[1]:
                fence = None
            body.append((idx + 1, None, False))
            prev_blank, prev_code = False, False
            continue
        opening = None if in_comment else _FENCE_OPEN_RE.match(raw)
        if opening and not (opening.group(1)[0] == "`" and "`" in opening.group(2)):
            fence = (opening.group(1)[0], len(opening.group(1)))
            body.append((idx + 1, None, False))
            prev_blank, prev_code = False, False
            continue
        blank = not raw.strip()
        in_code = not in_comment and not blank and _indent(raw) >= 4 and (prev_blank or prev_code)
        if in_code:
            text = _blank_inline(raw, False)[0]
        else:
            text, in_comment = _blank_inline(raw, in_comment)
        body.append((idx + 1, text, in_code))
        prev_blank, prev_code = blank, in_code
    return Parsed(body_start, body, _extract_links(body))


def _extract_links(body: list[tuple[int, str | None, bool]]) -> list[Link]:
    prose = [(no, text, code) for no, text, code in body if text is not None]
    defs: dict[str, str] = {}
    links: list[Link] = []
    for no, text, code in prose:
        ref_def = _REF_DEF_RE.match(text)
        if ref_def is not None:
            defs.setdefault(_label_key(ref_def.group(1)), ref_def.group(2))
            links.append(Link(no, "ref_def", ref_def.group(2), 0, ref_def.end(), code))
            continue
        for m in _INLINE_LINK_RE.finditer(text):
            links.append(Link(no, "inline", m.group(2), m.start(), m.end(), code))
        for m in _HREF_RE.finditer(text):
            href = m.group(1) if m.group(1) is not None else m.group(2)
            links.append(Link(no, "html", href, m.start(), m.end(), code))
        for m in _IMPORT_RE.finditer(text):
            target = m.group(1).rstrip(".,;:!?")
            if "/" in target or target.lower().endswith(".md"):
                links.append(Link(no, "import", target, m.start(), m.end(), code))
    for no, text, code in prose:
        for m in _REF_USE_RE.finditer(text):
            key = _label_key(m.group(2) or m.group(1))
            if key in defs:
                links.append(Link(no, "ref_use", defs[key], m.start(), m.end(), code))
    links.sort(key=lambda link: (link.line, link.start))
    return links
