"""Tests for src/struktur.py — redaktionen af blankettens struktur.

Daekker saerligt de to sikkerhedshuller der er rettet:

1. Et spoergsmaalsfelt (praefiks "er_"/"har_"/...) hvis navn OGSAA rammer
   SENSITIVE_HINTS skal stadig maskeres — praefikset alene beviser ikke at
   svaret er en kategori og ikke fri tekst.
2. Numeriske felter maskeres som udgangspunkt, uanset navn, og vises kun via
   den eksplicitte tilladelsesliste (ALLOWED_FIELDS) eller show_values.
3. "postnummer" rammes af SENSITIVE_HINTS (stammen "postnr" er ikke en
   delstreng af "postnummer").
"""

from src.struktur import ALLOWED_FIELDS, describe_scalar, describe_structure, is_sensitive


# --- 1. Spoergsmaalspraefiks + sensitivt navn -> maskeret ---

def test_question_prefixed_field_that_is_also_sensitive_is_masked():
    # "har_du_en_anden_adresse" starter med praefikset "har_", men indeholder
    # ogsaa "adresse" — et SENSITIVE_HINT. Foer rettelsen blev vaerdien vist,
    # fordi is_question() ikke tjekkede is_sensitive().
    path = "har_du_en_anden_adresse"
    assert is_sensitive(path)  # forudsaetning for testen

    result = describe_scalar(path, "Solsortevej 4", show_values=False)

    assert "Solsortevej 4" not in result
    assert "maskeret" in result


def test_question_prefixed_field_that_is_not_sensitive_is_still_shown():
    # Modstykket: et rent kategori-spoergsmaal uden noget spaerret ord i
    # navnet skal fortsat vises — det er selve pointen med QUESTION_PREFIXES.
    result = describe_scalar("skal_projektet_anmeldes", "Ja", show_values=False)

    assert result == 'str = "Ja"'


# --- 2. Tilladelseslisten ---

def test_allowlisted_field_is_shown_even_though_name_looks_sensitive():
    # "er_udfylder_grundejer_raadgiver_bygherre_eller_andet" indeholder
    # "udfylder" (SENSITIVE_HINT), men staar eksplicit paa ALLOWED_FIELDS
    # fordi det er verificeret som et rene kategori-svar.
    path = "er_udfylder_grundejer_raadgiver_bygherre_eller_andet"
    assert path in ALLOWED_FIELDS
    assert is_sensitive(path)  # ville ellers vaere maskeret

    result = describe_scalar(path, "Raadgiver", show_values=False)

    assert result == 'str = "Raadgiver"'


def test_second_allowlisted_field_is_shown():
    result = describe_scalar("ansoegning_indsendt_af", "Grundejer", show_values=False)

    assert result == 'str = "Grundejer"'


def test_field_not_on_allowlist_with_sensitive_name_stays_masked():
    # Sikrer at ALLOWED_FIELDS er opt-in — et vilkaarligt andet felt med
    # "udfylder" i navnet maa ikke automatisk blive vist.
    result = describe_scalar("udfylder_kommentar", "Fri tekst med detaljer", show_values=False)

    assert "Fri tekst med detaljer" not in result
    assert "maskeret" in result


# --- 3. Numeriske felter maskeres som udgangspunkt ---

def test_numeric_field_not_on_allowlist_is_masked():
    # Foer rettelsen blev tal kun maskeret naar navnet var paa spaerrelisten —
    # et frit navngivet felt som "telefon_privat" (int) blev vist i klartekst.
    result = describe_scalar("telefon_privat", 12345678, show_values=False)

    assert "12345678" not in result
    assert "maskeret" in result


def test_numeric_field_with_innocuous_name_is_also_masked_by_default():
    # Ogsaa et tal hvis navn slet ikke rammer SENSITIVE_HINTS maskeres nu som
    # udgangspunkt — kun ALLOWED_FIELDS eller show_values afdaekker det.
    result = describe_scalar("antal_skabe", 3, show_values=False)

    assert result == "int (maskeret)"


def test_numeric_field_is_shown_with_show_values():
    result = describe_scalar("husnummer", 42, show_values=True)

    assert result == "int = 42"


# --- 4. postnummer rammes af SENSITIVE_HINTS ---

def test_postnummer_field_is_masked():
    # "postnr" er ikke en delstreng af "postnummer" — det praecise felt
    # blanketten bruger. Uden "postnummer" i SENSITIVE_HINTS ville feltet
    # ikke blive genkendt som persondata.
    path = "postnummer"
    assert is_sensitive(path)

    result = describe_scalar(path, "8000", show_values=False)

    assert "8000" not in result
    assert "maskeret" in result


def test_postnr_field_is_also_masked():
    # Den oprindelige stamme skal fortsat virke for felter der rent faktisk
    # hedder "postnr" eller indeholder det.
    assert is_sensitive("vaelg_postnr")


# --- Grundlaeggende opfoersel (regression) ---

def test_describe_structure_never_leaks_values_without_show_values():
    submission = {
        "data": {
            "udfylder_navn": "Anders And",
            "udfylder_mail": "anders@andeby.dk",
            "er_udfylder_grundejer_raadgiver_bygherre_eller_andet": "Raadgiver",
            "vaelg_dato_for_ansoegning": "2026-01-15",
            "adresser": [
                {"vaelg_adresse": "Andebyvej 1, 9999 Andeby", "postnummer": "9999"}
            ],
        }
    }

    lines = describe_structure(submission, show_values=False)
    text = "\n".join(lines)

    assert "Anders And" not in text
    assert "anders@andeby.dk" not in text
    assert "Andebyvej 1" not in text
    assert "9999" not in text
    # Men kategori-svaret paa tilladelseslisten er der stadig, netop fordi
    # mapningen har brug for det:
    assert 'Raadgiver' in text


def test_describe_structure_reveals_everything_with_show_values():
    submission = {"udfylder_navn": "Anders And"}

    lines = describe_structure(submission, show_values=True)

    assert any("Anders And" in line for line in lines)


def test_empty_string_is_described_without_masking_noise():
    assert describe_scalar("udfylder_navn", "", show_values=False) == "str (tom)"


def test_known_date_format_is_described_not_shown():
    result = describe_scalar("nogen_dato", "2026-01-15", show_values=False)
    assert result == "str (dato YYYY-MM-DD)"
