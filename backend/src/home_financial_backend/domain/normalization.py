import unicodedata


def normalize_text(value: str | None) -> str:
    if value is None:
        return ""
    decomposed = unicodedata.normalize("NFKD", value.strip().casefold())
    without_marks = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(without_marks.split())
