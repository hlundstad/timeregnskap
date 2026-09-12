# Oppsett på GitHub

Rekkefølgen under tar deg fra tom konto til en side som viser regnskapet ditt.
Alt kan gjøres fra nettleseren, også på iPhone.

## 1. Lag repoet

github.com → **New repository** → navn `timeregnskap` → Private eller Public →
**Create repository**.

## 2. Legg inn filene

Enklest fra en maskin: pakk ut zip-filen, dra alle filene inn i
«uploading an existing file» på repo-siden.

Fra telefonen, eller hvis du vil ta det i nettleseren: **Add file → Create new
file**, skriv hele stien i navnefeltet (skriver du `.github/workflows/rapport.yml`
lager GitHub mappene selv), lim inn innholdet, **Commit**. Gjenta for hver fil.

Minimum for at siden skal virke:

    timeregnskap.py
    timer.csv
    .github/workflows/rapport.yml

Resten er valgfritt: `app.py`, `requirements.txt`, `Dockerfile` og `render.yaml`
hvis du vil kjøre serveren et sted, `nettleser/` hvis du vil ha den versjonen
som regner ut alt i telefonen, `endepunkt/` for Cloudflare-varianten.

## 3. Slå på Pages

**Settings → Pages → Source: GitHub Actions.** Ingen branch å velge.

## 4. Første kjøring

**Actions → Timeregnskap → Run workflow.** Når den er grønn ligger rapporten på

    https://<brukernavn>.github.io/timeregnskap/

og nettleserversjonen på `…/timeregnskap/app/`.

## 5. Koble til telefonen

Følg **IPHONE.md**. Kort fortalt: et fine-grained token med Contents:
Read and write, og en snarvei som sender CSV-en til

    https://api.github.com/repos/<brukernavn>/timeregnskap/dispatches

Etter det er rutinen: del CSV-en fra tidsappen til snarveien, vent et minutt,
åpne siden.

## Hvis du heller vil ha det gjort for deg

Med Claude Code koblet til GitHub-kontoen din kan Claude opprette repoet og
committe filene selv. I denne chatten finnes ikke det verktøyet.
