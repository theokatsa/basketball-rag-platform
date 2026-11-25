"""Checks an answer against the evidence it was given, without another language model."""

import re

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


def check(answer: str, question: str, contents: list[str]) -> dict:
    """Numbers that appear in no source, and citations that point at no source."""
    body = _CITATION.sub(" ", answer)
    body = re.sub(r"(?m)^\s*\d+[.)]\s", " ", body)  # list numbering
    evidence = _numbers(" ".join(contents))
    asked = _numbers(question)
    used = list(dict.fromkeys(_numbers(body)))
    unsupported = [n for n in used if n not in asked and not _supported(n, evidence)]
    cited = citations(answer)
    return {
        "numbers": len(used),
        "unsupported_numbers": unsupported,
        "cited": [c for c in cited if 1 <= c <= len(contents)],
        "invalid_citations": [c for c in cited if not 1 <= c <= len(contents)],
        "grounded": not unsupported and not [c for c in cited if not 1 <= c <= len(contents)],
    }
