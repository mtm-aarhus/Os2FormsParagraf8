"""Klient til OS2Forms' REST API.

Dokumentation: https://github.com/OS2Forms/os2forms_rest_api

Relevante endpoints:
    GET /webform_rest/{webform_id}/submissions            — list indsendelser
    GET /webform_rest/{webform_id}/submission/{uuid}       — hent én indsendelse

Autentificering sker med headeren `api-key`. Noeglen hoerer til en bruger med
rollen "OS2Form REST API user", og brugeren skal desuden have adgang til netop
den blanket der spoerges paa.
"""

import logging
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)

TIMEOUT = 60


class OS2FormsClient:
    """Laeseadgang til indsendelser paa én blanket."""

    def __init__(self, base_url: str, webform_id: str, api_key: str):
        # Base-URL'en kommer fra credentialet OS2FormsAPI og slutter allerede paa
        # den del der gaar forud for blankettens maskinnavn, fx
        # "https://.../webform_rest/". Derfor sikres én afsluttende skraastreg
        # frem for at fjerne den.
        self.base_url = base_url.rstrip("/") + "/"
        self.webform_id = webform_id
        self._session = requests.Session()
        self._session.headers.update({"api-key": api_key})

    # --- Opslag ---

    def list_submissions(self, starttime: str, endtime: Optional[str] = None) -> list[dict[str, Any]]:
        """Lister indsendelser i et tidsrum.

        Args:
            starttime: Dato i PHP Date/Time-format, fx "2026-09-01" eller "yesterday".
            endtime: Valgfri slutdato i samme format.

        Returns:
            En liste af indsendelser. Hvert element har som minimum "uuid";
            "serial" er med naar OS2Forms leverer det.
        """
        url = f"{self.base_url}{self.webform_id}/submissions"
        params = {"starttime": starttime}
        if endtime:
            params["endtime"] = endtime

        response = self._session.get(url, params=params, timeout=TIMEOUT)
        response.raise_for_status()
        return _normalize_submission_list(response.json())

    def get_submission(self, submission_uuid: str) -> dict[str, Any]:
        """Henter én indsendelse med alle felter.

        Returnerer raa JSON som den kommer fra OS2Forms — typisk med en "data"-del
        (blankettens felter) og en "entity"-del (metadata som sid, created, completed).
        """
        url = f"{self.base_url}{self.webform_id}/submission/{submission_uuid}"
        response = self._session.get(url, timeout=TIMEOUT)
        response.raise_for_status()
        return response.json()


def newest(submissions: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """Finder den nyeste indsendelse i en liste.

    Vaelger paa hoejeste serienummer, ikke paa raekkefoelgen i svaret — OS2Forms
    lover ingen sortering, og efter en blanketaendring er det afgoerende at
    ramme den nyeste og ikke en gammel med den tidligere feltstruktur.

    Falder tilbage til sidste element hvis ingen har et brugbart serienummer.
    """
    if not submissions:
        return None

    with_serial = [s for s in submissions if str(s.get("serial", "")).isdigit()]
    if with_serial:
        return max(with_serial, key=lambda s: int(s["serial"]))

    logger.warning("Ingen indsendelser har serienummer — vaelger sidste element i svaret.")
    return submissions[-1]


def extract_submission_uuid(payload: dict[str, Any]) -> Optional[str]:
    """Traekker det globalt unikke UUID ud af en indsendelse.

    Drupal pakker entity-felter som lister af {"value": ...}, saa UUID'et ligger
    i payload["entity"]["uuid"][0]["value"] — ikke som et fladt felt.
    """
    try:
        return payload["entity"]["uuid"][0]["value"]
    except (KeyError, IndexError, TypeError):
        logger.warning("Kunne ikke finde entity.uuid[0].value i indsendelsen.")
        return None


def _normalize_submission_list(payload: Any) -> list[dict[str, Any]]:
    """Goer listesvaret til en liste af dicts.

    OS2Forms kan levere listen enten som en JSON-liste eller som et objekt med
    UUID'et som noegle. Begge former haandteres her, saa resten af koden kun skal
    kende én facon.
    """
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if isinstance(payload, dict):
        submissions = []
        for key, value in payload.items():
            if not isinstance(value, dict):
                continue
            # Noeglen er UUID'et naar svaret er et objekt; bevar det hvis
            # elementet ikke selv baerer et.
            value.setdefault("uuid", key)
            submissions.append(value)
        return submissions

    logger.warning("Uventet svarformat fra /submissions: %s", type(payload).__name__)
    return []
