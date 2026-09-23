# §8-ansøgninger — SharePoint-lister (manuel oprettelse)

**Site:** _(udfyldes — se "Åbne punkter" nederst)_

Alle lister oprettes som **Brugerdefineret liste** ("Custom List" / Generic List) via
**Site Contents → Ny → Liste → Tom liste**.

Kolonnenavnet du taster ind bliver automatisk til det interne navn som både robotten og
SPFx-dashboardet bruger — derfor skal det staves **præcis** som vist (ingen mellemrum,
ingen æ/ø/å).

---

> ## ⚠️ Foreløbig — opret ikke listerne endnu
>
> OS2Forms-blanketten er ændret markant siden den gamle webhook blev skrevet. Kolonnerne
> nedenfor er udledt af de feltnavne der står i den gamle `app.py` (`vaelg_adresse`,
> `kontaktoplysninger_for_raadgiver`,
> `er_udfylder_grundejer_raadgiver_bygherre_eller_andet` med flere), og de navne gælder
> ikke nødvendigvis længere.
>
> **Selve strukturen holder** uanset blanketændringen: fire lister, `SubmissionUUID` som
> idempotensnøgle, denormaliserede tælle-felter på hovedlisten. Det er de *felter der
> kommer fra blanketten* der skal verificeres — og hvis blanketten nu har felter den ikke
> havde før, skal der tilføjes kolonner.
>
> Der skal bruges en **rå JSON-udskrift af en indsendelse fra den nye blanket**, før
> specifikationen kan gøres færdig og listerne oprettes. Se "Åbne punkter".

---

## Designprincipper

Strukturen er valgt med SPFx-dashboardet for øje, ikke som en 1:1-kopi af den gamle
SQL-model:

- **Én hovedliste, tre detaljelister.** `P8Ansogninger` er den liste dashboardet lister,
  filtrerer og sorterer. Adresser, kontakter og vedhæftninger ligger i hver sin liste og
  hentes kun når en enkelt ansøgning åbnes.
- **Denormaliserede felter på hovedlisten.** `AntalAdresser`, `AdresserTekst`,
  `PrimaerGrundejer` m.fl. vedligeholdes af robotten, så oversigten kan renderes med
  ét kald i stedet for et opslag pr. række. Samme mønster som `AntalReaktioner` /
  `AntalKommentarer` i master-dashboardet.
- **`SubmissionUUID` på alle fire lister.** Detaljelisterne har både en Lookup til
  ansøgningen (til dashboardet) *og* det rå UUID som tekst (så robotten kan slå op og
  rydde op uden først at skulle oversætte til et list-item-ID).
- **`SubmissionUUID` er idempotensnøglen.** Robotten henter alle eksisterende UUID'er én
  gang pr. kørsel og springer dem over. Derfor kan en kørsel gentages uden at skabe
  dubletter.

---

## Rækkefølge

`P8Ansogninger` skal oprettes først, da de tre øvrige lister har en Lookup til den:

1. `P8Ansogninger`
2. `P8Adresser`
3. `P8Kontakter`
4. `P8Vedhaeftninger`

---

## 1. P8Ansogninger

Hovedlisten — én række pr. indsendt §8-ansøgning. Det er denne liste dashboardet viser.

| Kolonnenavn (præcis stavning!) | Type | Indstillinger |
|---|---|---|
| **SubmissionUUID** | Enkelt tekstlinje | Unik nøgle fra OS2Forms. Robottens dubletsikring. Bør indekseres |
| **SubmissionSerial** | Tal | 0 decimaler. Fortløbende nummer pr. webform — bruges til at opdage huller, altså ansøgninger robotten aldrig fik hentet |
| **Udfylder** | Enkelt tekstlinje | Navnet på den der har udfyldt formularen |
| **UdfylderRolle** | Valg | Valgmuligheder: `Grundejer`, `Rådgiver`, `Bygherre`, `Andet` |
| **AnsogningsDato** | Dato og klokkeslæt | Inkluder klokkeslæt: **Nej**. Den dato ansøger selv har angivet |
| **Bemaerkninger** | Flere tekstlinjer | Almindelig tekst (ikke Rich Text) |
| **ModtagetDato** | Dato og klokkeslæt | Inkluder klokkeslæt: **Ja**. Tidspunktet OS2Forms oprettede indsendelsen |
| **AfsluttetDato** | Dato og klokkeslæt | Inkluder klokkeslæt: **Ja**. Tidspunktet indsendelsen blev fuldført. Kan stå tom |
| **Status** | Valg | Valgmuligheder: `Ny`, `Under behandling`, `Afgjort`, `Afvist`. Standardværdi: `Ny`. **Sagsbehandlerens felt — robotten sætter det kun ved oprettelse og rører det aldrig igen** |
| **AfgorelseSkrevet** | Ja/Nej | Standardværdi: Nej. Afløser `decision_written` fra SQL-modellen. Sættes af sagsbehandler, ikke af robotten |
| **AntalAdresser** | Tal | 0 decimaler, standard 0. Denormaliseret — vedligeholdes af robotten |
| **AntalKontakter** | Tal | 0 decimaler, standard 0. Denormaliseret |
| **AntalVedhaeftninger** | Tal | 0 decimaler, standard 0. Denormaliseret |
| **AdresserTekst** | Flere tekstlinjer | Alle ansøgningens adresser samlet, én pr. linje. Gør fritekstsøgning i dashboardet mulig uden at joine `P8Adresser` |
| **PrimaerGrundejer** | Enkelt tekstlinje | Navnet på grundejeren, denormaliseret så det kan vises som kolonne i oversigten |
| **SamletPdfUrl** | Hyperlink eller billede | Format: **Hyperlink**. Link til den samlede ansøgnings-PDF fra OS2Forms. Kan stå tom |

> `Title` findes automatisk — opret den ikke selv. Robotten sætter den til ansøgningens
> primære adresse, og falder tilbage til `§8 – <SubmissionSerial>` hvis ansøgningen ikke
> har nogen adresse.

> `Oprettet`/`Created` og `Ændret`/`Modified` findes også automatisk. Bemærk at `Oprettet`
> er *robottens* skrivetidspunkt, ikke ansøgerens — brug `ModtagetDato` i dashboardet.

**Indeksér `SubmissionUUID`:** Listeindstillinger → Indekserede kolonner → Opret nyt
indeks. Uden det bliver robottens dubletopslag langsomt når listen vokser forbi et par
tusind rækker.

---

## 2. P8Adresser

Én række pr. adresse på en ansøgning. En ansøgning kan have flere.

| Kolonnenavn (præcis stavning!) | Type | Indstillinger |
|---|---|---|
| **Ansogning** | Opslag (Lookup) | Hent fra liste `P8Ansogninger`, felt `Title`. Enkelt værdi |
| **SubmissionUUID** | Enkelt tekstlinje | Samme UUID som på hovedlisten. Bør indekseres |
| **Adresse** | Enkelt tekstlinje | Fra formularfeltet `vaelg_adresse` |
| **Matrikel** | Enkelt tekstlinje | Fra `mat` |
| **LokalitetsNummer** | Enkelt tekstlinje | Fra `lokalitets_nummer`. Jordforureningslokalitet |

> `Title` findes automatisk — robotten sætter den til adressen.

---

## 3. P8Kontakter

Én række pr. kontaktperson. En ansøgning har typisk 1-3: udfylderen selv, grundejeren
hvis udfylderen er en anden, og en eventuel ekstern rådgiver.

| Kolonnenavn (præcis stavning!) | Type | Indstillinger |
|---|---|---|
| **Ansogning** | Opslag (Lookup) | Hent fra liste `P8Ansogninger`, felt `Title`. Enkelt værdi |
| **SubmissionUUID** | Enkelt tekstlinje | Bør indekseres |
| **KontaktType** | Valg | Valgmuligheder: `Grundejer`, `Rådgiver`, `Bygherre` |
| **ErUdfylder** | Ja/Nej | Standard: Nej. Markerer hvilken kontakt der faktisk indsendte formularen |
| **Navn** | Enkelt tekstlinje | |
| **Firma** | Enkelt tekstlinje | |
| **Email** | Enkelt tekstlinje | |
| **Telefon** | Enkelt tekstlinje | |
| **Adresse** | Enkelt tekstlinje | Kontaktens egen adresse — ikke ansøgningens lokalitet |
| **By** | Enkelt tekstlinje | |
| **Postnummer** | Enkelt tekstlinje | Tekst, ikke Tal — bevarer foranstillede nuller |

> `Title` findes automatisk — robotten sætter den til kontaktens navn.

---

## 4. P8Vedhaeftninger

Én række pr. uploadet dokument. Filerne bliver liggende i OS2Forms; her gemmes kun
navn og URL.

| Kolonnenavn (præcis stavning!) | Type | Indstillinger |
|---|---|---|
| **Ansogning** | Opslag (Lookup) | Hent fra liste `P8Ansogninger`, felt `Title`. Enkelt værdi |
| **SubmissionUUID** | Enkelt tekstlinje | Bør indekseres |
| **Filnavn** | Enkelt tekstlinje | |
| **FilUrl** | Hyperlink eller billede | Format: **Hyperlink**. Peger ind i OS2Forms |
| **ErSamletPdf** | Ja/Nej | Standard: Nej. Sand for den samlede ansøgnings-PDF, falsk for ansøgers egne uploads |

> `Title` findes automatisk — robotten sætter den til filnavnet.

> **Bemærk:** URL'erne kræver en gyldig API-nøgle for at kunne hentes. Et dashboard der
> blot linker direkte til dem vil give adgangsfejl for almindelige brugere. Skal
> dokumenterne kunne åbnes fra dashboardet, er der to veje: enten henter robotten filerne
> ned og lægger dem som rigtige vedhæftninger på `P8Ansogninger`-elementet, eller også
> proxy'er dashboardet kaldet. Se "Åbne punkter".

---

## Efter oprettelse

- Bekræft at alle fire lister findes under **Site Contents**
- Bekræft at `SubmissionUUID` er indekseret på alle fire lister
- Bekræft at `Ansogning`-lookup-kolonnerne viser værdier fra `P8Ansogninger`
- Opret én testrække manuelt i `P8Ansogninger` og bekræft at en lookup fra
  `P8Adresser` kan finde den
- Bekræft at `Status` og `AfgorelseSkrevet` kan redigeres af sagsbehandlerne, men at
  robottens servicekonto har skriveadgang til alle øvrige felter

---

## Åbne punkter

Disse skal afklares, før robotten kan skrives færdig:

0. **Ny JSON fra blanketten.** Det vigtigste punkt. Blanketten er ændret markant, så
   feltmapningen skal laves forfra. Der skal bruges en rå JSON-udskrift af en indsendelse
   fra den nuværende blanket — både `data`- og `entity`-delen, som endpointet
   `/webform_rest/{webform_id}/submission/{uuid}` returnerer den. Uden den er enhver
   mapning gætværk. Indtil da er kolonnerne ovenfor foreløbige.
1. **Site-URL.** Skal §8-listerne ligge på samme site som master-dashboardet
   (`tea-teamsite10955`), eller på et selvstændigt site for §8-sagsbehandling?
2. **Listenavn-præfiks.** `P8` er valgt her som en kort, æ/ø/å-fri parallel til
   master-dashboardets `MTM`. Sig til hvis det skal hedde noget andet — det skal
   besluttes før oprettelse, da omdøbning ikke ændrer det interne navn.
3. **Vedhæftede dokumenter.** Kun URL (som specificeret nu), eller skal robotten hente
   filerne ned og lægge dem på list-elementet?
4. **`Status`-værdier.** `Ny` / `Under behandling` / `Afgjort` / `Afvist` er et gæt ud
   fra den gamle `status`-kolonne. Hvad er den faktiske sagsgang for en §8-ansøgning?
