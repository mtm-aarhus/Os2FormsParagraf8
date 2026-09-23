"""Henter en §8-indsendelse fra OS2Forms og beskriver dens struktur.

Formaalet er at skaffe grundlaget for feltmapningen i src/mapper.py. Blanketten
er aendret markant, saa mapningen skal skrives ud fra en faktisk indsendelse i
stedet for de gamle feltnavne.

Koeres lokalt — ikke via OpenOrchestrator.

=============================================================================
PERSONDATA
=============================================================================
Den fulde JSON indeholder rigtige persondata fra en borgerindsendelse: navne,
adresser, telefonnumre, mailadresser. Den gemmes i 'lokalt/', som ikke er i
versionsstyring, og maa ikke committes, mailes eller indsaettes i en chat.

Til mapningen er der ikke brug for vaerdierne, kun strukturen. Brug derfor
--struktur, som udskriver feltnavne, typer og indlejring med vaerdierne
udeladt. Den udskrift er fri for persondata og kan trygt deles.
=============================================================================

Brug:
    # Struktur uden vaerdier — det der skal bruges til mapningen
    python scripts/hent_eksempel_submission.py --struktur

    # List de seneste indsendelser
    python scripts/hent_eksempel_submission.py --list

    # Hent fuld JSON til lokalt/ (persondata — deles ikke)
    python scripts/hent_eksempel_submission.py

    # En bestemt indsendelse
    python scripts/hent_eksempel_submission.py --uuid 1234abcd-... --struktur

Legitimation hentes i denne raekkefoelge:
    1. OpenOrchestrator, hvis OpenOrchestratorSQL og OpenOrchestratorKey er sat
       i .env. Credentialet 'OS2FormsAPI' bruges — samme som robotten bruger.
    2. Ellers OS2FORMS_BASE_URL og OS2FORMS_API_KEY direkte fra .env.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

# Goer src/ og robot_framework/ importerbare naar scriptet koeres direkte
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from robot_framework import config  # noqa: E402  pylint: disable=wrong-import-position
from src.os2forms_client import OS2FormsClient, newest  # noqa: E402  pylint: disable=wrong-import-position
from src.struktur import describe_structure  # noqa: E402  pylint: disable=wrong-import-position

DEFAULT_OUTPUT = Path("lokalt") / "eksempel_submission.json"


def parse_args() -> argparse.Namespace:
    """Laeser kommandolinjeargumenter."""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--uuid", help="UUID paa en bestemt indsendelse. Udelades: tag den nyeste.")
    parser.add_argument("--list", action="store_true", dest="list_only",
                        help="List kun indsendelser, hent ingen fuld JSON.")
    parser.add_argument("--struktur", action="store_true",
                        help="Udskriv feltstruktur uden vaerdier. Fri for persondata.")
    parser.add_argument("--vis-vaerdier", action="store_true", dest="show_values",
                        help="Tag vaerdier med i strukturudskriften. Indeholder persondata.")
    parser.add_argument("--days", type=int, default=90,
                        help="Hvor mange dage tilbage der soeges. Standard: 90.")
    parser.add_argument("--webform-id", default=None,
                        help=f"Blankettens maskinnavn. Standard: {config.WEBFORM_ID}")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                        help=f"Hvor den fulde JSON gemmes. Standard: {DEFAULT_OUTPUT}")
    return parser.parse_args()


def build_client(webform_id: str) -> OS2FormsClient:
    """Bygger en klient, helst med legitimation fra OpenOrchestrator."""
    load_dotenv()

    oo_conn = os.environ.get("OpenOrchestratorSQL")
    oo_key = os.environ.get("OpenOrchestratorKey")

    if oo_conn and oo_key:
        # Importeres foerst her, saa scriptet kan koere paa .env alene uden at
        # OpenOrchestrator behoever vaere installeret.
        from OpenOrchestrator.orchestrator_connection.connection import (  # pylint: disable=import-outside-toplevel
            OrchestratorConnection,
        )
        print("Henter legitimation fra OpenOrchestrator...")
        # Signaturen er (process_name, connection_string, crypto_key,
        # process_arguments, trigger_id, job_id) — alle seks er paakraevede.
        # Bemaerk at sandbox.py i Os2FormsToSharepoint kun sender fem og derfor
        # fejler mod den nuvaerende OpenOrchestrator.
        connection = OrchestratorConnection(
            "hent_eksempel_submission", oo_conn, oo_key, None, None, None
        )
        credential = connection.get_credential(config.OS2FORMS_CREDENTIAL)
        return OS2FormsClient(
            base_url=credential.username,
            webform_id=webform_id,
            api_key=credential.password,
        )

    base_url = os.environ.get("OS2FORMS_BASE_URL")
    api_key = os.environ.get("OS2FORMS_API_KEY")
    if not base_url or not api_key:
        raise SystemExit(
            "Mangler legitimation.\n\n"
            "Saet enten OpenOrchestratorSQL og OpenOrchestratorKey i .env "
            "(saa hentes noeglen fra credentialet 'OS2FormsAPI'),\n"
            "eller OS2FORMS_BASE_URL og OS2FORMS_API_KEY direkte.\n\n"
            "Se .env.example."
        )

    print("Henter legitimation fra .env...")
    return OS2FormsClient(base_url=base_url, webform_id=webform_id, api_key=api_key)


def main() -> None:
    """Henter en indsendelse og udskriver eller gemmer den."""
    args = parse_args()
    webform_id = args.webform_id or config.WEBFORM_ID
    client = build_client(webform_id)

    print(f"Blanket: {webform_id}\n")

    if args.uuid:
        submission_uuid = args.uuid
    else:
        starttime = (datetime.now() - timedelta(days=args.days)).strftime("%Y-%m-%d")
        print(f"Henter indsendelser siden {starttime}...")
        submissions = client.list_submissions(starttime=starttime)

        if not submissions:
            raise SystemExit(f"Ingen indsendelser fundet de seneste {args.days} dage.")

        print(f"Fandt {len(submissions)} indsendelser:")
        for submission in sorted(
            submissions,
            key=lambda s: int(s["serial"]) if str(s.get("serial", "")).isdigit() else -1,
        ):
            print(
                f"  serial={str(submission.get('serial', '?')):>6}  "
                f"created={submission.get('created', '?')}  "
                f"uuid={submission.get('uuid', '?')}"
            )

        if args.list_only:
            return

        chosen = newest(submissions)
        submission_uuid = chosen.get("uuid") if chosen else None
        if not submission_uuid:
            raise SystemExit("Den nyeste indsendelse har intet uuid — angiv et med --uuid.")
        print(f"\nValgte den nyeste: serial={chosen.get('serial', '?')}")

    print(f"\nHenter fuld indsendelse {submission_uuid}...")
    submission = client.get_submission(submission_uuid)

    if args.struktur:
        print("\n" + "=" * 70)
        print("STRUKTUR" + ("  (med vaerdier — INDEHOLDER PERSONDATA)" if args.show_values else "  (uden vaerdier)"))
        print("=" * 70)
        for line in describe_structure(submission, show_values=args.show_values):
            print(line)
        print("=" * 70)
        if not args.show_values:
            print("Udskriften ovenfor er fri for persondata og kan deles.")
        return

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(submission, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Gemt i {args.output}")
    print("Filen indeholder persondata — del den ikke. Brug --struktur til mapningen.")


if __name__ == "__main__":
    main()
