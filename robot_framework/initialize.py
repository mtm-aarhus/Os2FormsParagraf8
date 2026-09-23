"""This module defines any initial processes to run when the robot starts.

For denne robot er det her koeen fyldes: OS2Forms spoerges efter indsendelser
i pollingvinduet, og dem der ikke allerede ligger i SharePoint laegges i koeen.
Selve behandlingen sker i process.py, ét koeelement ad gangen.
"""

from datetime import datetime, timedelta

from OpenOrchestrator.orchestrator_connection.connection import OrchestratorConnection

from robot_framework import config
from src.os2forms_client import OS2FormsClient
from src.sharepoint_client import SharePointClient, build_context


def initialize(orchestrator_connection: OrchestratorConnection) -> None:
    """Do all custom startup initializations of the robot."""
    orchestrator_connection.log_trace("Initializing.")

    os2forms = build_os2forms_client(orchestrator_connection)
    sharepoint = build_sharepoint_client(orchestrator_connection)

    starttime = (datetime.now() - timedelta(days=config.POLL_WINDOW_DAYS)).strftime("%Y-%m-%d")
    orchestrator_connection.log_info(f"Henter indsendelser fra OS2Forms siden {starttime}...")

    submissions = os2forms.list_submissions(starttime=starttime)
    orchestrator_connection.log_info(f"OS2Forms returnerede {len(submissions)} indsendelser i vinduet.")

    if not submissions:
        return

    _log_serial_gaps(submissions, orchestrator_connection)

    known_uuids = sharepoint.get_all_submission_uuids()
    orchestrator_connection.log_info(f"SharePoint indeholder i forvejen {len(known_uuids)} ansoegninger.")

    new_uuids = [
        uuid for uuid in (s.get("uuid") for s in submissions)
        if uuid and uuid not in known_uuids
    ]

    if not new_uuids:
        orchestrator_connection.log_info("Ingen nye ansoegninger at laegge i koeen.")
        return

    # Koeen kan allerede indeholde elementer fra en tidligere koersel der ikke naaede
    # at blive faerdig. Referencen er UUID'et, saa de kan filtreres fra her.
    queued = _references_already_in_queue(new_uuids, orchestrator_connection)
    to_enqueue = [uuid for uuid in new_uuids if uuid not in queued]

    if not to_enqueue:
        orchestrator_connection.log_info(
            f"Alle {len(new_uuids)} nye ansoegninger ligger allerede i koeen."
        )
        return

    orchestrator_connection.bulk_create_queue_elements(
        config.QUEUE_NAME,
        references=tuple(to_enqueue),
    )
    orchestrator_connection.log_info(f"Lagde {len(to_enqueue)} nye ansoegninger i koeen.")


def build_os2forms_client(orchestrator_connection: OrchestratorConnection) -> OS2FormsClient:
    """Bygger en OS2Forms-klient ud fra credential og constants i OpenOrchestrator."""
    api_key = orchestrator_connection.get_credential(config.OS2FORMS_CREDENTIAL).password
    base_url = orchestrator_connection.get_constant(config.OS2FORMS_BASE_URL_CONSTANT).value
    webform_id = orchestrator_connection.get_constant(config.OS2FORMS_WEBFORM_ID_CONSTANT).value
    return OS2FormsClient(base_url=base_url, webform_id=webform_id, api_key=api_key)


def build_sharepoint_client(orchestrator_connection: OrchestratorConnection) -> SharePointClient:
    """Bygger en SharePoint-klient med certifikat-auth ud fra OpenOrchestrator."""
    api_cred = orchestrator_connection.get_credential(config.SHAREPOINT_API_CREDENTIAL)
    cert_cred = orchestrator_connection.get_credential(config.SHAREPOINT_CERT_CREDENTIAL)
    site_url = orchestrator_connection.get_constant(config.SHAREPOINT_URL_CONSTANT).value

    ctx = build_context(
        site_url=site_url,
        tenant=api_cred.username,
        client_id=api_cred.password,
        thumbprint=cert_cred.username,
        cert_path=cert_cred.password,
    )
    return SharePointClient(ctx=ctx)


def _references_already_in_queue(uuids: list[str], orchestrator_connection: OrchestratorConnection) -> set[str]:
    """Finder de UUID'er der allerede ligger som koeelementer."""
    found = set()
    for uuid in uuids:
        if orchestrator_connection.get_queue_elements(config.QUEUE_NAME, reference=uuid, limit=1):
            found.add(uuid)
    return found


def _log_serial_gaps(submissions: list[dict], orchestrator_connection: OrchestratorConnection) -> None:
    """Advarer hvis der er huller i serienumrene.

    OS2Forms-serials er fortloebende pr. webform. Et hul betyder enten at en
    indsendelse er slettet, eller at den aldrig blev listet til os — det sidste
    ville ellers kunne passere ubemaerket, fordi vi kun ser det vi faar udleveret.
    """
    serials = sorted(
        int(s["serial"]) for s in submissions
        if str(s.get("serial", "")).isdigit()
    )
    if len(serials) < 2:
        return

    gaps = [
        (prev, nxt) for prev, nxt in zip(serials, serials[1:])
        if nxt - prev > 1
    ]
    if gaps:
        orchestrator_connection.log_info(
            f"Huller i serienumre fra OS2Forms: {gaps}. "
            "Kan skyldes slettede indsendelser, men boer efterses hvis det gentager sig."
        )
