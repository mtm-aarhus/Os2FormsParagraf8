> # ⚠️ Forældet — brug ikke denne
>
> Listespecifikationen er flyttet til **Jordportalen**, SPFx-frontenden, som nu definerer
> størstedelen af skemaet: status, ansvarlig, kommentarer, noter, opgaver, dokumenter og
> links. Dette dokument beskriver kun de fire lister robotten selv skriver til, og mangler
> de fem nye — samt ændringerne til `P8Ansogninger` (`Ansvarlig`, `AfventerAarsag`, og
> fjernelsen af `AfgorelseSkrevet`).
>
> **Den gældende specifikation ligger i `jordportalen/SHAREPOINT-LISTER.md`.**
>
> Filen her slettes og erstattes af et link, når jordportalens repo er oprettet.

# §8-ansøgninger — SharePoint-lister (manuel oprettelse)

**Site:** `https://aarhuskommune.sharepoint.com/teams/NaturogMiljDashboard`

Samme site som SPFx-frontenden bygges på. Siden der skal vise dem er
[§8-Ansøgninger – Jord og Grundvand](https://aarhuskommune.sharepoint.com/teams/NaturogMiljDashboard/SitePages/%C2%A78-Ans%C3%B8gninger---Jord-og-Grundvand.aspx).

Alle lister oprettes som **Brugerdefineret liste** ("Custom List" / Generic List) via
**Site Contents → Ny → Liste → Tom liste**.

Kolonnenavnet du taster ind bestemmer det **interne navn**, som både robotten og
SPFx-dashboardet skriver til — men det bliver ikke nødvendigvis det samme. Derfor skal
navnene staves **præcis** som vist. Læs afsnittet om interne kolonnenavne nedenfor, før
du opretter noget.

Kolonnerne herunder er udledt af en faktisk testindsendelse fra den nuværende blanket
(serienummer 75, 23/09/2026), ikke af den gamle SQL-model.

---

## Designprincipper

Strukturen er valgt med SPFx-dashboardet for øje:

- **Én hovedliste, tre detaljelister.** `P8Ansogninger` er den liste dashboardet lister,
  filtrerer og sorterer. Adresser, kontakter og vedhæftninger ligger i hver sin liste og
  hentes kun når en enkelt ansøgning åbnes.
- **Denormaliserede felter på hovedlisten.** `AntalAdresser`, `AdresserTekst`,
  `Grundejere` m.fl. vedligeholdes af robotten, så oversigten kan renderes med ét kald i
  stedet for et opslag pr. række. Samme mønster som `AntalReaktioner` /
  `AntalKommentarer` i master-dashboardet.
- **Intet felt antager ét af noget.** En ansøgning kan have ubegrænset mange adresser og
  op til to ligestillede grundejere. Derfor er der ingen `PrimaerAdresse` eller
  `PrimaerGrundejer` — de denormaliserede felter er flerlinjede opsummeringer, og
  detaljelisterne er sandheden.
- **`SubmissionUUID` på alle fire lister.** Detaljelisterne har både en Lookup til
  ansøgningen (til dashboardet) *og* det rå UUID som tekst (så robotten kan slå op uden
  først at oversætte til et list-item-ID).
- **`SubmissionUUID` er idempotensnøglen.** Robotten henter alle eksisterende UUID'er én
  gang pr. kørsel og springer dem over, så en kørsel kan gentages uden dubletter.

---

## Interne kolonnenavne — læs dette først

Det navn du taster ind er kolonnens **visningsnavn**. SharePoint udleder et **internt
navn** af det ved oprettelsen, og det er det interne navn koden skriver til. De to falder
fra hinanden på tre måder, som alle har kostet tid i MTM's øvrige robotter:

1. **Specialtegn kodes om.** Bindestreg bliver til `_x002d_`, `ø` til `_x00f8_`, mellemrum
   til `_x0020_`. Derfor hedder kolonnen der vises som "Az-ident" internt
   `Az_x002d_ident`.
2. **Navnet afkortes ved 32 tegn.** "Organisatorisk enhed over medarbejder" blev internt
   til `Organisatoriskenhedovermedarbejd` — afhugget midt i et ord, men korrekt.
3. **Omdøbning ændrer kun visningsnavnet.** Det interne navn er låst fra oprettelsen.

Værst er den fjerde: **to kolonner kan have samme visningsnavn.** I MTM's Altinget-liste
findes `Magistratsafdeling`, `Magistratsafdeling0` og `Magistratsafdeling1`, som alle
vises som "Magistratsafdeling". Skriver robotten til den forkerte, **lykkes kaldet uden
fejl** — værdien lander bare i en kolonne visningen ikke viser.

**Derfor:** navnene i denne specifikation er med vilje korte, rene ASCII-navne uden
mellemrum, bindestreger eller æ/ø/å, og alle under 32 tegn. Taster du dem præcis som vist,
bliver det interne navn identisk med visningsnavnet.

Bekræft det alligevel efter oprettelsen med `get_internal_column_names()` i
`src/sharepoint_client.py`.

---

## Rækkefølge

`P8Ansogninger` skal oprettes først, da de tre øvrige lister har en Lookup til den:

1. `P8Ansogninger`
2. `P8Adresser`
3. `P8Kontakter`
4. `P8Vedhaeftninger`

---

## 1. P8Ansogninger

Hovedlisten — én række pr. indsendt §8-ansøgning.

| Kolonnenavn (præcis stavning!) | Type | Fra blanketten | Indstillinger |
|---|---|---|---|
| **SubmissionUUID** | Enkelt tekstlinje | `uuid` | Unik nøgle. Robottens dubletsikring. **Skal indekseres** |
| **SubmissionSerial** | Tal | `serial` | 0 decimaler. Fortløbende pr. blanket — bruges til at opdage huller |
| **SubmissionSid** | Tal | `sid` | 0 decimaler. OS2Forms' interne id, bruges til at bygge linket tilbage |
| **OS2FormsUrl** | Hyperlink eller billede | *(udledt af `sid`)* | Format: **Hyperlink**. Link til indsendelsen i OS2Forms, så sagsbehandleren kan se originalen |
| **Udfylder** | Enkelt tekstlinje | `udfylder` | Navnet på den der udfyldte blanketten |
| **IndsendtAf** | Valg | `ansoegning_indsendt_af` | Valgmuligheder: `Grundejer`, `Bygherre`, `Rådgiver`. Der er ingen `Andet` |
| **AnsogningsDato** | Dato og klokkeslæt | `vaelg_dato_for_ansoegning` | Inkluder klokkeslæt: **Nej**. Kommer som `YYYY-MM-DD` |
| **Bemaerkninger** | Flere tekstlinjer | `bemaerkninger` | Almindelig tekst (ikke Rich Text) |
| **ModtagetDato** | Dato og klokkeslæt | `created` | Inkluder klokkeslæt: **Ja**. Kommer som Unix-tidsstempel |
| **AfsluttetDato** | Dato og klokkeslæt | `completed` | Inkluder klokkeslæt: **Ja**. Unix-tidsstempel. Kan stå tom |
| **FlereGrundejere** | Ja/Nej | `er_der_flere_grundejere` | Standard: Nej. Styrer om `_2`-kontakten gælder |
| **BygherreSammeSomGrundejer** | Ja/Nej | `er_bygherre_den_samme_som_grundejer` | Standard: Nej. Er den Ja, oprettes ingen selvstændig bygherre-kontakt |
| **Status** | Valg | *(sagsbehandler)* | `Ny`, `Under behandling`, `Afgjort`, `Afvist`. Standard: `Ny`. **Robotten sætter den kun ved oprettelse og rører den aldrig igen** |
| **AfgorelseSkrevet** | Ja/Nej | *(sagsbehandler)* | Standard: Nej |
| **AntalAdresser** | Tal | *(udledt)* | 0 decimaler, standard 0. Denormaliseret |
| **AntalKontakter** | Tal | *(udledt)* | 0 decimaler, standard 0. Denormaliseret |
| **AntalVedhaeftninger** | Tal | *(udledt)* | 0 decimaler, standard 0. Denormaliseret |
| **AdresserTekst** | Flere tekstlinjer | *(udledt)* | Alle adresser, én pr. linje. Antallet er ubegrænset, så feltet kan blive langt — det er en søge- og oversigtsfelt, ikke et display-felt |
| **Grundejere** | Flere tekstlinjer | *(udledt)* | Grundejernes navne, ét pr. linje. Der kan være to ligestillede |

> `Title` findes automatisk — opret den ikke selv. Robotten sætter den til ansøgningens
> første adresse, med `(+N flere)` bagefter hvis der er flere, og falder tilbage til
> `§8 – <SubmissionSerial>` hvis ansøgningen ikke har nogen adresse.

> `Oprettet`/`Created` findes også automatisk, men er *robottens* skrivetidspunkt, ikke
> ansøgerens. Brug `ModtagetDato` i dashboardet.

> **Datoer gemmes i UTC.** SharePoint lagrer alle DateTime-felter i UTC. Skriver man en
> dansk dato uden tidszone, forskydes den ved visning — typisk en dag tilbage, fordi
> midnat dansk tid er den foregående dag i UTC. Robotten sender derfor alle datoer
> gennem `src/datoer.py`. Det gælder også `AnsogningsDato`, selvom den ikke har noget
> klokkeslæt — det er netop dér fejlen er nemmest at overse.
>
> **Sitet skal stå til dansk tid.** Konverteringen forudsætter at SharePoint regner
> tilbage til Europe/Copenhagen ved visning. En ansøgningsdato på 21. februar gemmes som
> `2017-02-20T23:00:00Z`; står sitets regionale indstillinger til UTC i stedet for
> dansk tid, vises den som **den 20.** Tjek **Webstedsindstillinger → Regionale
> indstillinger → Tidszone** før listerne tages i brug. Fejlen er tavs og rammer kun
> datoer nær midnat, så den er svær at opdage bagefter.

**Indeksér `SubmissionUUID`:** Listeindstillinger → Indekserede kolonner → Opret nyt
indeks.

---

## 2. P8Adresser

Én række pr. ejendom på ansøgningen. **Antallet er ubegrænset** — ansøger kan tilføje så
mange ejendomme til projektet som ønsket. Det er grunden til at adresser ligger i en egen
liste frem for i felter på ansøgningen.

Kommer fra `adresser` i blanketten, som er en liste af blokke med tre felter.

| Kolonnenavn (præcis stavning!) | Type | Fra blanketten | Indstillinger |
|---|---|---|---|
| **Ansogning** | Opslag (Lookup) | | Hent fra `P8Ansogninger`, felt `Title`. Enkelt værdi |
| **SubmissionUUID** | Enkelt tekstlinje | | **Skal indekseres** |
| **Adresse** | Enkelt tekstlinje | `vaelg_adresse` | Hele adressen på én linje, fx `Eksempelvej 1, 9999 Eksempelby` |
| **Matrikel** | Enkelt tekstlinje | `mat` | |
| **LokalitetsNummer** | Enkelt tekstlinje | `lokalitets_nummer` | Jordforureningslokalitet |

> `Title` findes automatisk — robotten sætter den til adressen.

To konsekvenser af at antallet er ubegrænset:

- Denne liste vokser hurtigere end `P8Ansogninger`. Indekset på `SubmissionUUID` er
  **ikke valgfrit** — uden det rammer man SharePoints grænse på 5.000 elementer pr.
  visning, og opslag begynder at fejle frem for bare at blive langsomme.
- Dashboardet bør hente adresser for én ansøgning ad gangen, ikke for hele oversigten.
  `AdresserTekst` på hovedlisten findes netop for at kunne vise og søge uden at joine.

---

## 3. P8Kontakter

Én række pr. kontaktperson.

Blanketten er **flad**: kontaktoplysninger ligger ikke i indlejrede blokke, men som
parallelle felter med suffiks. Mapningen er:

| Suffiks | Rolle | Felter |
|---|---|---|
| *(intet)* | Grundejer | `navn_kontaktperson`, `evt_firma`, `cvr`, `e_mail`, `telefon_nr`, `adresse` |
| `_2` | Grundejer (nr. 2) | `evt_firma_2`, `cvr_2`, `e_mail_2`, `telefon_nr_2`, `adresse_2` |
| `_byg` | Bygherre | `navn_kontaktperson_byg`, `evt_firma_byg`, `cvr_byg`, `e_mail__byg`, `telefon_nr_byg`, `adresse_byg` |
| `_raad` | Rådgiver | `navn_kontaktperson_raad`, `evt_firma_raad`, `cvr_raad`, `e_mail_raad`, `telefon_nr_raad`, `adresse_raad` |

**To uregelmæssigheder i blanketten**, som koden er nødt til at tage højde for:

- `e_mail__byg` har **dobbelt underscore**, i modsætning til `e_mail_2` og `e_mail_raad`.
  Det er formentlig en tastefejl i blanketopbygningen, men det er det faktiske feltnavn.
- `navn_kontaktperson_2` **findes ikke**. Grundejer nr. 2 har adresse, CVR, firma, mail og
  telefon, men intet navnefelt. Se åbent punkt 2.

| Kolonnenavn (præcis stavning!) | Type | Indstillinger |
|---|---|---|
| **Ansogning** | Opslag (Lookup) | Hent fra `P8Ansogninger`, felt `Title`. Enkelt værdi |
| **SubmissionUUID** | Enkelt tekstlinje | **Skal indekseres** |
| **KontaktType** | Valg | `Grundejer`, `Bygherre`, `Rådgiver` |
| **ErUdfylder** | Ja/Nej | Standard: Nej. Sand for den rolle `ansoegning_indsendt_af` peger på |
| **Navn** | Enkelt tekstlinje | Kan stå tom for grundejer nr. 2 |
| **Firma** | Enkelt tekstlinje | |
| **CVR** | Enkelt tekstlinje | Tekst, ikke Tal — bevarer foranstillede nuller |
| **Email** | Enkelt tekstlinje | |
| **Telefon** | Enkelt tekstlinje | Tekst. Formatet varierer i blanketten |
| **Adresse** | Enkelt tekstlinje | Kontaktens egen adresse på én linje — ikke ansøgningens lokalitet |

> `Title` findes automatisk — robotten sætter den til kontaktens navn, eller til firmaet
> hvis navnet mangler.

**Der kan være to grundejere, men ikke altid.** `KontaktType` er derfor ikke unik — der
kan optræde flere rækker med `Grundejer` på samme ansøgning. Dashboardet må ikke antage
én ejer og slå op på "den første"; det skal hente alle rækker af typen og vise dem som en
gruppe.

**Bygherre oprettes kun hvis `er_bygherre_den_samme_som_grundejer` er Nej.** Er den Ja, er
bygherren grundejeren, og der skal ikke oprettes en dublet. Bemærk at blanketten godt kan
indeholde udfyldte `_byg`-felter *selvom* flaget er Ja — flaget vinder.

---

## 4. P8Vedhaeftninger

Én række pr. uploadet dokument, fra `upload_dokumenter`.

| Kolonnenavn (præcis stavning!) | Type | Indstillinger |
|---|---|---|
| **Ansogning** | Opslag (Lookup) | Hent fra `P8Ansogninger`, felt `Title`. Enkelt værdi |
| **SubmissionUUID** | Enkelt tekstlinje | **Skal indekseres** |
| **FilId** | Enkelt tekstlinje | OS2Forms' fil-id. Blanketten leverer kun id'et, ikke en URL |
| **Filnavn** | Enkelt tekstlinje | Kan stå tom indtil fil-id'et er slået op |
| **FilUrl** | Hyperlink eller billede | Format: **Hyperlink**. Kan stå tom. Se åbent punkt 1 |

> `Title` findes automatisk — robotten sætter den til filnavnet, eller til fil-id'et hvis
> navnet ikke kendes.

---

## Efter oprettelse

- Bekræft at sitets tidszone står til **(UTC+01:00) Bruxelles, København, Madrid, Paris**
  under Webstedsindstillinger → Regionale indstillinger. Står den forkert, vises
  ansøgningsdatoer en dag for tidligt
- Bekræft at alle fire lister findes under **Site Contents**
- Bekræft at `SubmissionUUID` er indekseret på **alle fire** lister
- Bekræft at `Ansogning`-lookup-kolonnerne viser værdier fra `P8Ansogninger`
- Kør `get_internal_column_names()` på hver liste og bekræft at interne navne er identiske
  med visningsnavnene
- Bekræft at `Status` og `AfgorelseSkrevet` kan redigeres af sagsbehandlerne, og at
  robottens servicekonto har skriveadgang til alle øvrige felter

---

## Åbne punkter

1. **Vedhæftede filer.** `upload_dokumenter` leverer kun fil-id'er (fx `507417`), ikke
   URL'er eller filnavne. REST-API'et har et `/entity/file/{file_id}`-endpoint, som
   formentlig kan slå dem op — det skal verificeres mod et rigtigt REST-svar. Indtil da
   gemmer robotten fil-id'et, og `Filnavn`/`FilUrl` står tomme.
2. **`navn_kontaktperson_2` mangler i blanketten.** Skal grundejer nr. 2 kunne angive et
   kontaktnavn? Hvis ja, skal feltet tilføjes i OS2Forms — det er ikke noget koden kan
   løse. Indtil da oprettes kontakten uden navn, med firmaet som `Title`.
3. **Sagsgangen.** `Ny` / `Under behandling` / `Afgjort` / `Afvist` er et gæt. Hvad er den
   faktiske proces for en §8-ansøgning?
4. **Listenavn-præfiks.** `P8` er valgt som en kort, æ/ø/å-fri parallel til
   master-dashboardets `MTM`. Skal besluttes før oprettelse — omdøbning ændrer ikke det
   interne navn.

## Afklaret

- **Site:** `/teams/NaturogMiljDashboard` — samme som SPFx-frontenden.
- **`ansoegning_indsendt_af`:** kun `Grundejer`, `Bygherre` og `Rådgiver`. Ingen `Andet`.
