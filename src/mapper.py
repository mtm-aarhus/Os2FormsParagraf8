"""Mapning fra OS2Forms-indsendelse til SharePoint-raekker.

=============================================================================
IKKE IMPLEMENTERET ENDNU — VENTER PAA NY JSON FRA BLANKETTEN
=============================================================================

OS2Forms-blanketten til §8 er aendret markant siden den oprindelige webhook
blev skrevet. Den gamle mapning laa i `app.py` og laeste felter som:

    data["udfylder"]
    data["vaelg_dato_for_ansoegning"]
    data["adresser"]
    data["er_udfylder_grundejer_raadgiver_bygherre_eller_andet"]
    data["kontaktoplysninger_for_grundejer"]      (og _raadgiver / _bygherre)
    data["hvem_er_grundejer"]                     (og _bygherre)
    data["linked"]["upload_dokumenter"]
    data["attachments"]["attachments"]
    entity["sid"] / entity["created"] / entity["completed"]

De feltnavne gaelder ikke noedvendigvis laengere, og der kan vaere kommet nye
felter til. At gaette paa dem ville give en robot der tier stille og skriver
tomme raekker — derfor rejser denne modul en fejl indtil mapningen er skrevet
paa et faktisk grundlag.

Den gamle mapning kan stadig ses i git-historikken:
    git show 7b0cdd7:app.py

Saadan skaffes grundlaget:
    python scripts/hent_eksempel_submission.py --help

Naar JSON'en foreligger, implementeres `map_submission` nedenfor, og
SHAREPOINT-LISTER.md rettes til saa kolonnerne matcher de faktiske felter.
"""

from typing import Any


def map_submission(submission: dict[str, Any]) -> tuple[dict, list[dict], list[dict], list[dict]]:
    """Oversaetter én OS2Forms-indsendelse til raekker i de fire SharePoint-lister.

    Args:
        submission: Raa JSON fra `/webform_rest/{webform_id}/submission/{uuid}`.

    Returns:
        Fire dele, i denne raekkefoelge:
            ansogning:      felter til P8Ansogninger (én raekke)
            adresser:       felter til P8Adresser (nul eller flere)
            kontakter:      felter til P8Kontakter (nul eller flere)
            vedhaeftninger: felter til P8Vedhaeftninger (nul eller flere)

        Noeglerne i hver dict skal matche kolonnernes interne navne i
        SHAREPOINT-LISTER.md praecist.
    """
    raise NotImplementedError(
        "Mapningen mangler. OS2Forms-blanketten er aendret, saa feltnavnene skal "
        "verificeres mod en faktisk indsendelse foer mapningen kan skrives. "
        "Koer scripts/hent_eksempel_submission.py for at hente en ned."
    )
