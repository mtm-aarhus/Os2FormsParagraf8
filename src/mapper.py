"""Mapning fra OS2Forms-indsendelse til SharePoint-raekker.

Skrevet ud fra en faktisk testindsendelse fra den nuvaerende blanket
(serienummer 75, 23/09/2026). Feltnavnene herunder er blankettens, ikke den
gamle Flask-webhooks — blanketten blev lavet markant om, og den gamle mapning i
app.py gaelder ikke laengere.

Kolonnenavnene paa hoejre side skal matche SHAREPOINT-LISTER.md praecist.

To uregelmaessigheder i blanketten, som koden er noedt til at leve med:

- 'e_mail__byg' har dobbelt underscore, i modsaetning til 'e_mail_2' og
  'e_mail_raad'. Formentlig en tastefejl i blanketopbygningen, men det er det
  faktiske feltnavn — se FIELD_NAME_EXCEPTIONS.
- 'navn_kontaktperson_2' findes ikke. Grundejer nr. 2 har adresse, CVR, firma,
  mail og telefon, men intet navnefelt.
"""

import logging
from typing import Any, Optional

from src.datoer import local_to_sharepoint_utc, unix_to_sharepoint_utc

logger = logging.getLogger(__name__)

# SharePoint-kolonne -> feltnavn i blanketten, uden suffiks.
CONTACT_FIELDS = {
    "Navn": "navn_kontaktperson",
    "Firma": "evt_firma",
    "CVR": "cvr",
    "Email": "e_mail",
    "Telefon": "telefon_nr",
    "Adresse": "adresse",
}

# Felter der ikke foelger moensteret basisnavn + suffiks.
FIELD_NAME_EXCEPTIONS = {
    ("e_mail", "_byg"): "e_mail__byg",
}

# Blanketten er flad: hver part har sit eget suffiks.
CONTACT_GROUPS = (
    ("", "Grundejer"),
    ("_2", "Grundejer"),
    ("_byg", "Bygherre"),
    ("_raad", "Rådgiver"),
)

# Sti til en indsendelse i OS2Forms' administration, saa sagsbehandleren kan se
# originalen. Udfyldes med sid.
SUBMISSION_URL = "https://selvbetjening.aarhuskommune.dk/admin/structure/webform/submission/{sid}"


def map_submission(submission: dict[str, Any]) -> tuple[dict, list[dict], list[dict], list[dict]]:
    """Oversaetter én OS2Forms-indsendelse til raekker i de fire SharePoint-lister.

    Args:
        submission: Raa JSON fra `/webform_rest/{webform_id}/submission/{uuid}`.

    Returns:
        Fire dele, i denne raekkefoelge:
            ansogning:      felter til P8Ansogninger (én raekke)
            adresser:       felter til P8Adresser (nul eller flere)
            kontakter:      felter til P8Kontakter (nul eller flere)
            vedhaeftninger: felter til P8Vedhaeftninger (nul eller flere)
    """
    data = submission.get("data") or {}

    adresser = _map_adresser(data)
    kontakter = _map_kontakter(data)
    vedhaeftninger = _map_vedhaeftninger(data)
    ansogning = _map_ansogning(submission, data, adresser, kontakter, vedhaeftninger)

    return ansogning, adresser, kontakter, vedhaeftninger


# --- Hovedliste ---

def _map_ansogning(submission: dict, data: dict, adresser: list[dict],
                   kontakter: list[dict], vedhaeftninger: list[dict]) -> dict:
    """Bygger raekken til P8Ansogninger."""
    sid = _meta(submission, "sid")

    # Falder tilbage til firmaet, da grundejer nr. 2 ingen navnefelt har i
    # blanketten. Uden det ville opsummeringen vise én ejer hvor der er to.
    grundejere = [
        k["Navn"] or k["Firma"]
        for k in kontakter
        if k["KontaktType"] == "Grundejer" and (k.get("Navn") or k.get("Firma"))
    ]

    return {
        "Title": _build_title(adresser, _meta(submission, "serial")),
        "SubmissionUUID": _meta(submission, "uuid"),
        "SubmissionSerial": _as_int(_meta(submission, "serial")),
        "SubmissionSid": _as_int(sid),
        "OS2FormsUrl": SUBMISSION_URL.format(sid=sid) if sid else None,

        "Udfylder": data.get("udfylder"),
        "IndsendtAf": data.get("ansoegning_indsendt_af"),
        "AnsogningsDato": _map_form_date(data.get("vaelg_dato_for_ansoegning")),
        "Bemaerkninger": data.get("bemaerkninger"),

        "ModtagetDato": unix_to_sharepoint_utc(_meta(submission, "created")),
        "AfsluttetDato": unix_to_sharepoint_utc(_meta(submission, "completed")),

        "FlereGrundejere": _is_yes(data.get("er_der_flere_grundejere")),
        "BygherreSammeSomGrundejer": _is_yes(data.get("er_bygherre_den_samme_som_grundejer")),

        # Sagsbehandlerens felter. Robotten saetter dem kun her ved oprettelsen
        # og roerer dem aldrig igen.
        "Status": "Ny",
        "AfgorelseSkrevet": False,

        "AntalAdresser": len(adresser),
        "AntalKontakter": len(kontakter),
        "AntalVedhaeftninger": len(vedhaeftninger),
        "AdresserTekst": "\n".join(a["Adresse"] for a in adresser if a.get("Adresse")) or None,
        "Grundejere": "\n".join(grundejere) or None,
    }


def _build_title(adresser: list[dict], serial: Any) -> str:
    """Bygger ansoegningens titel.

    Foerste adresse, med antallet af oevrige bagefter. Antallet af adresser er
    ubegraenset, saa titlen maa ikke forsoege at rumme dem alle.
    """
    med_adresse = [a["Adresse"] for a in adresser if a.get("Adresse")]
    if not med_adresse:
        return f"§8 – {serial}" if serial else "§8 – ukendt"

    title = med_adresse[0]
    if len(med_adresse) > 1:
        title += f" (+{len(med_adresse) - 1} flere)"
    return title


# --- Detaljelister ---

def _map_adresser(data: dict) -> list[dict]:
    """Bygger raekkerne til P8Adresser.

    Ansoeger kan tilfoeje ubegraenset mange ejendomme, saa der er ingen oevre
    graense her.
    """
    adresser = []
    for blok in data.get("adresser") or []:
        if not isinstance(blok, dict):
            logger.warning("Uventet element i 'adresser': %r", type(blok).__name__)
            continue

        adresse = _clean(blok.get("vaelg_adresse"))
        if not any((adresse, _clean(blok.get("mat")), _clean(blok.get("lokalitets_nummer")))):
            continue

        adresser.append({
            "Title": adresse or "(uden adresse)",
            "Adresse": adresse,
            "Matrikel": _clean(blok.get("mat")),
            "LokalitetsNummer": _clean(blok.get("lokalitets_nummer")),
        })
    return adresser


def _map_kontakter(data: dict) -> list[dict]:
    """Bygger raekkerne til P8Kontakter.

    Blanketten er flad, saa hver part samles fra felter med samme suffiks.
    """
    indsendt_af = _clean(data.get("ansoegning_indsendt_af"))
    flere_grundejere = _is_yes(data.get("er_der_flere_grundejere"))
    bygherre_er_grundejer = _is_yes(data.get("er_bygherre_den_samme_som_grundejer"))

    kontakter = []
    for suffix, kontakt_type in CONTACT_GROUPS:
        # Grundejer nr. 2 gaelder kun hvis blanketten siger der er flere.
        if suffix == "_2" and not flere_grundejere:
            continue

        # Er bygherren den samme som grundejeren, skal der ikke oprettes en
        # dublet. Blanketten kan godt indeholde udfyldte _byg-felter alligevel,
        # saa flaget vinder over indholdet.
        if suffix == "_byg" and bygherre_er_grundejer:
            continue

        kontakt = _map_kontakt(data, suffix, kontakt_type)
        if kontakt:
            # Kun den foerste grundejer kan vaere udfylderen — nr. 2 har
            # alligevel intet navnefelt.
            kontakt["ErUdfylder"] = (
                kontakt_type == indsendt_af and suffix in ("", "_raad", "_byg")
            )
            kontakter.append(kontakt)

    return kontakter


def _map_kontakt(data: dict, suffix: str, kontakt_type: str) -> Optional[dict]:
    """Samler én kontakt fra de felter der baerer et bestemt suffiks.

    Returnerer None hvis alle felter er tomme — saa har parten ikke vaeret
    udfyldt, og der skal ikke oprettes en raekke.
    """
    kontakt = {}
    for column, base in CONTACT_FIELDS.items():
        field = FIELD_NAME_EXCEPTIONS.get((base, suffix), f"{base}{suffix}")
        kontakt[column] = _clean(data.get(field))

    if not any(kontakt.values()):
        return None

    kontakt["KontaktType"] = kontakt_type
    # Firmaet som titel naar navnet mangler — det goer det bl.a. for grundejer
    # nr. 2, som ingen navnefelt har i blanketten.
    kontakt["Title"] = kontakt["Navn"] or kontakt["Firma"] or kontakt_type
    return kontakt


def _map_vedhaeftninger(data: dict) -> list[dict]:
    """Bygger raekkerne til P8Vedhaeftninger.

    Blanketten leverer kun fil-id'er, ikke URL'er eller filnavne. Skal filerne
    kunne aabnes fra dashboardet, skal id'erne slaas op via REST-API'ets
    /entity/file/{file_id} — se aabent punkt 1 i SHAREPOINT-LISTER.md.
    """
    vedhaeftninger = []
    for entry in data.get("upload_dokumenter") or []:
        # Et rent id i den flade form; et opslag hvis REST-svaret har udfoldet det.
        if isinstance(entry, dict):
            file_id = _clean(entry.get("fid") or entry.get("id"))
            filnavn = _clean(entry.get("filename") or entry.get("name"))
            url = _clean(entry.get("url"))
        else:
            file_id = _clean(entry)
            filnavn = None
            url = None

        if not file_id and not url:
            continue

        vedhaeftninger.append({
            "Title": filnavn or file_id or "(ukendt fil)",
            "FilId": file_id,
            "Filnavn": filnavn,
            "FilUrl": url,
        })
    return vedhaeftninger


# --- Hjaelpefunktioner ---

def _meta(submission: dict, key: str) -> Any:
    """Henter et metadatafelt, uanset om svaret er fladt eller Drupal-pakket.

    REST-API'et pakker entity-felter som lister af {"value": ...} under
    "entity", mens den flade visning har dem paa topniveau. Begge former
    forekommer, saa begge haandteres.
    """
    entity = submission.get("entity")
    if isinstance(entity, dict) and key in entity:
        value = entity[key]
        if isinstance(value, list) and value:
            first = value[0]
            return first.get("value") if isinstance(first, dict) else first
        return value

    return submission.get(key)


def _clean(value: Any) -> Optional[str]:
    """Normaliserer en vaerdi til tekst, eller None hvis den er tom.

    Tomme felter kommer tilbage som tom streng, ikke som null, saa de skal
    fanges her frem for at blive skrevet som tomme kolonner.
    """
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _as_int(value: Any) -> Optional[int]:
    """Konverterer til heltal. Serial og sid kommer som strenge."""
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        logger.warning("Kunne ikke laese tal: %r", value)
        return None


def _is_yes(value: Any) -> bool:
    """Blanketten sender Ja/Nej som tekst, ikke som boolean."""
    return _clean(value) == "Ja"


def _map_form_date(value: Any) -> Optional[str]:
    """Konverterer en dato fra blanketten (YYYY-MM-DD) til SharePoints UTC-form."""
    date_str = _clean(value)
    if not date_str:
        return None
    try:
        return local_to_sharepoint_utc(date_str)
    except ValueError:
        logger.warning("Uventet datoformat: %r", date_str)
        return None
