# Timeregnskap (Python)

Samme regnskap som nettleserversjonen, men skrevet i Python. Leser en CSV-fil
med arbeidstid per dag og viser

- timer og minutter per dag, og avviket fra dagsmålet (7,5 timer som standard)
- sum for perioden og samlet avvik
- totaler per uke, og hvor mye snittuka ligger over eller under målet
- eksport til CSV og en tekstversjon du kan lime rett inn i en e-post

Filene:

| Fil | Hva den gjør |
| --- | --- |
| `timeregnskap.py` | all innlesing og utregning, og et kommandolinjeverktøy. Ingen tredjepartspakker |
| `app.py` | Flask-server med opplastings-endepunktet og rapporten |
| `Dockerfile`, `render.yaml` | to måter å få serveren ut på nett |
| `.github/workflows/rapport.yml` | alternativet uten server: GitHub tar imot filen og lager rapporten |
| `IPHONE.md` | tre oppskrifter for å få filen fra iPhone og inn i appen |

## Kommandolinje

```bash
python timeregnskap.py timer.csv
python timeregnskap.py timer.csv --mal 7:30 --regel alle-ukedager
python timeregnskap.py timer.csv --html rapport.html --csv regnskap.csv
cat timer.csv | python timeregnskap.py -
```

Utskrift:

```
Totalt jobbet: 51 t 13 m (51,21 timer)
Mål totalt:    52 t 30 m på 7 dager
Avvik:         −1 t 17 m
Snitt per uke: 25 t 36 m (mål 26 t 15 m, avvik −0 t 39 m)
```

## Server med opplastings-endepunkt

```bash
pip install -r requirements.txt
export TIMEREGNSKAP_TOKEN=noe-langt-og-tilfeldig
python app.py            # http://localhost:8000
```

| Rute | |
| --- | --- |
| `GET /` | rapporten, med skjema for dagsmål og regel |
| `POST /opplasting` | tar imot CSV-en: enten et filfelt `file`, eller filen rå i kroppen |
| `GET /rapport.csv` | regnskapet som CSV |
| `GET /oppsummering.txt` | tekstversjonen |
| `GET /siste.csv` | filen slik den kom inn |

Fra telefonen, for eksempel med Snarveier (iOS) eller HTTP Shortcuts (Android):

```bash
curl -T timer.csv "https://<adressen-din>/opplasting?token=HEMMELIG"
# eller
curl -F file=@timer.csv "https://<adressen-din>/opplasting?token=HEMMELIG"
```

Er `TIMEREGNSKAP_TOKEN` satt, kreves den på alle ruter — som `?token=…`, som
`Authorization: Bearer …` eller som `X-Token`-hode. Åpner du rapporten med
tokenet i adressen én gang, husker nettleseren det i en informasjonskapsel, så
lenken blir kort etterpå. Uten tokenet satt er alt åpent, som er greit lokalt,
men ikke på nett.

Filen lagres som `data/siste.csv` (styres av `TIMEREGNSKAP_DATA`).

### Hvor du kan hoste den

GitHub Pages kan **ikke** kjøre Python — det er ren filservering. Serveren
trenger derfor et annet sted å bo. Koden kan fortsatt ligge på GitHub:

- **Render** — `render.yaml` ligger klar. New → Blueprint → velg repoet. Gratisnivået sover når det ikke er i bruk, og våkner på første forespørsel.
- **Fly.io, Railway, Koyeb** — bruk `Dockerfile`.
- **PythonAnywhere** — pek WSGI-filen på `app:app`.
- **Din egen maskin eller en Raspberry Pi** — `python app.py`, og nå den fra telefonen på hjemmenettet.

### Uten server i det hele tatt

Vil du holde deg til GitHub alene, tar `.github/workflows/rapport.yml` imot
filen for deg. Telefonen sender en `repository_dispatch` til GitHub-API-et,
workflowen kjører `timeregnskap.py`, lagrer filen som `timer.csv` i repoet og
publiserer rapporten på GitHub Pages. Slå på Settings → Pages → Source: GitHub
Actions først. Framgangsmåten fra iPhone står i **[IPHONE.md](IPHONE.md)**.

## Formatet på filen

Skilletegn `;`, `,` eller tabulator oppdages automatisk.

```
Name;Period;Duration (sec);Hours;Minutes;Seconds
Skatteetaten;2026-09-11;22500;6;15;0
```

Det eneste som kreves er en datokolonne (`Period`, `Dato`, `Date` …) og en
varighet. Varigheten leses fra `Duration (sec)` hvis den finnes, ellers regnes
den ut fra `Hours`, `Minutes` og `Seconds`. Datoene `2026-09-11`, `11.09.2026`
og `11/09/2026` forstås. Flere rader på samme dato legges sammen, og er det
flere navn i `Name`-kolonnen kan du velge ett av dem.

## Hvilke dager teller mot målet

`--regel` på kommandolinjen, nedtrekksmeny i nettleseren:

- `ukedag-med-tid` (standard) — en mandag med 0 timer regnes som fri og gir ikke minus. Jobber du en lørdag, blir alt du fører der pluss.
- `alle-med-tid` — også helgedager får dagsmålet som krav.
- `alle-ukedager` — ukedager som mangler i filen fylles inn med 0 timer og full minus. Bruk denne hvis fravær skal synes som underskudd.

Dagsmålet skrives som `7,5` eller `7:30`.
