"""Checks an answer against the evidence it was given, without another language model."""

import re
from functools import lru_cache

from app.services.text_utils import normalize_name

_NUMBER = re.compile(r"(?<![\w.])\d+(?:,\d{3})*(?:\.\d+)?")
_CITATION = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")
_SEASON = re.compile(r"\b\d{4}[-–]\d{2}\b")


def _numbers(value: str) -> list[str]:
    return [n.replace(",", "") for n in _NUMBER.findall(_SEASON.sub(" ", value))]


def citations(answer: str) -> list[int]:
    return sorted({int(n) for group in _CITATION.findall(answer) for n in group.split(",")})


def _supported(number: str, evidence: list[str]) -> bool:
    """Equal, or the evidence rounded to the precision the answer used ("27" for 26.8)."""
    places = len(number.partition(".")[2])
    return any(abs(float(number) - float(e)) <= 0.5 * 10 ** -places + 1e-9 if places < len(e.partition(".")[2]) else float(number) == float(e) for e in evidence)


_NUMBERING = re.compile(r"(?m)^\s*\d+[.)]\s|(?<![\d.])\b\d{1,2}\.\s(?=[A-Z])")  # "1. Jokić", also inside a line


@lru_cache(maxsize=4)
def _patterns(names: tuple[str, ...]) -> list[tuple[str, re.Pattern]]:
    """Full names, and surnames that belong to one name only ("Jokić" for Nikola Jokić)."""
    plain = [(n, normalize_name(n)) for n in names if n]
    last = {}
    for n, p in plain:
        last.setdefault(p.split()[-1], []).append(n)
    out = [(n, re.compile(rf"(?<!\w){re.escape(p)}(?!\w)")) for n, p in plain]
    out += [(owners[0], re.compile(rf"(?<!\w){re.escape(word)}(?!\w)")) for word, owners in last.items() if len(owners) == 1 and len(word) >= 4]
    return out


def attributed(text: str, names: tuple[str, ...]) -> list[tuple[str | None, str]]:
    """Each number with the player or team named last before it ("Giannis Antetokounmpo 30.4, Nikola Jokić 29.6")."""
    plain = normalize_name(_SEASON.sub(" ", text))
    marks = [(m.start(), 0, name) for name, rx in _patterns(names) for m in rx.finditer(plain)]
    marks += [(m.start(), 1, m.group().replace(",", "")) for m in _NUMBER.finditer(plain)]
    out, current = [], None
    for _, kind, value in sorted(marks):
        if kind == 0:
            current = value
        else:
            out.append((current, value))
    return out


def lead(text: str, names: tuple[str, ...]) -> tuple[str | None, str | None]:
    """The first player or team named, and the first number given, to compare two answers."""
    pairs = attributed(_NUMBERING.sub(" ", _CITATION.sub(" ", text)), names)
    plain = normalize_name(text)
    found = [(m.start(), name) for name, rx in _patterns(names) for m in [rx.search(plain)] if m]
    return (min(found)[1] if found else None), next((n for _, n in pairs), None)


def misattributed(answer: str, contents: list[str], names: tuple[str, ...]) -> list[str]:
    """A number the sources give to someone else, and never to the one the answer gives it to.

    Only these count: a number found nowhere is "unsupported" instead, and one that a source also
    states without a name, or for the same player or team, is not flagged. Small whole numbers
    (ranks, counts below 10) are left out, since they belong to many people at once.
    """
    if not names:
        return []
    evidence = [pair for content in contents for pair in attributed(content, names)]
    body = _NUMBERING.sub(" ", _CITATION.sub(" ", answer))
    flagged = []
    for owner, number in attributed(body, names):
        if owner is None or ("." not in number and float(number) < 10):
            continue
        holders = {who for who, n in evidence if _supported(number, [n])}
        if holders and owner not in holders and None not in holders:
            flagged.append(f"{number} ({owner})")
    return list(dict.fromkeys(flagged))


def check(answer: str, question: str, contents: list[str], names: tuple[str, ...] = ()) -> dict:
    """Numbers that appear in no source, numbers given to the wrong player or team, and citations that point at no source."""
    body = _CITATION.sub(" ", answer)
    body = re.sub(r"(?m)^\s*\d+[.)]\s", " ", body)  # list numbering
    evidence = _numbers(" ".join(contents))
    asked = _numbers(question)
    used = list(dict.fromkeys(_numbers(body)))
    unsupported = [n for n in used if n not in asked and not _supported(n, evidence)]
    wrong_owner = misattributed(answer, contents, names)
    cited = citations(answer)
    return {
        "numbers": len(used),
        "unsupported_numbers": unsupported,
        "misattributed": wrong_owner,
        "cited": [c for c in cited if 1 <= c <= len(contents)],
        "invalid_citations": [c for c in cited if not 1 <= c <= len(contents)],
        "grounded": not unsupported and not wrong_owner and not [c for c in cited if not 1 <= c <= len(contents)],
    }
