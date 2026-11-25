import unicodedata


def normalize_name(value: str) -> str:
    """Lower-case and strip accents, so "Jokic" finds "Jokić"."""
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower().strip()
