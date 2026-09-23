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
- Oprettelse af SharePoint-listerne, og valg af site
  (`SHAREPOINT_SITE_PATH` i `robot_framework/config.py`)
- Bekræftelse af blankettens maskinnavn (`WEBFORM_ID`)
- Webhook-opsætning på blanketten mod PyOrchestrator API'et
- Triggere i OpenOrchestrator
- SPFx-dashboardet (separat projekt)

## Beslægtede projekter

| Repo | Hvad vi bruger derfra |
|---|---|
| [`Os2FormsToSharepoint`](https://github.com/mtm-aarhus/Os2FormsToSharepoint) | Mønsteret for OS2Forms → SharePoint, credential-navne, og de dokumenterede faldgruber om interne kolonnenavne |
| [`FlaskOrchestratorAPI`](https://github.com/mtm-aarhus/FlaskOrchestratorAPI) | `POST /api/queue` — webhook-modtageren, der lægger indsendelser i køen |
| [`aktivt_systemejerskab`](https://github.com/mtm-aarhus/aktivt_systemejerskab) | Kø-framework og SharePoint-certifikatopsætning |

## Sådan virker den

Ansøgninger kommer ind ad to veje, og robotten behandler dem ens.

**Den hurtige vej — webhook.** Når en borger indsender §8-blanketten, POSTer
OS2Forms til det eksisterende [PyOrchestrator
API](https://github.com/mtm-aarhus/FlaskOrchestratorAPI) (`POST /api/queue`),
som opretter et køelement i OpenOrchestrator. En QueueTrigger starter robotten.
Der skal ikke bygges nogen modtager — API'et findes og bruges af de øvrige
MTM-robotter.

Blanketten konfigureres til at sende:

```json
{
  "queue_name": "Paragraf8Ansogninger",
  "reference": "[webform_submission:uuid]",
  "data": { "application_uuid": "[webform_submission:uuid]", "formular": "paragraf_8_ansoegning" },
  "created_by": "OS2Forms"
}
```

**Sikkerhedsnettet — planlagt polling.** En planlagt trigger kører `initialize`,
som spørger OS2Forms efter indsendelser i pollingvinduet (`POLL_WINDOW_DAYS`,
standard 14 dage) og lægger dem i køen, som webhooken ikke har meldt ind.
Køres robotten fra QueueTriggeren, springes pollingen over via procesargumentet
`no-poll`.

En tabt borgerhenvendelse er dyr, og forsikringen er nærmest gratis:
dubletfiltreringen sker på `SubmissionUUID`, så de to veje kan melde den samme
ansøgning ind uden at den oprettes to gange. Robotten logger desuden huller i
OS2Forms' fortløbende serienumre, da et hul kan betyde en indsendelse der aldrig
blev listet.

**Behandlingen.** For hvert køelement hentes den fulde indsendelse, den mappes,
og der skrives én række i `P8Ansogninger` plus rækker i `P8Adresser`,
`P8Kontakter` og `P8Vedhaeftninger`. Fejler én ansøgning, markeres netop det
køelement som fejlet, og robotten går videre til det næste.

### Hvorfor robotten ikke selv er en webserver

En OpenOrchestrator-robot starter, arbejder og afslutter. Scheduleren spawner en
subprocess og venter på at den afslutter, før status opdateres. En webserver
afslutter aldrig, så triggeren ville gå i RUNNING og blive der — den ville
aldrig fyre igen. Derfor ligger HTTP-modtagelsen i PyOrchestrator API'et, som
kører under IIS, og ikke i robotten.

## Triggere i OpenOrchestrator

| Type | Navn | Argument | Formål |
|---|---|---|---|
| QueueTrigger | `Paragraf8Ansogninger` | `no-poll` | Starter robotten når webhooken har lagt noget i køen |
| ScheduledTrigger | fx natligt | *(ingen)* | Sikkerhedsnet — poller OS2Forms for oversete ansøgninger |

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
