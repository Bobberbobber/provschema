"""
Bygger provschemat.

Hämtar SchoolSoft-kalendern (länken ligger i hemligheten SCHOOLSOFT_URL),
plockar ut prov, uppgifter, läxor och seminarier, lägger till det som står
i extra_prov.csv och skriver en färdig webbsida till site/index.html.
"""

import csv
import html
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from icalendar import Calendar

TZ = ZoneInfo("Europe/Stockholm")
KLASS = "LK24"

# Kurskoder i SchoolSoft -> namn som visas på sidan
KURSER = {
    "Ret": "Retorik",
    "Fi1": "Filosofi 1",
    "Hi1b": "Historia 1b",
    "En7": "Engelska 7",
    "Sv3": "Svenska 3",
    "Soc": "Sociologi",
    "Nk2": "Naturkunskap 2",
    "Hum.sam.-led": "Hum/sam-specialisering",
}

# Händelsetyper -> (etikett, färgklass). Ordningen spelar roll: längst först.
TYPER = [
    ("Skrivuppgift på lektionstid", "Skrivuppgift", "skriv"),
    ("Prov", "Prov", "prov"),
    ("Läxa", "Läxa", "laxa"),
    ("Inlämning", "Inlämning", "inl"),
    ("Lektion", "Seminarium", "sem"),
]

VECKODAGAR = ["mån", "tis", "ons", "tor", "fre", "lör", "sön"]
MANADER = ["jan", "feb", "mar", "apr", "maj", "jun",
           "jul", "aug", "sep", "okt", "nov", "dec"]


def till_lokal(dt):
    """Gör om ett datum/tid från kalendern till svensk tid."""
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            return dt.replace(tzinfo=TZ)
        return dt.astimezone(TZ)
    return datetime(dt.year, dt.month, dt.day, tzinfo=TZ)


def dela_typ(titel):
    """'Prov Källkritik - prov' -> ('Prov', 'prov', 'Källkritik - prov')."""
    for prefix, etikett, klass in TYPER:
        if titel.startswith(prefix + " "):
            return etikett, klass, titel[len(prefix):].strip()
    return "Övrigt", "ovr", titel


def hamta_schoolsoft(url):
    cal = Calendar.from_ical(requests.get(url, timeout=30).content)

    lektioner, uppgifter = [], []
    for e in cal.walk("VEVENT"):
        titel = str(e.get("SUMMARY", "")).strip()
        delar = titel.split()
        if not delar:
            continue
        start = till_lokal(e.get("DTSTART").dt)
        slut = till_lokal(e.get("DTEND").dt) if e.get("DTEND") else start

        # Vanlig lektion = bara "Lektion <kurskod>"
        if delar[0] == "Lektion" and len(delar) <= 2:
            if len(delar) == 2:
                lektioner.append((start, slut, delar[1]))
            continue

        uppgifter.append({
            "start": start,
            "titel": titel,
            "beskrivning": str(e.get("DESCRIPTION", "")).strip(),
        })

    def hitta_kurs(start):
        for l_start, l_slut, kod in lektioner:
            if l_start <= start < l_slut:
                return KURSER.get(kod, kod)
        return ""

    resultat = []
    for u in uppgifter:
        etikett, klass, namn = dela_typ(u["titel"])
        resultat.append({
            "datum": u["start"].date(),
            "tid": u["start"].strftime("%H:%M") if u["start"].hour or u["start"].minute else "",
            "kurs": hitta_kurs(u["start"]),
            "typ": etikett,
            "klass": klass,
            "titel": namn,
            "info": u["beskrivning"],
            "kalla": "SchoolSoft",
        })
    return resultat


def hamta_extra(fil):
    """Läser extra_prov.csv (datum,kurs,typ,titel,info)."""
    resultat = []
    if not Path(fil).exists():
        return resultat
    with open(fil, encoding="utf-8") as f:
        for rad in csv.DictReader(f):
            try:
                datum = date.fromisoformat(rad["datum"].strip())
            except (KeyError, ValueError):
                continue
            typ = (rad.get("typ") or "Prov").strip()
            klass = {"prov": "prov", "skrivuppgift": "skriv", "läxa": "laxa",
                     "inlämning": "inl", "seminarium": "sem"}.get(typ.lower(), "ovr")
            resultat.append({
                "datum": datum,
                "tid": "",
                "kurs": (rad.get("kurs") or "").strip(),
                "typ": typ,
                "klass": klass,
                "titel": (rad.get("titel") or "").strip(),
                "info": (rad.get("info") or "").strip(),
                "kalla": "Teams",
            })
    return resultat


def ta_bort_dubbletter(lista):
    sett, unika = set(), []
    for u in lista:
        nyckel = (u["datum"], u["kurs"].lower(), u["titel"].lower())
        if nyckel not in sett:
            sett.add(nyckel)
            unika.append(u)
    return unika


def nedrakning(dagar):
    if dagar == 0:
        return "idag"
    if dagar == 1:
        return "imorgon"
    return f"om {dagar} dagar"


# Bobber, en egen pixelkatt som sover, vaknar, går runt och kan klappas.
KATT_CSS = '  .kattbana { position: relative; height: 110px; margin: 8px 0 -24px; }\n  .katt { position: absolute; bottom: 0; left: 0; width: 64px; padding: 0; border: 0; background: none;\n    cursor: pointer; display: flex; flex-direction: column; align-items: center; }\n  .katt:focus-visible { outline: 3px solid var(--black); outline-offset: 4px; border-radius: 8px; }\n  .namn { font: 700 13px/1 "Atkinson Hyperlegible", sans-serif; color: #fff; background: #7b68c9;\n    border: 2px solid #4b3c93; border-radius: 4px; padding: 3px 6px; margin-bottom: 6px; white-space: nowrap; }\n  .kattsvg { display: block; width: 60px; height: 56px; }\n  .kattsvg .sovande, .kattsvg .ben-a, .kattsvg .ben-b { display: none; }\n  .katt.sover .kattsvg .vaken { display: none; }\n  .katt.sover .kattsvg .sovande { display: inline; }\n  .katt.gar .kattsvg .ben-sta { display: none; }\n  .katt.gar .kattsvg .ben-a { display: inline; animation: kattben .4s steps(1) infinite; }\n  .katt.gar .kattsvg .ben-b { display: inline; animation: kattben .4s steps(1) infinite reverse; }\n  .katt.gar .kattsvg { animation: kattstuds .4s steps(2) infinite; }\n  @keyframes kattben { 0% { visibility: visible; } 50% { visibility: hidden; } }\n  @keyframes kattstuds { 0% { translate: 0 0; } 100% { translate: 0 -2px; } }\n  .zzz { position: absolute; right: -14px; bottom: 30px; width: 24px; height: 30px; display: none; pointer-events: none; }\n  .katt.sover .zzz { display: block; }\n  .zzz i { position: absolute; left: 0; bottom: 0; font: 800 13px/1 "Bricolage Grotesque", sans-serif; font-style: normal;\n    color: var(--text); opacity: 0; animation: zflyg 2.4s ease-out infinite; }\n  .zzz i:nth-child(2) { animation-delay: .8s; }\n  .zzz i:nth-child(3) { animation-delay: 1.6s; }\n  @keyframes zflyg { 0% { opacity: 0; transform: translate(0, 0); } 25% { opacity: 1; } 100% { opacity: 0; transform: translate(8px, -22px); } }\n  .pop { position: absolute; bottom: 70px; width: 14px; height: 14px; pointer-events: none; opacity: 0;\n    animation: popp 1.3s ease-out forwards; image-rendering: pixelated; background-size: 100% 100%; }\n  .pop.hjarta { background-image: url("data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' viewBox=\'0 0 7 6\' shape-rendering=\'crispEdges\'%3E%3Cpath fill=\'%23f49cc4\' d=\'M1 0h2v1h1V0h2v1h1v2H6v1H5v1H4v1H3V5H2V4H1V3H0V1h1z\'/%3E%3C/svg%3E"); }\n  .pop.mynt { background-image: url("data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' viewBox=\'0 0 6 6\' shape-rendering=\'crispEdges\'%3E%3Cpath fill=\'%23c98d12\' d=\'M1 0h4v1h1v4H5v1H1V5H0V1h1z\'/%3E%3Cpath fill=\'%23f7c531\' d=\'M1 1h4v4H1z\'/%3E%3Cpath fill=\'%23fff3b0\' d=\'M2 1h1v1H2z\'/%3E%3C/svg%3E"); }\n  @keyframes popp { 0% { opacity: 0; transform: translateY(0) scale(.6); } 20% { opacity: 1; transform: translateY(-8px) scale(1); }\n    100% { opacity: 0; transform: translateY(-38px) scale(1); } }\n  @media (prefers-reduced-motion: reduce) {\n    .zzz i { animation: none; opacity: 1; }\n    .zzz i:nth-child(2) { transform: translate(5px, -9px); } .zzz i:nth-child(3) { transform: translate(10px, -18px); }\n    .katt.gar .kattsvg, .katt.gar .kattsvg .ben-a, .katt.gar .kattsvg .ben-b { animation: none; }\n  }\n'
KATT_HTML = '  <div class="kattbana">\n    <button class="katt sover" type="button" aria-label="Klappa Bobber">\n      <span class="namn">Bobber</span>\n      <span class="zzz" aria-hidden="true"><i>z</i><i>z</i><i>z</i></span>\n      <svg class="kattsvg" viewBox="0 -1 15 14" shape-rendering="crispEdges" xmlns="http://www.w3.org/2000/svg"><rect x="1" y="1" width="1" height="1" fill="#4b3c93"/><rect x="13" y="1" width="1" height="1" fill="#4b3c93"/><rect x="0" y="2" width="1" height="1" fill="#4b3c93"/><rect x="1" y="2" width="1" height="1" fill="#b9a8f5"/><rect x="2" y="2" width="1" height="1" fill="#4b3c93"/><rect x="12" y="2" width="1" height="1" fill="#4b3c93"/><rect x="13" y="2" width="1" height="1" fill="#b9a8f5"/><rect x="14" y="2" width="1" height="1" fill="#4b3c93"/><rect x="0" y="3" width="1" height="1" fill="#4b3c93"/><rect x="1" y="3" width="2" height="1" fill="#b9a8f5"/><rect x="3" y="3" width="9" height="1" fill="#4b3c93"/><rect x="12" y="3" width="2" height="1" fill="#b9a8f5"/><rect x="14" y="3" width="1" height="1" fill="#4b3c93"/><rect x="0" y="4" width="1" height="1" fill="#4b3c93"/><rect x="1" y="4" width="13" height="1" fill="#b9a8f5"/><rect x="14" y="4" width="1" height="1" fill="#4b3c93"/><rect x="0" y="5" width="1" height="1" fill="#4b3c93"/><rect x="1" y="5" width="13" height="1" fill="#b9a8f5"/><rect x="14" y="5" width="1" height="1" fill="#4b3c93"/><rect x="0" y="6" width="1" height="1" fill="#4b3c93"/><rect x="1" y="6" width="13" height="1" fill="#b9a8f5"/><rect x="14" y="6" width="1" height="1" fill="#4b3c93"/><rect x="0" y="7" width="1" height="1" fill="#4b3c93"/><rect x="1" y="7" width="1" height="1" fill="#b9a8f5"/><rect x="2" y="7" width="1" height="1" fill="#f49cc4"/><rect x="3" y="7" width="4" height="1" fill="#b9a8f5"/><rect x="7" y="7" width="1" height="1" fill="#2c2160"/><rect x="8" y="7" width="4" height="1" fill="#b9a8f5"/><rect x="12" y="7" width="1" height="1" fill="#f49cc4"/><rect x="13" y="7" width="1" height="1" fill="#b9a8f5"/><rect x="14" y="7" width="1" height="1" fill="#4b3c93"/><rect x="1" y="8" width="1" height="1" fill="#4b3c93"/><rect x="2" y="8" width="11" height="1" fill="#b9a8f5"/><rect x="13" y="8" width="1" height="1" fill="#4b3c93"/><rect x="2" y="9" width="1" height="1" fill="#4b3c93"/><rect x="3" y="9" width="9" height="1" fill="#b9a8f5"/><rect x="12" y="9" width="1" height="1" fill="#4b3c93"/><rect x="2" y="10" width="1" height="1" fill="#4b3c93"/><rect x="3" y="10" width="9" height="1" fill="#b9a8f5"/><rect x="12" y="10" width="1" height="1" fill="#4b3c93"/><g class="vaken"><rect x="5" y="0" width="1" height="1" fill="#f7c531"/><rect x="7" y="0" width="1" height="1" fill="#f7c531"/><rect x="9" y="0" width="1" height="1" fill="#f7c531"/><rect x="5" y="1" width="5" height="1" fill="#f7c531"/><rect x="5" y="2" width="5" height="1" fill="#f7c531"/><rect x="3" y="5" width="1" height="1" fill="#2c2160"/><rect x="11" y="5" width="1" height="1" fill="#2c2160"/><rect x="3" y="6" width="1" height="1" fill="#2c2160"/><rect x="11" y="6" width="1" height="1" fill="#2c2160"/></g><g class="sovande"><rect x="11" y="-1" width="1" height="1" fill="#ffffff"/><rect x="8" y="0" width="3" height="1" fill="#3b3f8f"/><rect x="5" y="1" width="5" height="1" fill="#3b3f8f"/><rect x="4" y="2" width="7" height="1" fill="#3b3f8f"/><rect x="2" y="6" width="2" height="1" fill="#2c2160"/><rect x="11" y="6" width="2" height="1" fill="#2c2160"/></g><g class="ben-sta"><rect x="3" y="11" width="1" height="1" fill="#4b3c93"/><rect x="4" y="11" width="1" height="1" fill="#b9a8f5"/><rect x="9" y="11" width="1" height="1" fill="#4b3c93"/><rect x="10" y="11" width="1" height="1" fill="#b9a8f5"/><rect x="3" y="12" width="2" height="1" fill="#4b3c93"/><rect x="9" y="12" width="2" height="1" fill="#4b3c93"/></g><g class="ben-a"><rect x="3" y="11" width="1" height="1" fill="#4b3c93"/><rect x="4" y="11" width="1" height="1" fill="#b9a8f5"/><rect x="10" y="11" width="1" height="1" fill="#4b3c93"/><rect x="11" y="11" width="1" height="1" fill="#b9a8f5"/><rect x="3" y="12" width="2" height="1" fill="#4b3c93"/><rect x="10" y="12" width="2" height="1" fill="#4b3c93"/></g><g class="ben-b"><rect x="4" y="11" width="1" height="1" fill="#4b3c93"/><rect x="5" y="11" width="1" height="1" fill="#b9a8f5"/><rect x="9" y="11" width="1" height="1" fill="#4b3c93"/><rect x="10" y="11" width="1" height="1" fill="#b9a8f5"/><rect x="4" y="12" width="2" height="1" fill="#4b3c93"/><rect x="9" y="12" width="2" height="1" fill="#4b3c93"/></g></svg>\n    </button>\n  </div>\n  <script>\n  (function () {\n    var katt = document.querySelector(".katt");\n    var bana = document.querySelector(".kattbana");\n    if (!katt || !bana) return;\n    var lugn = window.matchMedia("(prefers-reduced-motion: reduce)").matches;\n    var x = 12, timer = null;\n    function satt(nytt) { x = nytt; katt.style.transform = "translateX(" + x + "px)"; }\n    function vila(ms, sen) { clearTimeout(timer); timer = setTimeout(sen, ms); }\n    function somna() { katt.classList.remove("gar"); katt.classList.add("sover"); vila(9000 + Math.random() * 9000, vakna); }\n    function vakna() { katt.classList.remove("sover"); vila(1200, ga); }\n    function ga() {\n      if (lugn) { vila(4000, somna); return; }\n      var max = Math.max(0, bana.clientWidth - katt.offsetWidth - 12);\n      var mal = Math.round(12 + Math.random() * (max - 12));\n      var tid = Math.max(800, Math.abs(mal - x) / 55 * 1000);\n      katt.style.transition = "transform " + tid + "ms linear";\n      katt.classList.add("gar");\n      satt(mal);\n      vila(tid, function () { katt.classList.remove("gar"); vila(2500 + Math.random() * 3000, somna); });\n    }\n    function poppa(typ, dx, fordrojning) {\n      var e = document.createElement("span");\n      e.className = "pop " + typ;\n      e.style.left = (x + katt.offsetWidth / 2 + dx) + "px";\n      e.style.animationDelay = fordrojning + "ms";\n      bana.appendChild(e);\n      setTimeout(function () { e.remove(); }, 1600 + fordrojning);\n    }\n    katt.addEventListener("click", function () {\n      poppa("hjarta", -6, 0);\n      poppa("mynt", -26, 120);\n      poppa("mynt", 16, 220);\n      if (katt.classList.contains("sover")) vakna();\n    });\n    satt(12);\n    vila(4000 + Math.random() * 4000, vakna);\n  })();\n  </script>\n'


def bygg_sida(uppgifter, idag):
    e = html.escape
    kommande = sorted(
        (u for u in uppgifter if u["datum"] >= idag),
        key=lambda u: (u["datum"], u["tid"]),
    )

    # Gruppera per vecka
    veckor = {}
    for u in kommande:
        ar, vecka, _ = u["datum"].isocalendar()
        veckor.setdefault((ar, vecka), []).append(u)

    denna_vecka = idag.isocalendar()[:2]
    block = []
    for (ar, vecka), lista in veckor.items():
        mandag = date.fromisocalendar(ar, vecka, 1)
        fredag = mandag + timedelta(days=4)
        bedomningar = sum(1 for u in lista if u["klass"] in ("prov", "skriv"))

        if (ar, vecka) == denna_vecka:
            nar = "Den här veckan"
        elif (mandag - idag).days <= 7:
            nar = "Nästa vecka"
        else:
            nar = f"{mandag.day} {MANADER[mandag.month - 1]} till {fredag.day} {MANADER[fredag.month - 1]}"

        tung = ""
        if bedomningar >= 3:
            tung = f'<p class="tung">Tung vecka: {bedomningar} prov och skrivuppgifter</p>'
        elif bedomningar == 2:
            tung = '<p class="tung lagom">Två prov eller skrivuppgifter</p>'

        rader = []
        for u in lista:
            dagar = (u["datum"] - idag).days
            snart = " snart" if dagar <= 3 else ""
            kurs = f'<span class="kurs">{e(u["kurs"])}</span>' if u["kurs"] else ""
            tid = f'<span class="tid">kl. {e(u["tid"])}</span>' if u["tid"] else ""
            info = f'<p class="info">{e(u["info"])}</p>' if u["info"] else ""
            rader.append(f"""
        <li class="rad {u['klass']}{snart}">
          <div class="dag">
            <span class="vd">{VECKODAGAR[u['datum'].weekday()]}</span>
            <span class="nr">{u['datum'].day}</span>
          </div>
          <div class="text">
            <p class="meta"><mark class="typ">{e(u['typ'])}</mark>{kurs}{tid}</p>
            <h3>{e(u['titel'])}</h3>
            {info}
          </div>
          <span class="kvar">{nedrakning(dagar)}</span>
        </li>""")

        block.append(f"""
    <section class="vecka{' nu' if (ar, vecka) == denna_vecka else ''}" aria-label="Vecka {vecka}">
      <div class="vnr"><span class="v">v</span>{vecka}</div>
      <div class="vinnehall">
        <p class="nar">{nar}</p>{tung}
        <ul>{''.join(rader)}
        </ul>
      </div>
    </section>""")

    if not block:
        block.append('<p class="tomt">Inga prov eller uppgifter inlagda framöver. Skönt!</p>')

    hero = ""
    if kommande:
        n = kommande[0]
        dagar = (n["datum"] - idag).days
        if dagar == 0:
            stor, liten = "Idag", ""
        elif dagar == 1:
            stor, liten = "Imorgon", ""
        else:
            stor, liten = str(dagar), "dagar kvar"
        kurs = e(n["kurs"]) + ": " if n["kurs"] else ""
        hero = f"""
  <section class="hero {n['klass']}">
    <p class="hlabel">Nästa {e(n['typ'].lower())}</p>
    <div class="hrad">
      <span class="hstor">{stor}</span><span class="hliten">{liten}</span>
    </div>
    <p class="htitel">{kurs}{e(n['titel'])}</p>
  </section>"""

    antal = sum(1 for u in kommande if u["klass"] in ("prov", "skriv"))

    # Avklarade: allt som har passerat under det här läsåret, nyast först
    lasarsstart = date(idag.year if idag.month >= 8 else idag.year - 1, 8, 1)
    avklarade = sorted(
        (u for u in uppgifter if lasarsstart <= u["datum"] < idag),
        key=lambda u: (u["datum"], u["tid"]),
        reverse=True,
    )
    klara = ""
    if avklarade:
        klara_rader = []
        for u in avklarade:
            datumtext = f'{VECKODAGAR[u["datum"].weekday()]} {u["datum"].day} {MANADER[u["datum"].month - 1]}'
            kurs = f'<span class="kurs">{e(u["kurs"])}</span>' if u["kurs"] else ""
            klara_rader.append(f"""
        <li class="klar {u['klass']}">
          <span class="kdatum">{datumtext}</span>
          <p class="meta"><mark class="typ">{e(u['typ'])}</mark>{kurs}</p>
          <s class="ktitel">{e(u['titel'])}</s>
        </li>""")
        klara = f"""
  <details class="klara">
    <summary>Avklarade prov <span class="antal">{len(avklarade)}</span></summary>
    <ul>{''.join(klara_rader)}
    </ul>
  </details>"""
    uppdaterad = datetime.now(TZ).strftime("%-d/%-m kl. %H:%M")

    return f"""<!doctype html>
<html lang="sv">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#1c2f8f">
<title>Provschema {KLASS}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,400;12..96,700;12..96,800&family=Atkinson+Hyperlegible:wght@400;700&display=swap" rel="stylesheet">
<style>
  :root {{
    --papper: #f5f7fc;
    --rutor: #dfe5f3;
    --black: #1c2f8f;
    --text: #18203f;
    --dim: #5b6488;
    --rad: #ffffff;
    --prov: #ffe14a;
    --skriv: #ff9fcf;
    --inl: #8ee6c6;
    --laxa: #a7c6ff;
    --sem: #ffbe73;
    --ovr: #d9dce6;
    --varning: #e0294a;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --papper: #0f1533; --rutor: #1a2350; --black: #9fb2ff; --text: #eef1ff;
      --dim: #9aa3c9; --rad: #161e45; --ovr: #c9cde0; --varning: #ff5c79;
    }}
  }}
  * {{ box-sizing: border-box; }}
  html {{ -webkit-text-size-adjust: 100%; }}
  body {{
    margin: 0; color: var(--text); background-color: var(--papper);
    background-image:
      linear-gradient(var(--rutor) 1px, transparent 1px),
      linear-gradient(90deg, var(--rutor) 1px, transparent 1px);
    background-size: 24px 24px;
    font: 17px/1.5 "Atkinson Hyperlegible", system-ui, sans-serif;
  }}
  main {{ max-width: 760px; margin: 0 auto; padding: 28px 16px 64px; }}

  header {{ display: flex; justify-content: space-between; align-items: baseline; gap: 12px; flex-wrap: wrap; }}
  h1 {{ font: 800 1.35rem/1 "Bricolage Grotesque", sans-serif; margin: 0; color: var(--black); }}
  header p {{ margin: 0; color: var(--dim); font-size: .9rem; }}

  .hero {{ margin: 22px 0 36px; padding: 22px 22px 24px; background: var(--black); color: #fff; border-radius: 20px;
    position: relative; overflow: hidden; }}
  @media (prefers-color-scheme: dark) {{ .hero {{ background: #22307a; }} }}
  .hlabel {{ margin: 0; font-size: .95rem; opacity: .8; }}
  .hrad {{ display: flex; align-items: baseline; gap: 10px; }}
  .hstor {{ font: 800 clamp(4.5rem, 20vw, 7.5rem)/.95 "Bricolage Grotesque", sans-serif; letter-spacing: -.04em; }}
  .hliten {{ font: 700 1.2rem/1 "Bricolage Grotesque", sans-serif; }}
  .htitel {{ margin: 10px 0 0; font-size: 1.15rem; font-weight: 700; max-width: 34ch; }}
  .hero::after {{ content: ""; position: absolute; right: -40px; top: -40px; width: 180px; height: 180px; border-radius: 50%;
    background: var(--prov); opacity: .95; }}
  .hero.skriv::after {{ background: var(--skriv); }} .hero.inl::after {{ background: var(--inl); }}
  .hero.laxa::after {{ background: var(--laxa); }} .hero.sem::after {{ background: var(--sem); }}
  .hero > * {{ position: relative; z-index: 1; }}

  .vecka {{ display: grid; grid-template-columns: 92px 1fr; gap: 8px; margin-bottom: 30px; }}
  .vnr {{ font: 800 3.4rem/.9 "Bricolage Grotesque", sans-serif; color: var(--black); letter-spacing: -.05em;
    align-self: start; }}
  .vnr .v {{ font-size: .45em; font-weight: 700; letter-spacing: 0; margin-right: 2px; }}
  .nar {{ margin: 6px 0 8px; font-weight: 700; color: var(--dim); }}
  .vecka.nu .nar {{ color: var(--black); }}
  .tung {{ margin: -4px 0 10px; font-weight: 700; color: var(--varning); }}
  .tung.lagom {{ color: var(--dim); font-weight: 400; }}

  ul {{ list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; }}
  .rad {{ display: grid; grid-template-columns: 52px 1fr auto; gap: 14px; align-items: start;
    background: var(--rad); border-radius: 16px; padding: 14px 16px; box-shadow: 0 1px 0 var(--rutor), 0 0 0 1px var(--rutor); }}
  .dag {{ text-align: center; line-height: 1; padding-top: 2px; }}
  .vd {{ display: block; font-size: .8rem; color: var(--dim); }}
  .nr {{ display: block; font: 800 1.8rem/1.05 "Bricolage Grotesque", sans-serif; color: var(--black); }}
  .meta {{ margin: 0 0 2px; display: flex; flex-wrap: wrap; gap: 4px 10px; align-items: center; font-size: .88rem; color: var(--dim); }}
  mark.typ {{ background: var(--ovr); color: #18203f; font-weight: 700; padding: 1px 8px 2px; border-radius: 6px;
    display: inline-block; }}
  .prov mark.typ {{ background: var(--prov); }} .skriv mark.typ {{ background: var(--skriv); }}
  .inl mark.typ {{ background: var(--inl); }} .laxa mark.typ {{ background: var(--laxa); }}
  .sem mark.typ {{ background: var(--sem); }}
  .kurs {{ font-weight: 700; color: var(--text); }}
  h3 {{ margin: 0; font-size: 1.05rem; line-height: 1.3; }}
  .info {{ margin: 4px 0 0; color: var(--dim); font-size: .92rem; }}
  .kvar {{ font-size: .85rem; color: var(--dim); white-space: nowrap; padding-top: 2px; }}
  .rad.snart {{ box-shadow: 0 0 0 2px var(--varning); }}
  .rad.snart .kvar {{ color: var(--varning); font-weight: 700; }}

  .tomt {{ font-size: 1.1rem; margin-top: 40px; }}

{KATT_CSS}
  .klara {{ margin-top: 40px; border-top: 2px solid var(--rutor); padding-top: 18px; }}
  .klara summary {{ cursor: pointer; font: 700 1.25rem/1.2 "Bricolage Grotesque", sans-serif; color: var(--black);
    list-style: none; display: flex; align-items: center; gap: 10px; padding: 6px 0; }}
  .klara summary::-webkit-details-marker {{ display: none; }}
  .klara summary::before {{ content: ""; width: 9px; height: 9px; border-right: 3px solid currentColor; border-bottom: 3px solid currentColor;
    transform: rotate(-45deg); transition: transform .2s; margin-right: 4px; }}
  .klara[open] summary::before {{ transform: rotate(45deg); }}
  .klara summary:focus-visible {{ outline: 3px solid var(--black); outline-offset: 4px; border-radius: 6px; }}
  .antal {{ font: 700 .85rem/1 "Atkinson Hyperlegible", sans-serif; background: var(--rad); color: var(--dim);
    border-radius: 99px; padding: 4px 10px; box-shadow: 0 0 0 1px var(--rutor); }}
  .klara ul {{ margin-top: 12px; gap: 6px; }}
  .klar {{ display: grid; grid-template-columns: 96px auto 1fr; gap: 12px; align-items: center;
    padding: 10px 14px; border-radius: 12px; background: var(--rad); opacity: .7; }}
  .klar .meta {{ margin: 0; }}
  .kdatum {{ font-size: .88rem; color: var(--dim); }}
  .ktitel {{ color: var(--dim); text-decoration-thickness: 2px; text-decoration-color: var(--text); }}
  @media (prefers-reduced-motion: reduce) {{ .klara summary::before {{ transition: none; }} }}
  footer {{ margin-top: 48px; color: var(--dim); font-size: .85rem; max-width: 60ch; }}

  @media (max-width: 560px) {{
    .vecka {{ grid-template-columns: 1fr; gap: 0; }}
    .vnr {{ font-size: 2.6rem; }}
    .rad {{ grid-template-columns: 44px 1fr; }}
    .kvar {{ grid-column: 2; padding-top: 0; }}
    .klar {{ grid-template-columns: auto 1fr; }}
    .ktitel {{ grid-column: 1 / -1; }}
  }}
</style>
</head>
<body>
<main>
  <header>
    <h1>Provschema {KLASS}</h1>
    <p>{antal} prov och skrivuppgifter kvar</p>
  </header>{hero}
  {''.join(block)}
{KATT_HTML}{klara}
  <footer>Hämtas från SchoolSoft varje morgon. Uppgifter från Teams läggs in för hand. Senast uppdaterad {uppdaterad}. Dubbelkolla alltid med läraren.</footer>
</main>
</body>
</html>
"""

def main():
    url = os.environ.get("SCHOOLSOFT_URL", "").strip()
    if not url:
        raise SystemExit("Hemligheten SCHOOLSOFT_URL saknas.")

    uppgifter = hamta_schoolsoft(url) + hamta_extra("extra_prov.csv")
    uppgifter = ta_bort_dubbletter(uppgifter)

    Path("site").mkdir(exist_ok=True)
    Path("site/index.html").write_text(bygg_sida(uppgifter, datetime.now(TZ).date()), encoding="utf-8")
    print(f"Klart: {len(uppgifter)} uppgifter totalt.")


if __name__ == "__main__":
    main()
