"""Beskriver en JSON-struktur uden at afsloere indholdet.

Bruges til at kortlaegge blankettens felter forud for mapningen. En indsendelse
indeholder borgerens navn, adresse, telefonnummer og mailadresse, men til
mapningen skal der kun bruges feltnavne, typer og indlejring. Denne modul
udskriver netop det, saa kortlaegningen kan deles uden at persondata foelger med.
"""

import re
from typing import Any

# Feltnavne der ALTID maskeres. Vinder over SAFE_VALUE_HINTS nedenfor, saa et
# felt som "vaelg_adresse" maskeres selvom det starter med "vaelg_".
SENSITIVE_HINTS = (
    "adresse", "addr", "vej", "by", "postnr", "postal", "zip",
    "navn", "name", "udfylder", "kontakt", "person", "ejer",
    "mail", "email", "tlf", "telefon", "phone", "mobil",
    "cpr", "cvr", "matr", "mat", "lokalitet", "ejendom", "grund",
    "firma", "company", "virksomhed",
    "bemaerk", "kommentar", "comment", "beskriv", "tekst", "note",
)

# Praefikser der markerer et spoergsmaalsfelt. Svaret er en kategori — "Ja",
# "Nej", en rolle — og ikke persondata, saa det vises selvom feltnavnet
# indeholder et ord fra spaerrelisten. Uden denne undtagelse ville
# "er_udfylder_grundejer_raadgiver_eller_andet" blive maskeret, og netop det
# felt afgoer hvilke valgmuligheder SharePoint-kolonnen skal have.
QUESTION_PREFIXES = ("er_", "har_", "oensker_", "skal_", "vil_", "hvilken_type", "type_")

# Feltnavne hvor vaerdien typisk er en kategori og ikke persondata.
SAFE_VALUE_HINTS = ("rolle", "status", "kategori")

# Laengste vaerdi der vises for et felt der ligner en valgmulighed.
MAX_CHOICE_LENGTH = 40

# Formater der beskrives frem for at vises. Til mapningen er det formatet der
# betyder noget — ikke selve datoen.
FORMATS = (
    (re.compile(r"^\d{4}-\d{2}-\d{2}$"), "dato YYYY-MM-DD"),
    (re.compile(r"^\d{2}:\d{2}:\d{2}$"), "klokkeslaet HH:MM:SS"),
    (re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}"), "tidsstempel ISO8601"),
    (re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-"), "uuid"),
    (re.compile(r"^https?://"), "url"),
)


def describe_structure(value: Any, path: str = "", show_values: bool = False, depth: int = 0) -> list[str]:
    """Beskriver en JSON-struktur som linjer, med vaerdierne udeladt.

    Args:
        value: Den JSON-vaerdi der skal beskrives.
        path: Navnet paa den aktuelle noegle. Tom for roden.
        show_values: Tag de faktiske vaerdier med. Indeholder persondata.
        depth: Indrykningsniveau. Saettes af rekursionen.

    Returns:
        En linje pr. felt, indrykket efter indlejring.
    """
    indent = "  " * depth
    lines = []

    if isinstance(value, dict):
        lines.append(f"{indent}{path or '(rod)'}  dict[{len(value)}]")
        for key, item in value.items():
            lines.extend(describe_structure(item, key, show_values, depth + 1))

    elif isinstance(value, list):
        lines.append(f"{indent}{path}  list[{len(value)}]")
        # Kun foerste element beskrives — resten har samme facon.
        if value:
            lines.extend(describe_structure(value[0], "[0]", show_values, depth + 1))

    else:
        lines.append(f"{indent}{path}  {describe_scalar(path, value, show_values)}")

    return lines


def is_sensitive(path: str) -> bool:
    """Afgoer om et feltnavn peger paa persondata, der altid skal maskeres."""
    return any(hint in path.lower() for hint in SENSITIVE_HINTS)


def is_question(path: str) -> bool:
    """Afgoer om feltet er et spoergsmaal, hvis svar er en kategori."""
    return path.lower().startswith(QUESTION_PREFIXES)


def describe_scalar(path: str, value: Any, show_values: bool = False) -> str:
    """Beskriver en enkelt vaerdi — som regel uden at afsloere den."""
    type_name = type(value).__name__

    if value is None:
        return "null"
    if isinstance(value, bool):
        return f"bool = {value}"
    if isinstance(value, (int, float)):
        # Tal kan ogsaa vaere persondata — et husnummer, et telefonnummer.
        if is_sensitive(path) and not show_values:
            return f"{type_name} (maskeret)"
        return f"{type_name} = {value}"

    return _describe_text(path, str(value), type_name, show_values)


def _describe_text(path: str, text: str, type_name: str, show_values: bool) -> str:
    """Beskriver en tekstvaerdi."""
    if not text:
        return f"{type_name} (tom)"

    # Kendte formater beskrives frem for at vises. Det er formatet mapningen
    # skal bruge — om datoen er "2026-09-01" eller et ISO-tidsstempel afgoer
    # hvordan den skal konverteres til UTC.
    known_format = _detect_format(text)
    if known_format and not show_values:
        return f"{type_name} ({known_format})"

    # Spoergsmaalsfelter vises selvom navnet indeholder et spaerret ord — svaret
    # er en kategori, ikke en oplysning om borgeren. Derfor gaar de forud for
    # spaerrelisten nedenfor.
    short = len(text) <= MAX_CHOICE_LENGTH
    reveal = show_values or (short and (is_question(path) or _is_category(path)))
    if reveal:
        return f'{type_name} = "{text}"'

    masked = " (maskeret," if is_sensitive(path) else " ("
    return f"{type_name}{masked} laengde {len(text)})"


def _detect_format(text: str) -> str | None:
    """Genkender kendte vaerdiformater, saa de kan beskrives frem for vises."""
    for pattern, label in FORMATS:
        if pattern.match(text):
            return label
    return None


def _is_category(path: str) -> bool:
    """Afgoer om feltet baerer en kategori, der ikke er persondata."""
    return (
        any(hint in path.lower() for hint in SAFE_VALUE_HINTS)
        and not is_sensitive(path)
    )
