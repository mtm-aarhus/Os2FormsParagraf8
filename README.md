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
- Feltmapningen (`src/mapper.py`), skrevet og testet mod en faktisk
  testindsendelse fra den nuværende blanket

Mangler:

- Oprettelse af SharePoint-listerne
- Opslag af vedhæftede filer — blanketten giver kun fil-id'er, ikke navne
  eller URL'er (se åbent punkt 1 i `SHAREPOINT-LISTER.md`)
- Webhook-opsætning på blanketten mod PyOrchestrator API'et
- Triggere i OpenOrchestrator
- SPFx-dashboardet (separat projekt)

## SharePoint

| | |
|---|---|
| Site | `https://aarhuskommune.sharepoint.com/teams/NaturogMiljDashboard` |
| Frontend-side | [§8-Ansøgninger – Jord og Grundvand](https://aarhuskommune.sharepoint.com/teams/NaturogMiljDashboard/SitePages/%C2%A78-Ans%C3%B8gninger---Jord-og-Grundvand.aspx) |
| Lister | `P8Ansogninger`, `P8Adresser`, `P8Kontakter`, `P8Vedhaeftninger` |

## Blanketten

| | |
|---|---|
| Navn | Ansøgning om §8-tilladelse efter jordforureningsloven |
| Maskinnavn | `ansoegning_om_ss8_tilladelse_beb` |
| REST base | `https://selvbetjening.aarhuskommune.dk/webform_rest/` |
| [Blanketten](https://selvbetjening.aarhuskommune.dk/da/content/upload-ansoegning-om-ss8-tilladelse-efter-jordforureningsloven) | |

Maskinnavnet er præcis 32 tegn, fordi Drupal afkorter der — `_beb` er en
afhugget rest, ikke en tastefejl.

Adgang til API'et gives **pr. blanket** i OS2Forms. En nøgle der virker mod en
anden af kommunens blanketter virker ikke automatisk her; brugeren bag nøglen
skal eksplicit have adgang til denne. Svarer endpointet 403, er det typisk det,
der mangler.

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

### Kortlægning af blanketten

Feltmapningen kræver at man ved, hvad blanketten faktisk sender. Der er to
veje, alt efter om man kan få fat i API-nøglen.

**Via OpenOrchestrator — når nøglen ikke må hentes ud.** Robotten kører på
OO-maskinen og har adgang til credentialet i forvejen. Opret en SINGLE-trigger
på denne proces med procesargumentet:

```
struktur
```

Robotten henter så den nyeste indsendelse og skriver blankettens feltstruktur i
OO-loggen. Den rører hverken køen eller SharePoint — den læser kun. En bestemt
indsendelse kan vælges med `struktur uuid=1234abcd-...`.

**Lokalt — når man har nøglen.**

```sh
python -m venv venv
venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env
```

```sh
python scripts/hent_eksempel_submission.py --list
python scripts/hent_eksempel_submission.py --struktur
```

Sættes `OpenOrchestratorSQL` og `OpenOrchestratorKey` i `.env`, henter scriptet
selv nøglen fra credentialet `OS2FormsAPI`, så den ikke skal kopieres ud.

### Persondata i kortlægningen

En indsendelse indeholder borgerens navn, adresse, telefonnummer og
mailadresse. Til mapningen skal der kun bruges feltnavne, typer og indlejring,
så begge veje ovenfor udskriver **strukturen uden værdierne**:

```
data  dict[8]
  udfylder  str (maskeret, laengde 11)
  er_udfylder_grundejer_raadgiver_bygherre_eller_andet  str = "Raadgiver"
  vaelg_dato_for_ansoegning  str (dato YYYY-MM-DD)
  adresser  list[1]
    [0]  dict[3]
      vaelg_adresse  str (maskeret, laengde 30)
```

Felter hvis navn peger på persondata maskeres altid (`src/struktur.py`,
`SENSITIVE_HINTS`). Datoer beskrives ved deres format, da det er formatet
mapningen skal bruge. Spørgsmålsfelter — dem der starter med `er_`, `har_`,
`oensker_` — vises derimod, fordi svaret er en kategori og netop afgør hvilke
valgmuligheder SharePoint-kolonnen skal have.

Den udskrift er fri for persondata og kan deles. Den fulde JSON gemmes kun
lokalt i `lokalt/`, som ikke er i versionsstyring, og må ikke committes eller
videresendes.

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
