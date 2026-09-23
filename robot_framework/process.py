"""This module contains the main process of the robot.

Ét koeelement svarer til én §8-ansoegning. Referencen paa koeelementet er
indsendelsens UUID i OS2Forms.
"""

from OpenOrchestrator.orchestrator_connection.connection import OrchestratorConnection
from OpenOrchestrator.database.queues import QueueElement

from robot_framework import initialize
from robot_framework.exceptions import BusinessError
from src.mapper import map_submission

# Klienterne bygges én gang og genbruges resten af koerslen. Uden det ville
# hvert koeelement koste en ny SharePoint-certifikathandshake.
_clients: dict = {}


def _get_clients(orchestrator_connection: OrchestratorConnection) -> tuple:
    """Henter (eller opretter) de delte klienter."""
    if not _clients:
        _clients["os2forms"] = initialize.build_os2forms_client(orchestrator_connection)
        _clients["sharepoint"] = initialize.build_sharepoint_client(orchestrator_connection)
    return _clients["os2forms"], _clients["sharepoint"]


def process(orchestrator_connection: OrchestratorConnection, queue_element: QueueElement | None = None) -> None:
    """Henter én §8-ansoegning fra OS2Forms og skriver den til SharePoint."""
    if queue_element is None or not queue_element.reference:
        raise BusinessError("Koeelement uden reference — kan ikke vide hvilken ansoegning der menes.")

    submission_uuid = queue_element.reference
    os2forms, sharepoint = _get_clients(orchestrator_connection)

    orchestrator_connection.log_info(f"Behandler ansoegning {submission_uuid}...")

    submission = os2forms.get_submission(submission_uuid)

    # Dobbeltsikring: koeen kan indeholde et element fra en tidligere koersel der
    # naaede at skrive til SharePoint men ikke at blive markeret som faerdig.
    if sharepoint.submission_exists(submission_uuid):
        orchestrator_connection.log_info(
            f"Ansoegning {submission_uuid} findes allerede i SharePoint — springer over."
        )
        return

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
