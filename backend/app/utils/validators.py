import re
import unicodedata

_ALLOWED = re.compile(r"^[A-Z0-9.\-]{1,15}$")

def normalize_ticker(raw: str) -> str:
    s = unicodedata.normalize("NFKC", str(raw or ""))
    s = s.replace("\u00A0", " ").strip()           # remove NBSP, trim
    s = "".join(ch for ch in s if not ch.isspace())# remove ALL spaces
    return s.upper()

def validate_ticker(raw: str) -> str:
    t = normalize_ticker(raw)
    if not _ALLOWED.match(t):
        raise ValueError("Invalid ticker format.")
    return t
