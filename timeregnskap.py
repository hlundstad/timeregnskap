"""Timeregnskap – regner om sekunder per dag til timer, minutter og avvik.

Ingen tredjepartspakker. Kan brukes som bibliotek, som kommandolinjeverktøy
eller av webserveren i app.py.

    python timeregnskap.py timer.csv
    python timeregnskap.py timer.csv --mal 7,5 --html rapport.html
"""

from __future__ import annotations

import argparse
import csv
import html
import io
import re
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta

UKEDAG = ["man", "tir", "ons", "tor", "fre", "lør", "søn"]

REGLER = {
    "ukedag-med-tid": "Ukedager med registrert tid",
    "alle-med-tid": "Alle dager med registrert tid",
    "alle-ukedager": "Alle ukedager i perioden, også uten tid",
}


# --------------------------------------------------------------------------
# Formatering
# --------------------------------------------------------------------------

def hm(sekunder: float) -> str:
    """3 600 -> '1 t 00 m'. Tegnet håndteres av signert()."""
    a = abs(round(sekunder))
    t, rest = divmod(a, 3600)
    m = round(rest / 60)
    if m == 60:
        t += 1
        m = 0
    return f"{t} t {m:02d} m"


def signert(sekunder: float) -> str:
    r = round(sekunder / 60)
    if r == 0:
        return "0 t 00 m"
    return ("+" if r > 0 else "−") + hm(sekunder)


def desimal(sekunder: float) -> str:
    return f"{sekunder / 3600:.2f}".replace(".", ",")


def kort(d: date) -> str:
    return f"{d.day:02d}.{d.month:02d}"


def les_mal(tekst: str) -> int:
    """'7,5', '7.5' eller '7:30' -> sekunder."""
    t = (tekst or "").strip().replace(" ", "")
    m = re.fullmatch(r"(\d+):(\d{1,2})", t)
    if m:
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60
    try:
        return round(float(t.replace(",", ".")) * 3600)
    except ValueError:
        return 27000


# --------------------------------------------------------------------------
# Innlesing
# --------------------------------------------------------------------------

@dataclass
class Post:
    dato: date
    sek: int
    navn: str = ""


class CsvFeil(ValueError):
    """Filen kunne ikke tolkes."""


def _tall(verdi) -> float | None:
    if verdi is None:
        return None
    t = str(verdi).replace("\u00a0", "").replace(" ", "").replace(",", ".")
    if not t:
        return None
    try:
        return float(t)
    except ValueError:
        return None


def _dato(verdi) -> date | None:
    if not verdi:
        return None
    t = str(verdi).strip()
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", t)
    if m:
        return date(int(m[1]), int(m[2]), int(m[3]))
    m = re.match(r"^(\d{1,2})[./-](\d{1,2})[./-](\d{4})", t)
    if m:
        return date(int(m[3]), int(m[2]), int(m[1]))
    m = re.fullmatch(r"(\d{1,2})[./-](\d{1,2})[./-](\d{2})", t)
    if m:
        return date(2000 + int(m[3]), int(m[2]), int(m[1]))
    return None


def _rens(s: str) -> str:
    return re.sub(r"[^a-z0-9æøå]", "", str(s).lower())


def _kolonner(hode: list[str]) -> dict[str, int]:
    navn = [_rens(h) for h in hode]

    def finn(monster: str) -> int:
        for i, h in enumerate(navn):
            if re.search(monster, h):
                return i
        return -1

    return {
        "dato": finn(r"^(periode|period|dato|date|dag|day)"),
        "varighet": finn(r"(duration|varighet|totalsek)"),
        "timer": finn(r"^(hours|hrs|timer|time|t)$"),
        "min": finn(r"^(minutes|minutter|min|m)$"),
        "sek": finn(r"^(seconds|sekunder|sek|s)$"),
        "navn": finn(r"(name|navn|prosjekt|project|kunde|client|oppdrag)"),
    }


def les_csv(tekst: str) -> tuple[list[Post], list[int]]:
    """Returnerer (poster, linjenumre som ble hoppet over)."""
    ren = tekst.lstrip("\ufeff").strip()
    if not ren:
        raise CsvFeil("Filen er tom.")

    forste = ren.splitlines()[0]
    skille = max([";", ",", "\t"], key=forste.count)
    if forste.count(skille) == 0:
        skille = ";"

    rader = [r for r in csv.reader(io.StringIO(ren), delimiter=skille) if any(f.strip() for f in r)]
    rader = [[f.strip() for f in r] for r in rader]
    if not rader:
        raise CsvFeil("Filen har ingen rader.")

    kol = _kolonner(rader[0])
    start = 1
    if kol["dato"] < 0 and kol["varighet"] < 0:
        # Ingen gjenkjent overskrift – anta navn;dato;sekunder
        start = 0
        if _dato(rader[0][0]) is not None:
            kol = {"navn": -1, "dato": 0, "varighet": 1, "timer": -1, "min": -1, "sek": -1}
        else:
            kol = {"navn": 0, "dato": 1, "varighet": 2, "timer": 3, "min": 4, "sek": 5}
    if kol["dato"] < 0:
        raise CsvFeil("Fant ingen datokolonne. Forventet en kolonne som Period, Dato eller Date.")

    def celle(rad, i):
        return rad[i] if 0 <= i < len(rad) else None

    poster: list[Post] = []
    hoppet: list[int] = []
    for nr, rad in enumerate(rader[start:], start=start + 1):
        d = _dato(celle(rad, kol["dato"]))
        if d is None:
            hoppet.append(nr)
            continue
        sek = _tall(celle(rad, kol["varighet"])) if kol["varighet"] >= 0 else None
        if sek is None:
            t = _tall(celle(rad, kol["timer"])) or 0
            m = _tall(celle(rad, kol["min"])) or 0
            s = _tall(celle(rad, kol["sek"])) or 0
            sek = t * 3600 + m * 60 + s
        poster.append(Post(d, max(0, round(sek)), (celle(rad, kol["navn"]) or "") if kol["navn"] >= 0 else ""))

    if not poster:
        raise CsvFeil("Fant ingen rader med både dato og tid.")
    return poster, hoppet


# --------------------------------------------------------------------------
# Beregning
# --------------------------------------------------------------------------

@dataclass
class Dag:
    dato: date
    sek: int
    teller: bool = False
    mal: int = 0

    @property
    def diff(self) -> int:
        return self.sek - self.mal

    @property
    def ukedag(self) -> str:
        return UKEDAG[self.dato.weekday()]


@dataclass
class Uke:
    aar: int
    nr: int
    fra: date
    til: date
    sek: int = 0
    mal: int = 0
    dager: int = 0

    @property
    def diff(self) -> int:
        return self.sek - self.mal

    @property
    def navn(self) -> str:
        return f"Uke {self.nr}"


@dataclass
class Regnskap:
    dagsmal: int
    regel: str
    dager: list[Dag] = field(default_factory=list)
    uker: list[Uke] = field(default_factory=list)
    navn: str = ""

    @property
    def sum_sek(self) -> int:
        return sum(d.sek for d in self.dager)

    @property
    def sum_mal(self) -> int:
        return sum(d.mal for d in self.dager)

    @property
    def diff(self) -> int:
        return self.sum_sek - self.sum_mal

    @property
    def antall_dager(self) -> int:
        return sum(1 for d in self.dager if d.teller)

    @property
    def snitt_dag(self) -> float:
        return self.sum_sek / self.antall_dager if self.antall_dager else 0.0

    @property
    def snitt_uke(self) -> float:
        return self.sum_sek / len(self.uker) if self.uker else 0.0

    @property
    def mal_uke(self) -> float:
        return self.sum_mal / len(self.uker) if self.uker else 0.0

    @property
    def fra(self) -> date:
        return self.dager[0].dato

    @property
    def til(self) -> date:
        return self.dager[-1].dato

    @property
    def periode(self) -> str:
        return f"{kort(self.fra)}–{kort(self.til)}.{self.til.year}"


def beregn(poster: list[Post], dagsmal: int = 27000,
           regel: str = "ukedag-med-tid", navn: str = "") -> Regnskap:
    valgte = [p for p in poster if not navn or p.navn == navn]
    if not valgte:
        raise CsvFeil("Ingen rader for dette valget.")

    per_dag: dict[date, int] = {}
    for p in valgte:
        per_dag[p.dato] = per_dag.get(p.dato, 0) + p.sek

    if regel == "alle-ukedager":
        d, slutt = min(per_dag), max(per_dag)
        while d <= slutt:
            if d.weekday() < 5:
                per_dag.setdefault(d, 0)
            d += timedelta(days=1)

    dager: list[Dag] = []
    for d in sorted(per_dag):
        sek = per_dag[d]
        ukedag = d.weekday() < 5
        if regel == "alle-med-tid":
            teller = sek > 0
        elif regel == "alle-ukedager":
            teller = ukedag
        else:
            teller = ukedag and sek > 0
        dager.append(Dag(d, sek, teller, dagsmal if teller else 0))

    uker: dict[tuple[int, int], Uke] = {}
    for dag in dager:
        aar, nr, _ = dag.dato.isocalendar()
        u = uker.get((aar, nr))
        if u is None:
            u = Uke(aar, nr, dag.dato, dag.dato)
            uker[(aar, nr)] = u
        u.sek += dag.sek
        u.mal += dag.mal
        u.dager += 1 if dag.teller else 0
        u.fra = min(u.fra, dag.dato)
        u.til = max(u.til, dag.dato)

    return Regnskap(dagsmal, regel, dager, [uker[k] for k in sorted(uker)], navn)


# --------------------------------------------------------------------------
# Utdata
# --------------------------------------------------------------------------

def som_tekst(r: Regnskap) -> str:
    ut = [f"Timeregnskap {r.periode}", f"Mål per dag: {desimal(r.dagsmal)} timer", ""]
    for d in r.dager:
        avvik = f"  ({signert(d.diff)})" if d.teller else "  (teller ikke)"
        ut.append(f"{kort(d.dato)} {d.ukedag}  {hm(d.sek):>10}{avvik}")
    ut.append("")
    for u in r.uker:
        ut.append(f"{u.navn}: {hm(u.sek)} av {hm(u.mal)}  ({signert(u.diff)})")
    ut += [
        "",
        f"Totalt jobbet: {hm(r.sum_sek)} ({desimal(r.sum_sek)} timer)",
        f"Mål totalt:    {hm(r.sum_mal)} på {r.antall_dager} dager",
        f"Avvik:         {signert(r.diff)}",
        f"Snitt per dag: {hm(r.snitt_dag)}",
        f"Snitt per uke: {hm(r.snitt_uke)} (mål {hm(r.mal_uke)}, avvik {signert(r.snitt_uke - r.mal_uke)})",
    ]
    return "\n".join(ut)


def som_csv(r: Regnskap) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    w.writerow(["Dato", "Ukedag", "Uke", "Timer", "Minutter", "Desimaltimer", "Mal", "Avvik"])
    for d in r.dager:
        t, rest = divmod(d.sek, 3600)
        w.writerow([d.dato.isoformat(), d.ukedag, f"Uke {d.dato.isocalendar()[1]}",
                    t, round(rest / 60), desimal(d.sek),
                    desimal(d.mal) if d.teller else "", desimal(d.diff) if d.teller else ""])
    w.writerow([])
    for u in r.uker:
        w.writerow([u.navn, f"{u.fra.isoformat()}–{u.til.isoformat()}", u.dager, "", "",
                    desimal(u.sek), desimal(u.mal), desimal(u.diff)])
    w.writerow([])
    t, rest = divmod(r.sum_sek, 3600)
    w.writerow(["Totalt", "", r.antall_dager, t, round(rest / 60),
                desimal(r.sum_sek), desimal(r.sum_mal), desimal(r.diff)])
    return buf.getvalue()


CSS = """
:root{--paper:#F2F4F3;--surface:#FFF;--ink:#16292E;--muted:#63797E;--line:#D5DDDB;
--plus:#1C6B58;--minus:#9E3B2E;--focus:#2B6C8F;
--sans:'Archivo',system-ui,-apple-system,'Segoe UI',sans-serif;
--serif:'Newsreader',Georgia,'Times New Roman',serif}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--sans);
font-size:16px;line-height:1.45;font-variant-numeric:tabular-nums;-webkit-text-size-adjust:100%}
.wrap{max-width:44rem;margin:0 auto;padding:20px 16px 72px}
a{color:var(--focus)}
:focus-visible{outline:2px solid var(--focus);outline-offset:2px;border-radius:4px}
.masthead{display:flex;align-items:baseline;justify-content:space-between;gap:12px;
border-bottom:1px solid var(--line);padding-bottom:10px}
.masthead h1{font-family:var(--serif);font-weight:500;font-size:1.35rem;margin:0}
.periode{color:var(--muted);font-size:.82rem}
.balanse{padding:26px 0 18px;border-bottom:1px solid var(--line)}
.balanse .tall{font-family:var(--serif);font-size:clamp(2.9rem,14vw,4.4rem);line-height:1;
display:flex;align-items:baseline;gap:.12em;letter-spacing:-.02em}
.balanse .tegn{font-size:.62em;opacity:.8}
.balanse .enhet{font-family:var(--sans);font-size:.26em;color:var(--muted);font-weight:500;padding-left:.35em}
.balanse .undertekst{color:var(--muted);font-size:.85rem;margin-top:12px}
.balanse.pos .tall{color:var(--plus)}
.balanse.neg .tall{color:var(--minus)}
.skala{margin-top:18px;height:36px;position:relative}
.skala .akse{position:absolute;top:11px;left:0;right:0;height:1px;background:var(--line)}
.skala .null{position:absolute;top:1px;height:21px;width:1px;background:var(--ink);opacity:.6}
.skala .stolpe{position:absolute;top:6px;height:11px;border-radius:2px}
.skala .tick{position:absolute;top:3px;height:17px;width:2px;background:var(--ink);opacity:.32}
.skala .merke{position:absolute;top:22px;font-size:.68rem;color:var(--muted);
transform:translateX(-50%);white-space:nowrap}
section{margin-top:26px}
h2{font-family:var(--serif);font-weight:500;font-size:1.05rem;margin:0 0 10px}
.hint{color:var(--muted);font-size:.8rem;margin:6px 0 0}
table{width:100%;border-collapse:collapse;font-size:.9rem}
th{text-align:left;font-weight:500;color:var(--muted);font-size:.75rem;padding:0 0 6px;
border-bottom:1px solid var(--line)}
td{padding:9px 0;border-bottom:1px solid var(--line);vertical-align:middle}
.num{text-align:right;white-space:nowrap}
tr.total td{font-weight:600;border-bottom:none;border-top:2px solid var(--ink);padding-top:11px}
.pos{color:var(--plus)}.neg{color:var(--minus)}.null0{color:var(--muted)}
.dato{display:block}.ukedag{color:var(--muted);font-size:.75rem}
tr.fri td{color:var(--muted)}
.bar{display:inline-block;width:64px;height:10px;position:relative}
.bar i{position:absolute;top:1px;height:8px;border-radius:2px}
.bar .mid{position:absolute;top:0;bottom:0;left:50%;width:1px;background:var(--line)}
@media(max-width:420px){.bar{display:none}table{font-size:.86rem}}
.panel{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:14px}
.felt{display:flex;flex-direction:column;gap:5px;margin-bottom:12px}
label{font-size:.8rem;color:var(--muted)}
input,select{font:inherit;font-size:.92rem;padding:9px 10px;border:1px solid var(--line);
border-radius:8px;background:var(--surface);color:var(--ink);width:100%}
.knapper{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px;align-items:center}
button,.knapp{font:inherit;font-size:.88rem;font-weight:500;padding:10px 14px;border-radius:8px;
border:1px solid var(--ink);background:var(--ink);color:var(--paper);cursor:pointer;
text-decoration:none;display:inline-block}
.sekundar{background:transparent;color:var(--ink);border-color:var(--line)}
.melding{margin-top:12px;font-size:.85rem;padding:10px 12px;border-radius:8px;
background:#FBECE8;color:var(--minus);border:1px solid #EDCEC7}
.melding.ok{background:#E9F2EF;color:var(--plus);border-color:#CBE0D9}
details summary{cursor:pointer;font-size:.85rem;color:var(--muted);padding:4px 0}
details[open] summary{margin-bottom:10px}
footer{margin-top:36px;padding-top:14px;border-top:1px solid var(--line);color:var(--muted);font-size:.78rem}
@media print{body{background:#fff}.ikke-print{display:none!important}.wrap{max-width:none;padding:0}}
"""

_HODE = """<!DOCTYPE html><html lang="no"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Timeregnskap</title><meta name="theme-color" content="#F2F4F3">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600&family=Newsreader:opsz,wght@6..72,400;6..72,500&display=swap" rel="stylesheet">
<style>%s</style></head><body><div class="wrap">"""


def _klasse(sek: float) -> str:
    r = round(sek / 60)
    return "null0" if r == 0 else ("pos" if r > 0 else "neg")


def _skala(r: Regnskap) -> str:
    maks = max([1800, abs(r.diff)] + [abs(u.diff) for u in r.uker])
    halv = 44
    lengde = abs(r.diff) / maks * halv
    venstre = 50 if r.diff >= 0 else 50 - lengde
    farge = "var(--plus)" if r.diff >= 0 else "var(--minus)"
    ende = f"{maks / 3600:.1f}".replace(".", ",") + " t"
    biter = ['<span class="akse"></span>',
             f'<span class="stolpe" style="left:{venstre:.2f}%;width:{max(lengde, 0.8):.2f}%;background:{farge}"></span>']
    for u in r.uker:
        biter.append(f'<span class="tick" style="left:{50 + u.diff / maks * halv:.2f}%"></span>')
    biter += ['<span class="null" style="left:50%"></span>',
              '<span class="merke" style="left:50%">0</span>',
              f'<span class="merke" style="left:{50 - halv}%">−{ende}</span>',
              f'<span class="merke" style="left:{50 + halv}%">+{ende}</span>']
    return '<div class="skala" aria-hidden="true">' + "".join(biter) + "</div>"


def som_html(r: Regnskap, skjema: str = "", melding: str = "", melding_ok: bool = False) -> str:
    tegn = "±" if round(r.diff / 60) == 0 else ("+" if r.diff > 0 else "−")
    kl = "" if round(r.diff / 60) == 0 else (" pos" if r.diff > 0 else " neg")

    ut = [_HODE % CSS]
    ut.append(f'<header class="masthead"><h1>Timeregnskap</h1>'
              f'<span class="periode">{r.periode}</span></header>')
    ut.append(f'<div class="balanse{kl}"><div class="tall"><span class="tegn">{tegn}</span>'
              f'<span>{hm(r.diff)}</span><span class="enhet">mot målet</span></div>')
    ut.append(_skala(r))
    ut.append(f'<p class="undertekst">{hm(r.sum_sek)} jobbet på {r.antall_dager} dager · '
              f'mål {hm(r.sum_mal)} ({desimal(r.dagsmal)} t per dag) · '
              f'snitt {hm(r.snitt_dag)} per dag</p></div>')

    if melding:
        ut.append(f'<div class="melding{" ok" if melding_ok else ""}">{html.escape(melding)}</div>')
    if skjema:
        ut.append(skjema)

    # Uker
    ut.append('<section><h2>Per uke</h2><table><thead><tr><th>Uke</th>'
              '<th class="num">Dager</th><th class="num">Jobbet</th>'
              '<th class="num">Mål</th><th class="num">Avvik</th></tr></thead><tbody>')
    for u in r.uker:
        ut.append(f'<tr><td>{u.navn} <span class="ukedag">{kort(u.fra)}–{kort(u.til)}</span></td>'
                  f'<td class="num">{u.dager}</td><td class="num">{hm(u.sek)}</td>'
                  f'<td class="num">{hm(u.mal)}</td>'
                  f'<td class="num {_klasse(u.diff)}">{signert(u.diff)}</td></tr>')
    ut.append(f'<tr class="total"><td>Totalt</td><td class="num">{r.antall_dager}</td>'
              f'<td class="num">{hm(r.sum_sek)}</td><td class="num">{hm(r.sum_mal)}</td>'
              f'<td class="num {_klasse(r.diff)}">{signert(r.diff)}</td></tr></tbody></table>')
    uke_diff = r.snitt_uke - r.mal_uke
    if round(uke_diff / 60) == 0:
        slutt = "akkurat på snittet."
    else:
        slutt = f"{hm(uke_diff)} {'over' if uke_diff > 0 else 'under'} snittet per uke."
    ut.append(f'<p class="hint">Snitt per uke: {hm(r.snitt_uke)} mot et ukesmål på '
              f'{hm(r.mal_uke)} — {slutt}</p></section>')

    # Dager
    maks = max([7200] + [abs(d.diff) for d in r.dager])
    ut.append('<section><h2>Per dag</h2><table><thead><tr><th>Dato</th>'
              '<th class="num">Jobbet</th><th></th><th class="num">Avvik</th></tr></thead><tbody>')
    for d in r.dager:
        andel = min(1.0, abs(d.diff) / maks) * 50
        if round(d.diff / 60) == 0 or not d.teller:
            stolpe = ""
        elif d.diff > 0:
            stolpe = f'<i style="left:50%;width:{andel:.1f}%;background:var(--plus)"></i>'
        else:
            stolpe = f'<i style="right:50%;width:{andel:.1f}%;background:var(--minus)"></i>'
        rad = ' class="fri"' if not d.teller and d.sek == 0 else ""
        merk = "" if d.teller else " · teller ikke"
        ut.append(f'<tr{rad}><td><span class="dato">{kort(d.dato)}</span>'
                  f'<span class="ukedag">{d.ukedag}{merk}</span></td>'
                  f'<td class="num">{hm(d.sek)}</td>'
                  f'<td><span class="bar"><span class="mid"></span>{stolpe}</span></td>'
                  f'<td class="num {_klasse(d.diff) if d.teller else "null0"}">'
                  f'{signert(d.diff) if d.teller else "–"}</td></tr>')
    ut.append(f'<tr class="total"><td>Totalt ({desimal(r.sum_sek)} timer)</td>'
              f'<td class="num">{hm(r.sum_sek)}</td><td></td>'
              f'<td class="num {_klasse(r.diff)}">{signert(r.diff)}</td></tr></tbody></table></section>')

    ut.append('<footer>Regnet ut med Python. Grunnlaget er CSV-filen du lastet opp.</footer>')
    ut.append("</div></body></html>")
    return "".join(ut)


# --------------------------------------------------------------------------
# Kommandolinje
# --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Regn ut timeregnskap fra en CSV-fil.")
    p.add_argument("fil", help="CSV-fil, eller - for standard inn")
    p.add_argument("--mal", default="7,5", help="mål per dag, f.eks. 7,5 eller 7:30 (standard 7,5)")
    p.add_argument("--regel", default="ukedag-med-tid", choices=list(REGLER),
                   help="hvilke dager som teller mot målet")
    p.add_argument("--navn", default="", help="ta bare med rader med dette navnet")
    p.add_argument("--html", metavar="FIL", help="skriv rapporten som HTML")
    p.add_argument("--csv", metavar="FIL", help="skriv regnskapet som CSV")
    a = p.parse_args(argv)

    tekst = sys.stdin.read() if a.fil == "-" else open(a.fil, encoding="utf-8-sig").read()
    try:
        poster, hoppet = les_csv(tekst)
        r = beregn(poster, les_mal(a.mal), a.regel, a.navn)
    except CsvFeil as e:
        print(f"Feil: {e}", file=sys.stderr)
        return 1

    if hoppet:
        print(f"Hoppet over {len(hoppet)} rad(er) uten gyldig dato: "
              f"{', '.join(map(str, hoppet[:10]))}", file=sys.stderr)
    if a.html:
        open(a.html, "w", encoding="utf-8").write(som_html(r))
        print(f"Skrev {a.html}", file=sys.stderr)
    if a.csv:
        open(a.csv, "w", encoding="utf-8-sig", newline="").write(som_csv(r))
        print(f"Skrev {a.csv}", file=sys.stderr)
    if not a.html and not a.csv:
        print(som_tekst(r))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
