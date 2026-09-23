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

Er indsendelsen en TESTINDSENDELSE med opdigtede data, kan vaerdierne tages med.
Det giver en langt praecisere mapning, fordi de viser de faktiske
valgmuligheder, datoformater og hvordan tomme felter kommer tilbage:

    struktur vis-vaerdier

Brug ALDRIG vis-vaerdier paa en rigtig borgerindsendelse — saa skrives navn,
adresse, telefonnummer og mailadresse i OO-loggen.

Robotten roerer hverken koeen eller SharePoint i denne tilstand — den laeser
kun.
"""

import re
import sys
from datetime import datetime, timedelta

from OpenOrchestrator.orchestrator_connection.connection import OrchestratorConnection

from robot_framework import config
from robot_framework import initialize
from src.os2forms_client import newest
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
    show_values = "vis-vaerdier" in arguments.lower()

    log_submission_structure(orchestrator_connection, requested_uuid, show_values)


def log_submission_structure(orchestrator_connection: OrchestratorConnection,
                             submission_uuid: str | None = None,
                             show_values: bool = False) -> None:
    """Henter én indsendelse og skriver dens struktur i loggen."""
    if show_values:
        orchestrator_connection.log_info(
            "ADVARSEL: vis-vaerdier er slaaet til. Indsendelsens faktiske vaerdier "
            "skrives i loggen. Det maa kun ske for en testindsendelse med "
            "opdigtede data — aldrig for en rigtig borgerindsendelse."
        )

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

        orchestrator_connection.log_info(f"Fandt {len(submissions)} indsendelser. De nyeste:")
        by_serial = sorted(
            submissions,
            key=lambda s: int(s["serial"]) if str(s.get("serial", "")).isdigit() else -1,
        )
        for submission in by_serial[-10:]:
            orchestrator_connection.log_info(
                f"  serial={submission.get('serial', '?')}  "
                f"created={submission.get('created', '?')}  "
                f"uuid={submission.get('uuid', '?')}"
            )

        chosen = newest(submissions)
        submission_uuid = chosen.get("uuid") if chosen else None
        if not submission_uuid:
            orchestrator_connection.log_error(
                "Den nyeste indsendelse har intet uuid — angiv et med 'uuid=...' i procesargumentet."
            )
            return

        orchestrator_connection.log_info(
            f"Valgte den nyeste: serial={chosen.get('serial', '?')}. "
            "Er det ikke den nye testindsendelse, saa angiv 'uuid=...' i procesargumentet."
        )

    orchestrator_connection.log_info(f"Henter indsendelse {submission_uuid}...")
    submission = os2forms.get_submission(submission_uuid)

    lines = describe_structure(submission, show_values=show_values)
    beskrivelse = (
        "MED vaerdier — maa kun deles hvis det er en testindsendelse"
        if show_values
        else "uden vaerdier (ingen persondata)"
    )
    orchestrator_connection.log_info(
        f"Struktur for {config.WEBFORM_ID} — {len(lines)} linjer, {beskrivelse}:"
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
