test rad 1
    indenterad
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


def bygg_sida(uppgifter, idag):
    kommande = sorted(
        (u for u in uppgifter if u["datum"] >= idag),
        key=lambda u: (u["datum"], u["tid"]),
    )

    # Gruppera per vecka
    veckor = {}
    for u in kommande:
        ar, vecka, _ = u["datum"].isocalendar()
        veckor.setdefault((ar, vecka), []).append(u)

    e = html.escape
    block = []
    for (ar, vecka), lista in veckor.items():
        mandag = date.fromisocalendar(ar, vecka, 1)
        sondag = mandag + timedelta(days=6)
        bedomningar = sum(1 for u in lista if u["klass"] in ("prov", "skriv"))
        varning = (f'<span class="varning">{bedomningar} prov/skrivuppgifter denna vecka</span>'
                   if bedomningar >= 3 else "")
        denna = ' denna' if (ar, vecka) == idag.isocalendar()[:2] else ""

        kort = []
        for u in lista:
            dagar = (u["datum"] - idag).days
            datumtext = f'{VECKODAGAR[u["datum"].weekday()]} {u["datum"].day} {MANADER[u["datum"].month - 1]}'
            tid = f' · {e(u["tid"])}' if u["tid"] else ""
            info = f'<p class="info">{e(u["info"])}</p>' if u["info"] else ""
            kurs = f'<span class="kurs">{e(u["kurs"])}</span>' if u["kurs"] else ""
            narmast = " snart" if dagar <= 3 else ""
            kort.append(f"""
        <li class="kort {u['klass']}{narmast}">
          <div class="datum"><strong>{datumtext}</strong>{tid}<span class="kvar">{nedrakning(dagar)}</span></div>
          <div class="innehall">
            <div class="rad1"><span class="typ">{e(u['typ'])}</span>{kurs}</div>
            <h3>{e(u['titel'])}</h3>
            {info}
          </div>
        </li>""")

        block.append(f"""
    <section class="vecka{denna}">
      <h2>Vecka {vecka} <span class="span">{mandag.day} {MANADER[mandag.month-1]} – {sondag.day} {MANADER[sondag.month-1]}</span>{varning}</h2>
      <ul>{''.join(kort)}
      </ul>
    </section>""")

    if not block:
        block.append('<p class="tomt">Inga kommande prov eller uppgifter just nu.</p>')

    nasta = kommande[0] if kommande else None
    toppkort = ""
    if nasta:
        dagar = (nasta["datum"] - idag).days
        toppkort = f"""
    <div class="nasta">
      <span class="etikett">Närmast</span>
      <strong>{e(nasta['titel'])}</strong>
      <span>{e(nasta['kurs'] or nasta['typ'])} · {nedrakning(dagar)}</span>
    </div>"""

    uppdaterad = datetime.now(TZ).strftime("%Y-%m-%d %H:%M")

    return f"""<!doctype html>
<html lang="sv">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Provschema {KLASS}</title>
<style>
  :root {{
    --bg: #f6f5f1; --yta: #ffffff; --text: #1d1d1b; --dim: #6b6a65; --linje: #e4e2dc;
    --prov: #d1495b; --skriv: #edae49; --laxa: #00798c; --inl: #6a4c93; --sem: #30638e; --ovr: #8a8a8a;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg: #141413; --yta: #1f1f1d; --text: #f0efe9; --dim: #a09e97; --linje: #2e2e2b; }}
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: var(--bg); color: var(--text);
    font: 16px/1.45 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }}
  main {{ max-width: 720px; margin: 0 auto; padding: 24px 16px 48px; }}
  header h1 {{ font-size: 1.9rem; margin: 0 0 4px; letter-spacing: -0.02em; }}
  header p {{ margin: 0; color: var(--dim); font-size: .9rem; }}
  .nasta {{ margin: 20px 0 8px; padding: 16px 18px; border-radius: 14px; background: var(--text); color: var(--bg);
    display: flex; flex-direction: column; gap: 2px; }}
  .nasta .etikett {{ font-size: .75rem; text-transform: uppercase; letter-spacing: .08em; opacity: .7; }}
  .nasta strong {{ font-size: 1.15rem; }}
  .vecka h2 {{ font-size: 1rem; margin: 28px 0 10px; display: flex; flex-wrap: wrap; gap: 8px; align-items: baseline; }}
  .vecka .span {{ color: var(--dim); font-weight: 400; font-size: .9rem; }}
  .vecka.denna h2::after {{ content: "denna vecka"; font-size: .75rem; font-weight: 600; color: var(--prov); }}
  .varning {{ font-size: .8rem; font-weight: 600; color: #fff; background: var(--prov); padding: 2px 8px; border-radius: 99px; }}
  ul {{ list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }}
  .kort {{ display: grid; grid-template-columns: 110px 1fr; gap: 14px; background: var(--yta);
    border: 1px solid var(--linje); border-left: 5px solid var(--ovr); border-radius: 12px; padding: 12px 14px; }}
  .kort.prov {{ border-left-color: var(--prov); }} .kort.skriv {{ border-left-color: var(--skriv); }}
  .kort.laxa {{ border-left-color: var(--laxa); }} .kort.inl {{ border-left-color: var(--inl); }}
  .kort.sem {{ border-left-color: var(--sem); }}
  .datum {{ display: flex; flex-direction: column; font-size: .9rem; color: var(--dim); }}
  .datum strong {{ color: var(--text); font-size: 1rem; }}
  .kvar {{ margin-top: 4px; font-size: .8rem; }}
  .kort.snart .kvar {{ color: var(--prov); font-weight: 700; }}
  .rad1 {{ display: flex; gap: 8px; flex-wrap: wrap; font-size: .75rem; text-transform: uppercase; letter-spacing: .05em; color: var(--dim); }}
  .kurs {{ font-weight: 600; color: var(--text); }}
  h3 {{ margin: 2px 0 0; font-size: 1.02rem; }}
  .info {{ margin: 4px 0 0; color: var(--dim); font-size: .9rem; }}
  .tomt {{ color: var(--dim); margin-top: 32px; }}
  footer {{ margin-top: 40px; color: var(--dim); font-size: .8rem; }}
  @media (max-width: 480px) {{ .kort {{ grid-template-columns: 1fr; gap: 6px; }} .datum {{ flex-direction: row; gap: 8px; align-items: baseline; }} .kvar {{ margin: 0 0 0 auto; }} }}
</style>
</head>
<body>
<main>
  <header>
    <h1>Provschema {KLASS}</h1>
    <p>Prov, skrivuppgifter, inlämningar och läxor på ett ställe.</p>
  </header>{toppkort}
  {''.join(block)}
  <footer>Uppdaterad {uppdaterad}. Hämtas automatiskt från SchoolSoft varje morgon, plus uppgifter från Teams som läggs in för hand. Dubbelkolla alltid med läraren.</footer>
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
