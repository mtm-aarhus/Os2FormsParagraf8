# Næste skridt — robotten

Status pr. 25. september 2026. Skrevet så arbejdet kan genoptages uden at skulle
rekonstrueres.

## Hvor vi står

Robotten er **færdigbygget, gennemgået og sikkerhedsgodkendt**, men **ikke sat i drift**.

- Kode: [`mtm-aarhus/Os2FormsParagraf8`](https://github.com/mtm-aarhus/Os2FormsParagraf8), offentlig, `main` beskyttet
- 25 tests grønne, alt kompilerer
- Sikkerhedsgennemgang af kode og hele git-historikken gennemført — se `SIKKERHEDSGENNEMGANG.md`
- Feltmapningen er skrevet og testet mod en faktisk testindsendelse (serienummer 75)

Den har aldrig kørt mod rigtige data. Intet er verificeret mod OS2Forms eller SharePoint.

## Det der mangler, i rækkefølge

### 1. Sæt robotten op i OpenOrchestrator

Credentials, som skal findes eller oprettes:

| Navn | Indhold |
|---|---|
| `OS2FormsAPI` | username = API base-URL, password = API-nøglen |
| `SharePointAPI` | username = tenant-id, password = client-id |
| `SharePointCert` | username = thumbprint, password = sti til .pem |

Constants:

| Navn | Indhold |
|---|---|
| `AarhusKommuneSharePoint` | base-URL til SharePoint |
| `Error Email` | modtager af fejlmails |
| `SmtpServer` | hostnavn på SMTP-relæet |
| `SmtpPort` | port på samme |

Processen henter koden fra den nye URL. Opret to triggere:

- **QueueTrigger** på `Paragraf8Ansogninger` med procesargumentet `no-poll`
- **Planlagt trigger**, fx natlig, uden argument — sikkerhedsnettet der fanger hvad
  webhooken måtte have tabt

### 2. Verificér forbindelsen før noget andet

Kør processen som en SINGLE-trigger med procesargumentet:

```
struktur uuid=f2a5f224-b27d-4bf0-b590-5420ca7e6ba1
```

Den rører hverken køen eller SharePoint — den henter én indsendelse og skriver
blankettens feltstruktur i OO-loggen. Det beviser, at API-nøglen, base-URL'en og
blankettens maskinnavn hænger sammen.

Får du 403: nøglens bruger mangler adgang til netop denne blanket. Adgang gives pr.
blanket i OS2Forms.

### 3. Få webhooken sat op

Kræver en **OS2Forms-administrator** — du har ikke selv rettigheder til at redigere
remote post-URL'er.

- URL: `https://pyorchestrator.aarhuskommune.dk/api/queue`
- Krop: `queue_name`, `reference` og `data` som beskrevet i `POWER-AUTOMATE.md`
- Header: `X-API-Key` — samme nøgle som jeres øvrige OS2-løsninger bruger

### 4. Afklar den gamle Azure-app

`os2data-webhook` kan stadig køre fra før ombygningen. Peger blanketten stadig på den,
lander borgerhenvendelser i en Azure SQL-database, ingen vedligeholder. Bør lukkes ned.

## Åbne punkter i koden

**Filnavne på borgerens bilag mangler.** OS2Forms leverer kun fil-id'er.
REST-API'et har et `/entity/file/{file_id}`-endpoint, som ikke er afprøvet.
`P8Vedhaeftninger.Filnavn` og `FilUrl` står tomme indtil da.

**`navn_kontaktperson_2` findes ikke i blanketten.** Grundejer nr. 2 har adresse, CVR,
firma, mail og telefon, men intet navnefelt. Koden bruger firmanavnet. Det er en mangel
i OS2Forms, ikke i koden.

**PnP-godkendelse i tenanten.** Låser op for automatiseret listeoprettelse og for
`deploy_spfx.ps1` i jordportalen. Godkendelses-URL ligger i jordportalens
`OPRET-LISTER.md`.

## Beslægtet

Frontenden ligger i [`mtm-aarhus/jordportalen`](https://github.com/mtm-aarhus/jordportalen).
Se dens `NAESTE-SKRIDT.md` og `OVERDRAGELSE.md`.
