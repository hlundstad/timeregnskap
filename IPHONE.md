# Fra iPhone til GitHub

På iPhone finnes det ingen delingsmeny-kobling til nettsider slik Android har,
så veien går via appen **Snarveier** (Shortcuts), som ligger ferdig installert.
Du lager én snarvei, og deretter er jobben: del CSV-filen fra tidsappen →
velg snarveien → åpne siden.

Velg én av de tre måtene under. Den første er den du spør etter: filen sendes
til GitHub, GitHub regner ut, og resultatet ligger på nettsiden din.

---

## 1. Send til GitHub, se resultatet på GitHub Pages

GitHub Pages kan bare vise filer, men GitHub *selv* har et API som kan ta imot.
Snarveien varsler repoet ditt, `.github/workflows/rapport.yml` kjører Python og
publiserer ferdig rapport på Pages. Tar omtrent ett minutt.

### Engangsoppsett

1. Legg `timeregnskap.py` og mappa `.github/workflows/` i et repo, for eksempel `timeregnskap`.
2. **Settings → Pages → Source: GitHub Actions.**
3. Lag et tilgangstoken: **Settings** (på profilen din, ikke repoet) **→ Developer settings → Personal access tokens → Fine-grained tokens → Generate new token.**
   - Repository access: bare dette ene repoet
   - Permissions → Repository permissions → **Contents: Read and write**
   - Kopier tokenet. Det vises bare én gang.

### Snarveien

Ny snarvei, og slå på **Vis i delingsark** under snarveiens innstillinger, med
«Filer» som godtatt type.

| Handling | Innstilling |
| --- | --- |
| Hent tekst fra inndata | inndata = Snarveiinndata |
| Hent innhold fra URL | se under |
| Åpne URL-er | `https://<brukernavn>.github.io/timeregnskap/` |

For «Hent innhold fra URL»:

- URL: `https://api.github.com/repos/<brukernavn>/timeregnskap/dispatches`
- Metode: **POST**
- Headers:
  - `Authorization` → `Bearer <tokenet ditt>`
  - `Accept` → `application/vnd.github+json`
- Forespørselstekst: **JSON**
  - `event_type` (Tekst) → `timer`
  - `client_payload` (Ordbok) → nøkkel `csv` (Tekst) → variabelen **Tekst** fra forrige steg

Legg gjerne inn «Vent 60 sekunder» før «Åpne URL-er», så er siden oppdatert når
den åpner seg.

### Slik bruker du den

Eksporter CSV fra tidsappen → Del → snarveien din. GitHub kjører utregningen,
filen blir liggende som `timer.csv` i repoet, og rapporten havner på
`https://<brukernavn>.github.io/timeregnskap/`. Den kan du åpne fra hvilken som
helst maskin — praktisk når du skal sende regnskapet videre til arbeidsgiver.

Vil du sjekke at det virker før du lager snarveien, kan du prøve fra en maskin:

```bash
curl -X POST https://api.github.com/repos/<brukernavn>/timeregnskap/dispatches \
  -H "Authorization: Bearer <token>" \
  -H "Accept: application/vnd.github+json" \
  -d "$(python3 -c 'import json,sys;print(json.dumps({"event_type":"timer","client_payload":{"csv":open("timer.csv").read()}}))')"
```

---

## 2. Uten token: send filen i lenken

Nettleserversjonen (`timeregnskap/index.html`) leser CSV-en rett ut av adressen,
så du trenger verken server, token eller ventetid. Regnestykket skjer i Safari.

| Handling | Innstilling |
| --- | --- |
| Hent tekst fra inndata | inndata = Snarveiinndata |
| Base64-koding | kod Tekst |
| Tekst | `https://<brukernavn>.github.io/timeregnskap/#data=` + variabelen **Base64-kodet** |
| Åpne URL-er | variabelen **Tekst** |

Del CSV-en til snarveien, så åpner siden seg med tallene ferdig utregnet. En
måned med data blir en lenke på under tusen tegn, så det er god plass.

Ulempen: tallene vises bare på telefonen der du åpnet lenken. Siden husker
riktignok siste fil lokalt, så neste gang du åpner den vanlige adressen ligger
de der fortsatt.

---

## 3. Ekte endepunkt, side på GitHub

Vil du ha en fast adresse tidsappen kan poste til helt av seg selv, setter du
opp Python-serveren (`app.py` på Render) eller Cloudflare Worker-en. Da laster
telefonen opp til endepunktet, og siden på GitHub Pages henter derfra:

- I snarveien: «Hent innhold fra URL», POST til `https://<endepunktet>/opplasting?token=…`, forespørselstekst = **Fil** = Snarveiinndata.
- I nettleserversjonen: åpne «Andre måter å hente filen på», lim inn `https://<endepunktet>/siste.csv?token=…` og kryss av for automatisk henting.

Kan tidsappen selv poste til en URL, trenger du ikke snarvei i det hele tatt.

---

## Hvilken bør du velge?

Vil du se regnskapet fra flere enheter og ha historikken liggende i repoet,
er **1** riktig. Skal det bare gå fort på telefonen, er **2** minst oppsett.
**3** er den eneste som lar tidsappen sende filen uten at du er involvert.

Ellers: legg siden til på Hjem-skjermen i Safari (Del → Legg til på
Hjem-skjerm), så åpner den seg uten adressefelt og oppfører seg som en vanlig
app.
