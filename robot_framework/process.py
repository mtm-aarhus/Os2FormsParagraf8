"""This module contains the main process of the robot.

Ét koeelement svarer til én §8-ansoegning. Elementet kommer enten fra
PyOrchestrator-API'et (webhook fra OS2Forms) eller fra sikkerhedsnets-pollingen
i initialize.py — begge lagrer samme dataform.
"""

import json
import re

from OpenOrchestrator.orchestrator_connection.connection import OrchestratorConnection
from OpenOrchestrator.database.queues import QueueElement

from robot_framework import initialize
from robot_framework.exceptions import BusinessError
from src.mapper import map_submission

# Klienterne bygges én gang og genbruges resten af koerslen. Uden det ville
# hvert koeelement koste en ny SharePoint-certifikathandshake.
_clients: dict = {}

# Standard UUID-facon: 36 tegn, 8-4-4-4-12 hex adskilt af bindestreg.
_UUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _get_clients(orchestrator_connection: OrchestratorConnection) -> tuple:
    """Henter (eller opretter) de delte klienter."""
    if not _clients:
        _clients["os2forms"] = initialize.build_os2forms_client(orchestrator_connection)
        _clients["sharepoint"] = initialize.build_sharepoint_client(orchestrator_connection)
    return _clients["os2forms"], _clients["sharepoint"]


def _submission_uuid_from(queue_element: QueueElement) -> str:
    """Finder indsendelsens UUID paa et koeelement.

    Webhooken laegger det i data som "application_uuid" (samme facon som de
    oevrige MTM-robotter). Referencen baerer det ogsaa, og bruges som fallback
    hvis data mangler eller ikke kan parses.
    """
    if queue_element.data:
        try:
            data = json.loads(queue_element.data)
            uuid = data.get("application_uuid")
            if uuid:
                return uuid
        except (json.JSONDecodeError, AttributeError):
            pass  # Falder tilbage til referencen nedenfor

    if queue_element.reference:
        return queue_element.reference

    raise BusinessError(
        "Koeelement uden application_uuid i data og uden reference — "
        "kan ikke vide hvilken ansoegning der menes."
    )


def _validate_submission_uuid(submission_uuid: str) -> None:
    """Validerer at UUID'et har standardfacon, foer det bruges til noget.

    Vaerdien flyder uescapet ind i et OData-filter i src/sharepoint_client.py
    (et apostrof kan bryde filteret, saa submission_exists() fejlagtigt
    returnerer sandt og en ansoegning droppes stille) og i en URL-sti i
    src/os2forms_client.py ("../"-segmenter normaliseres af serveren og kan
    omdirigere kaldet til et andet endpoint paa samme host — med
    api-key-headeren siddende paa).

    I dag kommer vaerdien kun fra det interne PyOrchestrator-API, ikke fra den
    offentlige blanket direkte, men det er én webhook-fejlkonfiguration fra at
    aendre sig. Selve vaerdien logges bevidst ikke her — kun dens facon — for
    ikke at skrive en evt. ondsindet streng i klartekst i OO-loggen.
    """
    if isinstance(submission_uuid, str) and _UUID_PATTERN.match(submission_uuid):
        return

    shape = f"{type(submission_uuid).__name__} med {len(str(submission_uuid))} tegn"
    raise BusinessError(
        f"submission_uuid har ikke den forventede UUID-facon "
        f"(36 tegn, 8-4-4-4-12 hex adskilt af bindestreg) — fik {shape}."
    )


def process(orchestrator_connection: OrchestratorConnection, queue_element: QueueElement | None = None) -> None:
    """Henter én §8-ansoegning fra OS2Forms og skriver den til SharePoint."""
    orchestrator_connection.log_trace("Running process.")

    if queue_element is None:
        raise BusinessError("Intet koeelement — denne robot koeres kun koebaseret.")

    submission_uuid = _submission_uuid_from(queue_element)
    _validate_submission_uuid(submission_uuid)
    os2forms, sharepoint = _get_clients(orchestrator_connection)

    orchestrator_connection.log_info(f"Behandler ansoegning {submission_uuid}...")

    # Dubletsikring foer der hentes: koeen kan indeholde et element fra en
    # tidligere koersel der naaede at skrive til SharePoint men ikke at blive
    # markeret som faerdig. Webhook og sikkerhedsnets-polling kan ogsaa melde
    # den samme ansoegning ind hver for sig.
    if sharepoint.submission_exists(submission_uuid):
        orchestrator_connection.log_info(
            f"Ansoegning {submission_uuid} findes allerede i SharePoint — springer over."
        )
        return

    submission = os2forms.get_submission(submission_uuid)
    ansogning, adresser, kontakter, vedhaeftninger = map_submission(submission)

    item_id = sharepoint.create_ansogning(ansogning)
    orchestrator_connection.log_info(f"  Oprettet ansoegning som item {item_id}.")

    for adresse in adresser:
        sharepoint.create_adresse(item_id, submission_uuid, adresse)
    for kontakt in kontakter:
        sharepoint.create_kontakt(item_id, submission_uuid, kontakt)
    for vedhaeftning in vedhaeftninger:
        sharepoint.create_vedhaeftning(item_id, submission_uuid, vedhaeftning)

    orchestrator_connection.log_info(
        f"  {len(adresser)} adresser, {len(kontakter)} kontakter, "
        f"{len(vedhaeftninger)} vedhaeftninger skrevet."
    )
