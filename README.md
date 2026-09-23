# §8-ansøgninger — OS2Forms til SharePoint

Robot der henter §8-ansøgninger (jordforurening) fra OS2Forms og skriver dem i
SharePoint-lister, som et SPFx-dashboard læser fra.

Bygget på ITK's [OpenOrchestrator Robot-Framework
V2](https://github.com/itk-dev-rpa/OpenOrchestrator) i den kø-baserede variant.

## Status

**Under ombygning — kan ikke køre endnu.**

Projektet var oprindeligt en Flask-webhook deployet til Azure App Service, som
skrev til Azure SQL. Det er ved at blive lavet om til en OpenOrchestrator-robot
der skriver til SharePoint.

Færdigt:

- Robot-stillads (kø-framework, config, fejlhåndtering)
- OS2Forms-klient
- SharePoint-klient
- Specifikation af SharePoint-lister (`SHAREPOINT-LISTER.md`)

Mangler:

- **Feltmapningen** (`src/mapper.py`). Blanketten er ændret markant, så de gamle
  feltnavne gælder ikke længere. Kræver en rå JSON-udskrift fra den nuværende
  blanket — se nedenfor.
- Oprettelse af SharePoint-listerne
- Constants og credentials i OpenOrchestrator
- SPFx-dashboardet (separat projekt)

## Sådan virker den

En kørsel består af to faser:

**1. `initialize` fylder køen.** OS2Forms spørges efter indsendelser i
pollingvinduet (`POLL_WINDOW_DAYS`, standard 14 dage). De UUID'er der ikke
allerede findes i SharePoint — og ikke allerede ligger i køen — lægges i
OpenOrchestrator-køen `Paragraf8Ansogninger` med UUID'et som reference.

**2. Kø-loopet behandler én ansøgning ad gangen.** For hvert køelement hentes
den fulde indsendelse, den mappes, og der skrives én række i `P8Ansogninger`
plus rækker i `P8Adresser`, `P8Kontakter` og `P8Vedhaeftninger`.

Fejler én ansøgning, markeres netop det køelement som fejlet, og robotten går
videre til det næste.

### Hvorfor polling og ikke webhook

En OpenOrchestrator-robot starter, arbejder og afslutter på et skema. Den kan
ikke ligge og lytte efter indgående HTTP-kald, som den gamle Flask-app gjorde.
Derfor spørger robotten selv OS2Forms via
`/webform_rest/{webform_id}/submissions`.

Pollingvinduet er bevidst meget bredere end kørselsintervallet. Indsendelser
der allerede findes i SharePoint springes over på `SubmissionUUID`, så overlap
koster ingenting — mens et for smalt vindue ville tabe ansøgninger permanent,
hvis en kørsel fejlede. Robotten logger desuden huller i OS2Forms' fortløbende
serienumre, da et hul kan betyde en indsendelse der aldrig blev listet.

## Kom i gang

### Krav

- Python 3.11+
- Adgang til OS2Forms med rollen "OS2Form REST API user" og adgang til §8-blanketten

### Lokalt

```sh
python -m venv venv
venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env
```

Udfyld `.env` og hent en eksempel-indsendelse:

```sh
python scripts/hent_eksempel_submission.py --list
python scripts/hent_eksempel_submission.py
```

JSON'en lander i `lokalt/`, som ikke er i versionsstyring — den indeholder
persondata fra en rigtig borgerindsendelse og må ikke committes.

### I produktion

OpenOrchestrator kører `main.py`, som selv henter seneste kode, sætter et
virtuelt miljø op med `uv` og starter `robot_framework`. Alle hemmeligheder
hentes fra OpenOrchestrator — se listen over credentials og constants i
`.env.example`.

## Projektstruktur

```
main.py                  Bootstrap — køres af OpenOrchestrator
robot_framework/
  __main__.py            Indgang
  queue_framework.py     Kø-loop med retry og fejlhåndtering
  config.py              Navne på credentials, constants og lister
  initialize.py          Poller OS2Forms og fylder køen
  process.py             Behandler én ansøgning
  reset.py               Oprydning mellem forsøg
  exceptions.py          Fejlhåndtering mod OpenOrchestrator
  error_screenshot.py    Fejlmail
src/
  os2forms_client.py     REST-klient til OS2Forms
  sharepoint_client.py   Skrivning til de fire lister
  mapper.py              Blanket til SharePoint-felter  ← mangler
scripts/
  hent_eksempel_submission.py   Henter en indsendelse til brug for mapningen
SHAREPOINT-LISTER.md     Specifikation af listerne
```

## Historik

Den oprindelige Flask-webhook ligger i git-historikken. Den gamle feltmapning
kan ses med:

```sh
git show 7b0cdd7:app.py
```
