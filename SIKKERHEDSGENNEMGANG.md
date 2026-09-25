# Sikkerhedsgennemgang før offentliggørelse

Gennemført 25. september 2026, før repoet blev overført til `mtm-aarhus` og gjort
offentligt. Robotten håndterer borgerdata for en offentlig myndighed, så gennemgangen
dækkede både koden og hele git-historikken.

## Hemmeligheder: ingen

Alle 70 blobs, der nogensinde har eksisteret i historikken, blev udtrukket og scannet
for nøgler, tokens, certifikater og strenge med høj entropi. Intet fundet.

`.env` blev committet i den første commit og senere taget ud af versionsstyring. Den
indeholdt én linje: en forbindelsesstreng til Azure SQL med
`authentication=ActiveDirectoryMSI` — altså værtsnavn og databasenavn, **intet
brugernavn eller kodeord**. Managed Identity betyder, at der ikke er nogen hemmelighed
at lække. Historikken behøvede derfor ikke omskrives.

Al legitimation hentes fra OpenOrchestrator ved kørsel. Der findes ingen tenant-GUID'er,
certifikat-thumbprints, certifikatstier eller personlige mailadresser i træet eller
historikken.

## Rettet før offentliggørelse

### Maskeringen i `src/struktur.py` havde en omgåelse

Modulet findes for at kunne beskrive en blankets felter uden at skrive borgerens svar i
OpenOrchestrator-loggen. Men spørgsmålsfelter — dem hvis navn starter med `er_`, `har_`,
`oensker_` og lignende — vandt over spærrelisten. Et felt som `har_du_en_anden_adresse`
ville derfor have fået sin værdi skrevet i loggen ordret.

Fejlen var i designet, ikke i implementeringen: et præfiks kan ikke skelne et
kategorispørgsmål fra et frit tekstfelt. Præfikset er nu underordnet spærrelisten, og
de felter, der reelt skal vises, står på en **eksplicit tilladelsesliste efter fuldt
feltnavn** — verificeret mod den faktiske blanket.

To gaps i samme fil blev rettet med: tal maskeres nu som udgangspunkt frem for kun når
navnet står på spærrelisten (et husnummer eller telefonnummer gemt som tal slap
igennem), og `postnummer` matchede ikke spærreordet `postnr`, fordi tjekket er
substring-baseret.

### Fejlmails sendte et skærmbillede af hele skrivebordet

`error_screenshot.py` kaldte `ImageGrab.grab()` og mailede resultatet over ukrypteret
SMTP. Robotten kører uden brugerflade, så billedet kunne kun indeholde, hvad der
**ellers** stod på OpenOrchestrator-workerens skrivebord — en anden robots vindue eller
en sagsbehandlers skærm med borgerdata.

Skærmbilledet er fjernet. Funktionen sender kun fejlteksten. `Pillow` er samtidig
fjernet som afhængighed, da den kun var der til det formål.

### Fejltekster kunne gengive indsendte feltværdier

`handle_error` skrev `repr(error)` og den fulde stak til både OO-loggen og køelementets
status. En `ClientRequestException` fra `office365` bærer serverens svartekst, så et
afvist `add_item` kunne gengive de feltværdier, der blev forsøgt skrevet.

For den undtagelsestype vises nu HTTP-statuskoden og listenavnet i stedet for
svarteksten, og al fejltekst afkortes.

### `submission_uuid` blev aldrig valideret

Værdien nåede to usikrede steder: et OData-filter, hvor et apostrof kunne få
`submission_exists()` til fejlagtigt at returnere sandt og dermed droppe en ansøgning
stille, og en URL-sti, hvor `../`-segmenter kunne omdirigere kaldet til et andet
endpoint på samme vært — **med `api-key`-headeren siddende på**.

Værdien kommer i dag fra det interne PyOrchestrator-API og ikke fra den offentlige
blanket, så det var ikke udnytteligt udefra. Det var én webhook-fejlkonfiguration fra
at blive det. Facon valideres nu, før værdien bruges til noget.

### Mindre

- `SCREENSHOT_SENDER` pegede på `robot@friend.dk` — en ITK-skabelonrest med et domæne,
  kommunen ikke ejer.
- SMTP-server og -port flyttet til OpenOrchestrator-constants frem for at stå som
  litteraler i et offentligt repo.
- `diagnostik.py` med `vis-vaerdier` og uden `uuid=` valgte den nyeste indsendelse —
  altså en rigtig borger — og skrev hver værdi i den permanente OO-log. Et eksplicit
  `uuid=` er nu påkrævet.
- `tzdata` pinnet til en major-version som de øvrige afhængigheder.
- En rigtig adresse fra en testindsendelse i `SHAREPOINT-LISTER.md` erstattet med en
  opdigtet.

## Vurderet og accepteret

Borgerens formulardata kan **ikke** bryde ud af en OData-streng. Værdierne når kun
`add_item()`-kroppe, og URL-felter kræver `http`/`https` plus en vært, før de skrives.
`submission_uuid` var den eneste usikrede interpolation i repoet.

Det, offentliggørelsen afslører — SharePoint-sitets sti, liste- og kolonnenavne,
blankettens maskinnavn, `selvbetjening.aarhuskommune.dk`-URL'erne — kræver en
autentificeret session for at være til nogen nytte, og svarer til hvad organisationen
allerede publicerer for sine øvrige robotter.

## Forudsætning for drift

`main.py` kører `git pull origin main` og afvikler derefter koden. Når repoet er
offentligt, har enhver med push-adgang til `main` dermed kodeudførelse på
OpenOrchestrator-serveren. **`main` bør beskyttes med branch protection.** Det gælder
alle robotter i organisationen, ikke kun denne.
