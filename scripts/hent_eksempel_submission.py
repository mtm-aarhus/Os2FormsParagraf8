"""Henter en §8-indsendelse ned fra OS2Forms og gemmer den raa JSON.

Formaalet er at skaffe grundlaget for feltmapningen i src/mapper.py. Blanketten
er aendret markant, saa mapningen skal skrives ud fra en faktisk indsendelse i
stedet for de gamle feltnavne.

Koeres lokalt — ikke via OpenOrchestrator. API-noeglen laeses fra .env.

Brug:
    # List de seneste indsendelser (kun uuid/serial/dato, ingen persondata)
    python scripts/hent_eksempel_submission.py --list

    # Hent den nyeste indsendelse i fuld laengde
    python scripts/hent_eksempel_submission.py

    # Hent en bestemt indsendelse
    python scripts/hent_eksempel_submission.py --uuid 1234abcd-...

    # Gem et andet sted end standardplaceringen
    python scripts/hent_eksempel_submission.py --output C:\\temp\\eksempel.json

OBS: Den hentede fil indeholder rigtige persondata fra en borgerindsendelse.
Den gemmes som standard i .gitignore'de 'lokalt/' og maa ikke committes.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

# Goer src/ importerbar naar scriptet koeres direkte
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.os2forms_client import OS2FormsClient  # noqa: E402  pylint: disable=wrong-import-position

DEFAULT_OUTPUT = Path("lokalt") / "eksempel_submission.json"


def parse_args() -> argparse.Namespace:
    """Laeser kommandolinjeargumenter."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--uuid", help="UUID paa en bestemt indsendelse. Udelades: tag den nyeste.")
    parser.add_argument("--list", action="store_true", dest="list_only",
                        help="List kun indsendelser, hent ingen fuld JSON.")
    parser.add_argument("--days", type=int, default=90,
                        help="Hvor mange dage tilbage der soeges. Standard: 90.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                        help=f"Hvor JSON'en gemmes. Standard: {DEFAULT_OUTPUT}")
    return parser.parse_args()


def build_client() -> OS2FormsClient:
    """Bygger en klient ud fra miljoevariabler i .env."""
    load_dotenv()

    missing = [
        name for name in ("OS2FORMS_BASE_URL", "OS2FORMS_WEBFORM_ID", "OS2FORMS_API_KEY")
        if not os.environ.get(name)
    ]
    if missing:
        raise SystemExit(
            "Mangler i .env: " + ", ".join(missing) + "\n"
            "Se .env.example for hvad de skal indeholde."
        )

    return OS2FormsClient(
        base_url=os.environ["OS2FORMS_BASE_URL"],
        webform_id=os.environ["OS2FORMS_WEBFORM_ID"],
        api_key=os.environ["OS2FORMS_API_KEY"],
    )


def main() -> None:
    """Henter og gemmer en indsendelse."""
    args = parse_args()
    client = build_client()

    if args.uuid:
        submission_uuid = args.uuid
    else:
        starttime = (datetime.now() - timedelta(days=args.days)).strftime("%Y-%m-%d")
        print(f"Henter indsendelser siden {starttime}...")
        submissions = client.list_submissions(starttime=starttime)

        if not submissions:
            raise SystemExit(f"Ingen indsendelser fundet de seneste {args.days} dage.")

        print(f"Fandt {len(submissions)} indsendelser:")
        for submission in submissions:
            print(f"  serial={submission.get('serial', '?'):>6}  uuid={submission.get('uuid', '?')}")

        if args.list_only:
            return

        submission_uuid = submissions[-1].get("uuid")
        if not submission_uuid:
            raise SystemExit("Den nyeste indsendelse har intet uuid — angiv et med --uuid.")

    print(f"\nHenter fuld indsendelse {submission_uuid}...")
    submission = client.get_submission(submission_uuid)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(submission, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Gemt i {args.output}")
    print("\nTopniveau-noegler:", ", ".join(submission.keys()))
    if isinstance(submission.get("data"), dict):
        print(f"\nFelter i 'data' ({len(submission['data'])}):")
        for field in submission["data"]:
            print(f"  {field}")


if __name__ == "__main__":
    main()
