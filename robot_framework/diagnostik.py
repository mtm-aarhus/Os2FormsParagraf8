"""Kortlaegger blankettens felter og skriver resultatet i OpenOrchestrator-loggen.

Baggrund: API-noeglen til OS2Forms maa ikke hentes ud af OpenOrchestrator. Men
robotten koerer paa OO-maskinen og har adgang til credentialet i forvejen, saa
den kan selv hente en indsendelse og skrive dens struktur i loggen. Loggen kan
laeses i OO-UI'et, og da udskriften er uden vaerdier, indeholder den ingen
persondata og kan deles frit.

Koeres som en SINGLE-trigger med procesargumentet:

    struktur

Vil man kortlaegge en bestemt indsendelse frem for den nyeste:

    struktur uuid=1234abcd-....

Robotten roerer hverken koeen eller SharePoint i denne tilstand — den laeser
kun.
"""

import re
import sys
from datetime import datetime, timedelta

from OpenOrchestrator.orchestrator_connection.connection import OrchestratorConnection

from robot_framework import config
from robot_framework import initialize
from src.struktur import describe_structure

# Antal linjer pr. logindgang. OO-loggen haandterer lange tekster daarligt,
# saa udskriften deles op frem for at sende alt i én indgang.
LINES_PER_ENTRY = 30

# Hvor langt tilbage der ledes efter en indsendelse at kortlaegge.
LOOKBACK_DAYS = 365

UUID_PATTERN = re.compile(r"uuid=([0-9a-fA-F-]{8,})")


def main() -> None:
    """Indgangspunkt for diagnose-tilstanden."""
    orchestrator_connection = OrchestratorConnection.create_connection_from_args()
    orchestrator_connection.log_info("Diagnose: kortlaegger blankettens felter.")

    arguments = str(getattr(orchestrator_connection, "process_arguments", "") or "")
    match = UUID_PATTERN.search(arguments)
    requested_uuid = match.group(1) if match else None

    log_submission_structure(orchestrator_connection, requested_uuid)


def log_submission_structure(orchestrator_connection: OrchestratorConnection,
                             submission_uuid: str | None = None) -> None:
    """Henter én indsendelse og skriver dens struktur i loggen."""
    os2forms = initialize.build_os2forms_client(orchestrator_connection)
    orchestrator_connection.log_info(f"Blanket: {config.WEBFORM_ID}")

    if not submission_uuid:
        starttime = (datetime.now() - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")
        orchestrator_connection.log_info(f"Henter indsendelser siden {starttime}...")

        submissions = os2forms.list_submissions(starttime=starttime)
        if not submissions:
            orchestrator_connection.log_info(
                f"Ingen indsendelser de seneste {LOOKBACK_DAYS} dage — intet at kortlaegge."
            )
            return

        orchestrator_connection.log_info(f"Fandt {len(submissions)} indsendelser.")
        for submission in submissions[-10:]:
            orchestrator_connection.log_info(
                f"  serial={submission.get('serial', '?')}  uuid={submission.get('uuid', '?')}"
            )

        submission_uuid = submissions[-1].get("uuid")
        if not submission_uuid:
            orchestrator_connection.log_error(
                "Den nyeste indsendelse har intet uuid — angiv et med 'uuid=...' i procesargumentet."
            )
            return

    orchestrator_connection.log_info(f"Henter indsendelse {submission_uuid}...")
    submission = os2forms.get_submission(submission_uuid)

    lines = describe_structure(submission)
    orchestrator_connection.log_info(
        f"Struktur for {config.WEBFORM_ID} — {len(lines)} linjer, uden vaerdier (ingen persondata):"
    )

    for start in range(0, len(lines), LINES_PER_ENTRY):
        chunk = lines[start:start + LINES_PER_ENTRY]
        part = start // LINES_PER_ENTRY + 1
        total = (len(lines) + LINES_PER_ENTRY - 1) // LINES_PER_ENTRY
        orchestrator_connection.log_info(f"--- struktur {part}/{total} ---\n" + "\n".join(chunk))

    orchestrator_connection.log_info("Diagnose faerdig. Kopiér struktur-indgangene ovenfor.")


def wanted(argv: list[str] | None = None) -> bool:
    """Afgoer om robotten er startet i diagnose-tilstand."""
    args = argv if argv is not None else sys.argv[1:]
    return "struktur" in " ".join(args).lower()
