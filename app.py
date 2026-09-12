"""Timeregnskap – webserver med et endepunkt telefonen kan laste opp til.

    pip install -r requirements.txt
    python app.py                      # http://localhost:8000

Endepunkter:
    GET  /                  rapporten
    POST /opplasting        last opp CSV (felt «file», eller rå tekst i body)
    GET  /rapport.csv       regnskapet som CSV
    GET  /oppsummering.txt  tekstversjonen, klar til å limes inn i en e-post
    GET  /siste.csv         filen du sist lastet opp, slik den kom inn

Er miljøvariabelen TIMEREGNSKAP_TOKEN satt, kreves den som ?token=…,
«Authorization: Bearer …» eller «X-Token»-hode. Første gang du åpner
rapporten med riktig token i adressen, husker nettleseren den i en
informasjonskapsel.
"""

from __future__ import annotations

import hmac
import os
from pathlib import Path

from flask import Flask, Response, make_response, redirect, request

import timeregnskap as tr

DATA = Path(os.environ.get("TIMEREGNSKAP_DATA", "data"))
DATA.mkdir(parents=True, exist_ok=True)
FIL = DATA / "siste.csv"
TOKEN = os.environ.get("TIMEREGNSKAP_TOKEN", "")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024  # 2 MB holder i massevis


# --------------------------------------------------------------------------

def godkjent() -> bool:
    if not TOKEN:
        return True
    oppgitt = (
        request.args.get("token")
        or request.headers.get("X-Token")
        or request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        or request.form.get("token")
        or request.cookies.get("token")
        or ""
    )
    return hmac.compare_digest(oppgitt, TOKEN)


def avvis() -> Response:
    return Response("Feil eller manglende token.\n", status=401, mimetype="text/plain")


def les_lagret() -> str:
    return FIL.read_text(encoding="utf-8-sig") if FIL.exists() else ""


def innstillinger() -> tuple[int, str, str]:
    mal = tr.les_mal(request.args.get("mal", "7,5"))
    regel = request.args.get("regel", "ukedag-med-tid")
    if regel not in tr.REGLER:
        regel = "ukedag-med-tid"
    return mal, regel, request.args.get("navn", "")


def skjema(navn_valg: list[str]) -> str:
    mal_tekst = request.args.get("mal", "7,5")
    _, regel, valgt_navn = innstillinger()
    valg = "".join(
        f'<option value="{k}"{" selected" if k == regel else ""}>{v}</option>'
        for k, v in tr.REGLER.items()
    )
    navn_felt = ""
    if len(navn_valg) > 1:
        alt = '<option value="">Alle</option>' + "".join(
            f'<option{" selected" if n == valgt_navn else ""}>{n}</option>' for n in navn_valg
        )
        navn_felt = f'<div class="felt"><label for="navn">Oppdragsgiver</label>' \
                    f'<select id="navn" name="navn">{alt}</select></div>'
    return f"""
<section class="ikke-print">
  <form class="panel" method="get" action="/">
    <div class="felt"><label for="mal">Mål per dag</label>
      <input id="mal" name="mal" value="{mal_tekst}" inputmode="decimal"></div>
    <div class="felt"><label for="regel">Hvilke dager teller mot målet</label>
      <select id="regel" name="regel">{valg}</select></div>
    {navn_felt}
    <div class="knapper"><button type="submit">Regn om</button>
      <a class="knapp sekundar" href="/rapport.csv">Last ned CSV</a>
      <a class="knapp sekundar" href="/oppsummering.txt">Tekstversjon</a></div>
  </form>
  <details><summary>Last opp ny fil</summary>
    <form class="panel" method="post" action="/opplasting" enctype="multipart/form-data">
      <div class="felt"><label for="file">CSV-fil fra tidsappen</label>
        <input id="file" type="file" name="file" accept=".csv,text/csv,text/plain" required></div>
      <div class="knapper"><button type="submit">Last opp</button></div>
    </form>
  </details>
</section>"""


def tom_side(melding: str = "") -> str:
    kropp = tr._HODE % tr.CSS
    kropp += '<header class="masthead"><h1>Timeregnskap</h1>' \
             '<span class="periode">ingen data</span></header>'
    if melding:
        kropp += f'<div class="melding">{melding}</div>'
    kropp += """
<section><div class="panel">
  <p class="hint">Last opp CSV-filen fra tidsappen, så regnes timer, minutter og
  avvik fra dagsmålet ut her.</p>
  <form method="post" action="/opplasting" enctype="multipart/form-data">
    <div class="felt"><input type="file" name="file" accept=".csv,text/csv,text/plain" required></div>
    <div class="knapper"><button type="submit">Last opp</button></div>
  </form>
</div></section>
<footer>Fra telefonen kan du også sende filen rett hit:
<code>POST /opplasting</code></footer></div></body></html>"""
    return kropp


# --------------------------------------------------------------------------

@app.get("/")
def rapport():
    if not godkjent():
        return avvis()
    tekst = les_lagret()
    if not tekst:
        return tom_side()

    mal, regel, navn = innstillinger()
    try:
        poster, hoppet = tr.les_csv(tekst)
        r = tr.beregn(poster, mal, regel, navn)
    except tr.CsvFeil as e:
        return tom_side(str(e))

    navn_valg = sorted({p.navn for p in poster if p.navn})
    melding = f"Hoppet over {len(hoppet)} rad(er) uten gyldig dato." if hoppet else ""
    side = tr.som_html(r, skjema(navn_valg), melding)

    svar = make_response(side)
    if TOKEN and request.args.get("token"):
        svar.set_cookie("token", TOKEN, max_age=60 * 60 * 24 * 365,
                        httponly=True, samesite="Lax", secure=request.is_secure)
    return svar


@app.post("/opplasting")
def opplasting():
    if not godkjent():
        return avvis()

    innhold = ""
    if "file" in request.files:
        innhold = request.files["file"].read().decode("utf-8-sig", errors="replace")
    if not innhold.strip():
        for felt in ("csv", "data", "text"):
            if felt in request.form:
                innhold = request.form[felt]
                break
    if not innhold.strip():
        innhold = request.get_data(as_text=True)
    if not innhold.strip():
        return Response("Tom fil.\n", status=400, mimetype="text/plain")

    try:
        poster, _ = tr.les_csv(innhold)
    except tr.CsvFeil as e:
        return Response(f"Kunne ikke tolke filen: {e}\n", status=400, mimetype="text/plain")

    FIL.write_text(innhold, encoding="utf-8")

    if request.accept_mimetypes.accept_html and "file" in request.files:
        return redirect("/")
    return Response(f"Lagret {len(poster)} rader.\n", mimetype="text/plain")


@app.get("/rapport.csv")
def rapport_csv():
    if not godkjent():
        return avvis()
    mal, regel, navn = innstillinger()
    try:
        poster, _ = tr.les_csv(les_lagret())
        r = tr.beregn(poster, mal, regel, navn)
    except tr.CsvFeil as e:
        return Response(f"{e}\n", status=404, mimetype="text/plain")
    filnavn = f"timeregnskap-{r.fra}-{r.til}.csv"
    return Response("\ufeff" + tr.som_csv(r), mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{filnavn}"'})


@app.get("/oppsummering.txt")
def oppsummering():
    if not godkjent():
        return avvis()
    mal, regel, navn = innstillinger()
    try:
        poster, _ = tr.les_csv(les_lagret())
        r = tr.beregn(poster, mal, regel, navn)
    except tr.CsvFeil as e:
        return Response(f"{e}\n", status=404, mimetype="text/plain")
    return Response(tr.som_tekst(r) + "\n", mimetype="text/plain; charset=utf-8")


@app.get("/siste.csv")
def siste():
    if not godkjent():
        return avvis()
    tekst = les_lagret()
    if not tekst:
        return Response("Ingen fil lastet opp ennå.\n", status=404, mimetype="text/plain")
    return Response(tekst, mimetype="text/csv; charset=utf-8")


@app.get("/helse")
def helse():
    return {"status": "ok", "har_data": FIL.exists()}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=bool(os.environ.get("DEBUG")))
