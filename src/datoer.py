"""Datokonvertering til SharePoint.

Ligger for sig uden afhaengigheder, saa mapningen kan testes uden at
SharePoint-biblioteket er installeret.
"""

import logging
from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

COPENHAGEN_TZ = ZoneInfo("Europe/Copenhagen")
UTC = ZoneInfo("UTC")

SHAREPOINT_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def local_to_sharepoint_utc(date_str: str, time_str: str = "00:00:00") -> str:
    """Konverterer dansk lokaltid til den UTC-streng SharePoint forventer.

    SharePoint lagrer DateTime-felter internt i UTC. Skriver man en dansk dato
    uden tidszone, forskydes den ved visning — typisk en dag tilbage, fordi
    midnat dansk tid er den foregaaende dag i UTC. Derfor skal alle datoer fra
    blanketten igennem denne konvertering, inklusive dem uden klokkeslaet.

    Haandterer sommer- og vintertid via zoneinfo.
    """
    naive_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
    local_dt = naive_dt.replace(tzinfo=COPENHAGEN_TZ)
    return local_dt.astimezone(UTC).strftime(SHAREPOINT_FORMAT)


def unix_to_sharepoint_utc(timestamp: Any) -> Optional[str]:
    """Konverterer et Unix-tidsstempel til den UTC-streng SharePoint forventer.

    OS2Forms leverer 'created' og 'completed' som sekunder siden epoch, og som
    streng — ikke som ISO-datoer. Et tidsstempel er allerede i UTC, saa her skal
    der ikke tidszonekonverteres, kun formateres.

    Returnerer None for tomme eller ubrugelige vaerdier, saa feltet udelades
    frem for at blive skrevet forkert.
    """
    if timestamp in (None, "", 0, "0"):
        return None
    try:
        seconds = int(timestamp)
    except (TypeError, ValueError):
        logger.warning("Kunne ikke laese tidsstempel: %r", timestamp)
        return None

    return datetime.fromtimestamp(seconds, UTC).strftime(SHAREPOINT_FORMAT)
