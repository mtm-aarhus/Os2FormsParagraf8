"""This module defines any initial processes to run when the robot starts.

Robotten koeres fra to slags triggere:

- En QueueTrigger, naar PyOrchestrator-API'et har lagt en ansoegning i koeen
  efter en indsendelse i OS2Forms. Her er der intet at polle — elementet ligger
  der allerede, og robotten skal bare i gang.
- En planlagt trigger som sikkerhedsnet. Her polles OS2Forms for alt hvad
  webhooken maatte have tabt, og de manglende ansoegninger laegges i koeen.

Pollingen springes over naar procesargumentet indeholder "no-poll". Standard er
at polle, saa en forkert opsat trigger fejler til den sikre side.
"""

from datetime import datetime, timedelta

from OpenOrchestrator.orchestrator_connection.connection import OrchestratorConnection

from robot_framework import config
from src.os2forms_client import OS2FormsClient
from src.sharepoint_client import SharePointClient, build_context


def initialize(orchestrator_connection: OrchestratorConnection) -> None:
    """Do all custom startup initializations of the robot."""
    orchestrator_connection.log_trace("Initializing.")

    if not _should_poll(orchestrator_connection):
        orchestrator_connection.log_info("Springer polling over (no-poll) — koersel er udloest af koeen.")
        return

    fill_queue_from_os2forms(orchestrator_connection)


def _should_poll(orchestrator_connection: OrchestratorConnection) -> bool:
    """Afgoer om denne koersel skal polle OS2Forms."""
    arguments = getattr(orchestrator_connection, "process_arguments", None) or ""
    return "no-poll" not in str(arguments).lower()


def fill_queue_from_os2forms(orchestrator_connection: OrchestratorConnection) -> None:
    """Poller OS2Forms og laegger ubehandlede ansoegninger i koeen.

    Sikkerhedsnet for de indsendelser webhooken ikke naaede at melde ind.
    """
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

    # Koeen kan allerede indeholde elementer — enten fra webhooken, eller fra en
    # tidligere koersel der ikke naaede at blive faerdig. Referencen er UUID'et,
    # saa de kan filtreres fra her.
    queued = _references_already_in_queue(new_uuids, orchestrator_connection)
    to_enqueue = [uuid for uuid in new_uuids if uuid not in queued]

    if not to_enqueue:
        orchestrator_connection.log_info(
            f"Alle {len(new_uuids)} nye ansoegninger ligger allerede i koeen."
        )
        return

    # Samme dataform som webhooken laegger ind, saa process.py kun skal kende én.
    orchestrator_connection.bulk_create_queue_elements(
        config.QUEUE_NAME,
        references=tuple(to_enqueue),
        data=tuple(
            {"application_uuid": uuid, "formular": config.WEBFORM_ID}
            for uuid in to_enqueue
        ),
        created_by="Sikkerhedsnet-polling",
    )
    orchestrator_connection.log_info(
        f"Lagde {len(to_enqueue)} ansoegninger i koeen som webhooken ikke havde meldt ind."
    )


def build_os2forms_client(orchestrator_connection: OrchestratorConnection) -> OS2FormsClient:
    """Bygger en OS2Forms-klient ud fra credentialet i OpenOrchestrator.

    Credentialet OS2FormsAPI baerer base-URL'en i username og noeglen i password.
    """
    credential = orchestrator_connection.get_credential(config.OS2FORMS_CREDENTIAL)
    return OS2FormsClient(
        base_url=credential.username,
        webform_id=config.WEBFORM_ID,
        api_key=credential.password,
    )


def build_sharepoint_client(orchestrator_connection: OrchestratorConnection) -> SharePointClient:
    """Bygger en SharePoint-klient med certifikat-auth ud fra OpenOrchestrator."""
    api_cred = orchestrator_connection.get_credential(config.SHAREPOINT_API_CREDENTIAL)
    cert_cred = orchestrator_connection.get_credential(config.SHAREPOINT_CERT_CREDENTIAL)
    base_url = orchestrator_connection.get_constant(config.SHAREPOINT_BASE_CONSTANT).value

    ctx = build_context(
        site_url=f"{base_url.rstrip('/')}{config.SHAREPOINT_SITE_PATH}",
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
