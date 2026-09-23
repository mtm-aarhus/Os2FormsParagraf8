"""Klient til de fire §8-lister i SharePoint.

Kolonnenavne og listestruktur er beskrevet i SHAREPOINT-LISTER.md.
"""

import logging
from datetime import datetime
from typing import Any, Optional
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from office365.sharepoint.client_context import ClientContext

from robot_framework import config

logger = logging.getLogger(__name__)

COPENHAGEN_TZ = ZoneInfo("Europe/Copenhagen")

UUID_FIELD = "SubmissionUUID"
LOOKUP_FIELD = "AnsogningId"  # Lookup-kolonner saettes med Id-suffiks via REST

# Kolonner der er af typen "Hyperlink eller billede" og derfor skal pakkes ind
# i en SP.FieldUrlValue frem for at saettes som ren tekst.
URL_FIELDS = {"SamletPdfUrl", "FilUrl"}


def build_context(site_url: str, tenant: str, client_id: str, thumbprint: str, cert_path: str) -> ClientContext:
    """Opretter en SharePoint-kontekst med certifikat-autentificering."""
    return ClientContext(site_url).with_client_certificate(
        tenant=tenant,
        client_id=client_id,
        thumbprint=thumbprint,
        cert_path=cert_path,
    )


def local_to_sharepoint_utc(date_str: str, time_str: str = "00:00:00") -> str:
    """Konverterer dansk lokaltid til den UTC-streng SharePoint forventer.

    SharePoint gemmer DateTime-felter internt i UTC. Skriver man en dansk dato
    uden tidszone, forskydes den ved visning — typisk en dag tilbage, fordi
    midnat dansk tid er den foregaaende dag i UTC. Derfor skal alle datoer fra
    blanketten igennem denne konvertering, inklusive dem uden klokkeslaet.

    Haandterer sommer- og vintertid via zoneinfo.
    """
    naive_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
    local_dt = naive_dt.replace(tzinfo=COPENHAGEN_TZ)
    return local_dt.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ")


class SharePointClient:
    """Skriver §8-ansoegninger til SharePoint-listerne."""

    def __init__(self, ctx: ClientContext):
        self._ctx = ctx

    # --- Opslag ---

    def get_all_submission_uuids(self) -> set[str]:
        """Henter alle UUID'er der allerede ligger i ansoegningslisten.

        Hentes samlet én gang pr. koersel i stedet for ét opslag pr. indsendelse —
        ellers ville hver koersel koste et kald pr. ansoegning i pollingvinduet.
        """
        items = (
            self._ctx.web.lists.get_by_title(config.LIST_ANSOGNINGER)
            .items.top(5000)
            .get()
            .execute_query()
        )
        uuids = {
            item.properties[UUID_FIELD]
            for item in items
            if item.properties.get(UUID_FIELD)
        }
        logger.info("Hentede %d eksisterende UUID'er fra '%s'", len(uuids), config.LIST_ANSOGNINGER)
        return uuids

    def submission_exists(self, submission_uuid: str) -> bool:
        """Tjekker om en enkelt ansoegning allerede findes."""
        return self._find_ansogning_id(submission_uuid) is not None

    def _find_ansogning_id(self, submission_uuid: str) -> Optional[int]:
        """Finder list-item-ID'et for en ansoegning ud fra dens UUID."""
        items = (
            self._ctx.web.lists.get_by_title(config.LIST_ANSOGNINGER)
            .items.filter(f"{UUID_FIELD} eq '{submission_uuid}'")
            .top(1)
            .get()
            .execute_query()
        )
        return items[0].properties["ID"] if items else None

    # --- Skrivning ---

    def create_ansogning(self, ansogning: dict[str, Any]) -> int:
        """Opretter én raekke i ansoegningslisten og returnerer dens item-ID."""
        item = (
            self._ctx.web.lists.get_by_title(config.LIST_ANSOGNINGER)
            .add_item(_clean(ansogning))
        )
        self._ctx.execute_query()
        return item.properties["ID"]

    def create_adresse(self, ansogning_id: int, submission_uuid: str, adresse: dict[str, Any]) -> None:
        """Opretter én adresseraekke knyttet til en ansoegning."""
        self._create_child(config.LIST_ADRESSER, ansogning_id, submission_uuid, adresse)

    def create_kontakt(self, ansogning_id: int, submission_uuid: str, kontakt: dict[str, Any]) -> None:
        """Opretter én kontaktraekke knyttet til en ansoegning."""
        self._create_child(config.LIST_KONTAKTER, ansogning_id, submission_uuid, kontakt)

    def create_vedhaeftning(self, ansogning_id: int, submission_uuid: str, vedhaeftning: dict[str, Any]) -> None:
        """Opretter én vedhaeftningsraekke knyttet til en ansoegning."""
        self._create_child(config.LIST_VEDHAEFTNINGER, ansogning_id, submission_uuid, vedhaeftning)

    def get_internal_column_names(self, list_title: str) -> dict[str, str]:
        """Returnerer {visningsnavn: internt navn} for skrivbare kolonner.

        SharePoint koder kolonnenavne om ved oprettelsen — bindestreg bliver til
        _x002d_, oe bliver til _x00f8_, og navnet afkortes ved 32 tegn. Det
        interne navn er derfor sjaeldent det man tastede ind, og det er det
        interne navn der skal skrives til.

        Vaerre endnu: to kolonner kan have samme visningsnavn men forskellige
        interne navne (Felt, Felt0, Felt1). Skriver man til den forkerte,
        lykkes kaldet uden fejl, men vaerdien lander et sted visningen ikke
        viser. Brug denne metode til at bekraefte mapningen foer den tages i
        brug — og igen hvis en kolonne senere omdoebes.
        """
        fields = (
            self._ctx.web.lists.get_by_title(list_title)
            .fields.get()
            .execute_query()
        )
        result = {}
        for field in fields:
            props = field.properties
            if props.get("Hidden") or props.get("ReadOnlyField"):
                continue
            result[props.get("Title")] = props.get("InternalName")
        return result

    def _create_child(self, list_name: str, ansogning_id: int, submission_uuid: str, values: dict[str, Any]) -> None:
        """Opretter en raekke i en af detaljelisterne.

        Baade lookup'en og det raa UUID saettes: lookup'en er det dashboardet
        navigerer paa, UUID'et er det robotten selv kan slaa op og rydde op paa
        uden foerst at skulle oversaette til et item-ID.
        """
        payload = _clean(values)
        payload[LOOKUP_FIELD] = ansogning_id
        payload[UUID_FIELD] = submission_uuid

        self._ctx.web.lists.get_by_title(list_name).add_item(payload)
        self._ctx.execute_query()


# --- Hjaelpefunktioner ---

def _clean(data: dict[str, Any]) -> dict[str, Any]:
    """Fjerner tomme vaerdier og formaterer URL-felter som SP.FieldUrlValue."""
    result: dict[str, Any] = {}
    for key, value in data.items():
        if value is None or value == "":
            continue
        if key in URL_FIELDS:
            url_value = _as_url_value(key, value)
            if url_value is not None:
                result[key] = url_value
        else:
            result[key] = value
    return result


def _as_url_value(key: str, value: Any) -> Optional[dict[str, Any]]:
    """Pakker en streng ind som SP.FieldUrlValue, eller udelader den hvis den ikke er en brugbar URL."""
    if not isinstance(value, str):
        return None

    url = value.strip().replace(" ", "%20")[:255]
    parsed = urlparse(url)
    if parsed.scheme in ("http", "https") and parsed.netloc:
        return {"__metadata": {"type": "SP.FieldUrlValue"}, "Url": url, "Description": url}

    logger.warning("URL-felt '%s' mangler scheme eller host — udelades: '%s'", key, url[:100])
    return None
