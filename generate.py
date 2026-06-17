import anthropic
import json
import re
import urllib.parse
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta, date

PERIGON_KEY = "51d90d54-03df-4bec-910e-ac40924fb42e"
client = anthropic.Anthropic()

# ── DATE HELPERS ──
def parse_date(s):
    if not s: return None
    s = s.strip()
    for fmt in ["%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S GMT",
                "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%SZ"]:
        try: return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except: pass
    try: return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
    except: return None

def is_recent(pub_str, hours=36):
    dt = parse_date(pub_str)
    if not dt: return True
    return (datetime.now(timezone.utc) - dt) < timedelta(hours=hours)

def fmt_heure(pub_str):
    dt = parse_date(pub_str)
    if not dt: return ""
    paris = dt + timedelta(hours=2)
    return f"{paris.hour:02d}h{paris.minute:02d}"

# ── OAT CURVE (BCE) ──
def fetch_oat_curve():
    maturities = [("2 ans","SR_2Y"),("5 ans","SR_5Y"),("10 ans","SR_10Y"),
                  ("20 ans","SR_20Y"),("30 ans","SR_30Y")]
    curve = []
    for label, mat in maturities:
        url = f"https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_A.SV_C_YM.{mat}?lastNObservations=2&format=jsondata"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read())
            series = data["dataSets"][0]["series"]["0:0:0:0:0:0:0"]["observations"]
            dates = data["structure"]["dimensions"]["observation"][0]["values"]
            obs_sorted = sorted(series.items(), key=lambda x: int(x[0]))
            latest_val = float(obs_sorted[-1][1][0])
            prev_val = float(obs_sorted[-2][1][0]) if len(obs_sorted) >= 2 else latest_val
            latest_date = dates[int(obs_sorted[-1][0])]["id"] if dates else ""
            trend = "up" if latest_val > prev_val + 0.001 else "down" if latest_val < prev_val - 0.001 else "flat"
            diff = round(latest_val - prev_val, 3)
            curve.append({"maturity": label, "rate": round(latest_val, 3),
                         "prev": round(prev_val, 3), "diff": diff, "trend": trend, "date": latest_date})
            print(f"  OAT {label}: {latest_val:.3f}% ({trend})")
        except Exception as e:
            print(f"  OAT {label}: erreur - {e}")
            curve.append({"maturity": label, "rate": None, "prev": None,
                         "diff": None, "trend": "flat", "date": ""})
    return curve

# ── ECONOMIC CALENDAR ──
def fetch_economic_calendar():
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    friday = monday + timedelta(days=4)
    url = (f"https://econdb.com/api/events/?country=FR,EU,DE"
           f"&date_after={monday.isoformat()}&date_before={friday.isoformat()}"
           f"&importance=2,3&format=json")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        events = []
        for e in data.get("results", []):
            events.append({"date": e.get("date",""), "time": e.get("time",""),
                          "pays": e.get("country",""), "event": e.get("event",""),
                          "importance": e.get("importance", 1),
                          "previous": e.get("previous",""), "consensus": e.get("consensus",""),
                          "actual": e.get("actual","")})
        print(f"  Calendrier: {len(events)} events")
        return sorted(events, key=lambda x: (x["date"], x["time"]))
    except Exception as e:
        print(f"  Calendrier erreur: {e}")
        return []

# ── CURIOSITY & CULTURE ECO ──
def generate_curiosity(today, ts):
    prompt = f"""Date : {today}. Tu es un expert en histoire economique et finance.

Genere 3 contenus courts et fascinants pour un professionnel de la finance. JSON uniquement sans backticks :
{{
  "chiffre_du_jour": {{
    "chiffre": "Un chiffre economique surprenant et recent",
    "contexte": "1-2 phrases expliquant ce chiffre",
    "source": "Source"
  }},
  "ephemeride": {{
    "evenement": "Un evenement economique ou financier historique marquant survenu ce jour",
    "impact": "1 phrase sur l'impact de cet evenement"
  }},
  "graphique_semaine": {{
    "titre": "Titre du phenomene economique a visualiser",
    "description": "2-3 phrases expliquant la tendance",
    "donnees": [
      {{"label": "P1", "valeur": 0}}, {{"label": "P2", "valeur": 0}},
      {{"label": "P3", "valeur": 0}}, {{"label": "P4", "valeur": 0}}, {{"label": "P5", "valeur": 0}}
    ]
  }}
}}"""
    try:
        response = client.messages.create(model="claude-haiku-4-5-20251001", max_tokens=800,
                                          messages=[{"role": "user", "content": prompt}])
        text = "".join(b.text for b in response.content if hasattr(b, "text"))
        s, e = text.find("{"), text.rfind("}")
        return json.loads(text[s:e+1]) if s != -1 else {}
    except Exception as ex:
        print(f"  Curiosite erreur: {ex}")
        return {}

# ── RSS SOURCES (economie/finance) ──
RSS_SOURCES = [
    ("BFM Business",    "https://www.bfmtv.com/rss/news-flux-rss/all-news/economie/"),
    ("Le Monde Eco",    "https://www.lemonde.fr/economie/rss_full.xml"),
    ("Le Monde Eco",    "https://www.lemonde.fr/entreprises/rss_full.xml"),
    ("Le Monde Eco",    "https://www.lemonde.fr/politique/rss_full.xml"),
    ("Challenges",      "https://www.challenges.fr/rss.xml"),
    ("Capital",         "https://www.capital.fr/feed"),
    ("La Tribune",      "https://www.latribune.fr/rss/rubriques/economie.html"),
]

# ── RSS SOURCES (droit des affaires) ──
RSS_DROIT = [
    ("Legifrance",        "https://www.legifrance.gouv.fr/contenu/Rss/RssJuriCass.xml"),
    ("Dalloz Actualite",  "https://www.dalloz-actualite.fr/rss"),
]

# ── RSS VATICAN NEWS ──
RSS_VATICAN = [
    ("Vatican News", "https://www.vaticannews.va/fr.rss.xml"),
]

def fetch_rss(source, url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; briefing-bot/1.0)"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = resp.read()
        root = ET.fromstring(data)
        items = []
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link  = (item.findtext("link")  or "").strip()
            pub   = (item.findtext("pubDate") or "").strip()
            desc  = re.sub(r"<[^>]+>", "", (item.findtext("description") or ""))[:250]
            if title and link:
                items.append({"source": source, "titre": title, "url": link,
                             "resume": desc.strip(), "pub": pub, "heure": fmt_heure(pub)})
        return items
    except Exception as e:
        print(f"  RSS {source}: {e}")
        return []

def get_rss_from_list(source_list, hours=36, max_total=None):
    all_articles = []
    seen_urls = set()
    for source, url in source_list:
        for a in fetch_rss(source, url):
            if a["url"] not in seen_urls and is_recent(a["pub"], hours=hours):
                seen_urls.add(a["url"])
                all_articles.append(a)
    if max_total:
        all_articles = all_articles[:max_total]
    return all_articles

# ── PERIGON (Les Echos + Le Figaro) ──
def get_perigon_articles():
    articles = []
    queries = [
        {"source": "lesechos.fr",  "nom": "Les Echos",  "q": "economie finance marches",           "pageSize": 20},
        {"source": "lesechos.fr",  "nom": "Les Echos",  "q": "entreprises resultats strategie",     "pageSize": 15},
        {"source": "lesechos.fr",  "nom": "Les Echos",  "q": "fusion acquisition M&A taux BCE",     "pageSize": 15},
        {"source": "lefigaro.fr",  "nom": "Le Figaro",  "q": "economie finance marches",            "pageSize": 20},
        {"source": "lefigaro.fr",  "nom": "Le Figaro",  "q": "entreprises politique budget",        "pageSize": 15},
        {"source": "lefigaro.fr",  "nom": "Le Figaro",  "q": "taux OAT BCE inflation conjoncture",  "pageSize": 15},
    ]
    for q in queries:
        try:
            params = urllib.parse.urlencode({"apiKey": PERIGON_KEY, "language": "fr",
                                             "sortBy": "date", "pageSize": q.get("pageSize", 15),
                                             "source": q["source"], "q": q.get("q", "")})
            url = f"https://api.goperigon.com/v1/all?{params}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            count = 0
            for a in data.get("articles", []):
                titre = (a.get("title") or "").strip()
                url_  = (a.get("url") or "").strip()
                pub   = (a.get("pubDate") or a.get("addDate") or "").strip()
                desc  = (a.get("description") or a.get("shortSummary") or "").strip()
                if titre and url_ and is_recent(pub, hours=36):
                    articles.append({"source": q["nom"], "titre": titre, "url": url_,
                                    "resume": desc[:250], "pub": pub, "heure": fmt_heure(pub)})
                    count += 1
            print(f"  Perigon {q['nom']} ({q['q'][:30]}): {count} articles")
        except Exception as e:
            print(f"  Perigon {q['nom']}: {e}")
    return articles

# ── HAIKU SYNTHESIS ──
def parse_json_safe(text):
    s = text.find("{")
    if s == -1: raise ValueError(f"No JSON: {text[:200]}")
    depth, in_str, i = 0, False, s
    while i < len(text):
        c = text[i]
        if c == '"' and (i == 0 or text[i-1] != "\\"): in_str = not in_str
        elif not in_str:
            if c == "{": depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    raw = text[s:i+1]
                    try: return json.loads(raw)
                    except:
                        raw = re.sub(r',(\s*[}\]])', r'\1', raw)
                        return json.loads(raw)
        i += 1
    # Reparation JSON tronque
    raw = text[s:]
    for end in range(len(raw)-1, 0, -1):
        if raw[end] == "}":
            try: return json.loads(raw[:end+1])
            except: continue
    raise ValueError(f"JSON irreparable apres {len(text)} chars")

def synthesize(articles, today, ts):
    date_short = datetime.now().strftime("%d/%m/%Y")
    ctx = "\n".join(f"[{i}] {a['source']} | {a['heure']} | {a['titre']}"
                    for i, a in enumerate(articles))
    prompt = f"""Tu es un analyste financier senior a Paris. Date: {today} {ts}.

{len(articles)} vrais articles d'aujourd'hui :
{ctx}

Genere un briefing JSON tres analytique et precis. La synthese doit etre dense, professionnelle, avec des chiffres concrets et des implications pratiques pour un professionnel de la finance. Pas de generalites journalistiques.

Pour chaque section, utilise les INDEX les plus pertinents (5 par section). Remplis TOUTES les sections. Aucun article en anglais.

JSON sans backticks :
{{
  "timestamp": "{ts} le {date_short}",
  "alerte": null,
  "synthese": {{
    "resume": "5-6 phrases analytiques et precises : chiffres cles, tendances, implications marche. Ton professionnel, pas journalistique.",
    "points": [
      {{"titre": "Marches - sujet precis avec chiffre", "detail": "analyse avec donnees chiffrees et implications concretes"}},
      {{"titre": "Macro - sujet precis avec chiffre", "detail": "analyse avec donnees chiffrees et implications concretes"}},
      {{"titre": "Entreprises/M&A - sujet precis", "detail": "analyse avec montants et implications strategiques"}},
      {{"titre": "Politique/Geo - sujet precis", "detail": "impact economique chiffre et concret"}}
    ]
  }},
  "marches":     {{"indices": [0,1,2,3,4]}},
  "entreprises": {{"indices": [0,1,2,3,4]}},
  "ma":          {{"indices": [0,1,2,3,4]}},
  "macro":       {{"indices": [0,1,2,3,4]}},
  "politique":   {{"indices": [0,1,2,3,4]}},
  "taux":        {{"indices": [0,1,2,3,4]}}
}}

REGLES STRICTES :
- "macro" = indicateurs economiques uniquement (PIB, inflation, BCE, conjoncture)
- "politique" = politique et geopolitique uniquement
- "taux" = taux d'interet, OAT, Bund, spread, credit, BCE, obligations
- "ma" = deals, transactions, LBO, PE uniquement
- "entreprises" = resultats, nominations, strategie (pas de deals M&A)
- Sections macro et politique doivent avoir des articles DIFFERENTS
- Aucun article en anglais"""

    response = client.messages.create(model="claude-haiku-4-5-20251001", max_tokens=3000,
                                      messages=[{"role": "user", "content": prompt}])
    text = "".join(b.text for b in response.content if hasattr(b, "text"))
    print(f"  Haiku: {len(text)} chars")
    return parse_json_safe(text)

def build_briefing(classified, articles):
    briefing = {
        "timestamp":   classified.get("timestamp", ""),
        "alerte":      classified.get("alerte"),
        "synthese":    classified.get("synthese", {}),
        "marches":     {"metrics": [], "articles": []},
        "entreprises": {"articles": []},
        "ma":          {"articles": []},
        "macro":       {"articles": []},
        "politique":   {"articles": []},
        "taux":        {"articles": [], "courbe": []},
    }
    for key in ["marches", "entreprises", "ma", "macro", "politique", "taux"]:
        indices = classified.get(key, {}).get("indices", [])
        seen = set()
        for idx in indices:
            if isinstance(idx, int) and 0 <= idx < len(articles):
                a = articles[idx]
                if a["url"] not in seen:
                    seen.add(a["url"])
                    briefing[key]["articles"].append({
                        "source": a["source"], "heure": a.get("heure",""),
                        "titre": a["titre"], "resume": a.get("resume",""), "url": a["url"]
                    })
    return briefing

# ── EMAIL ──
def send_email(briefing, curiosity, today, ts):
    import os
    api_key   = os.environ.get("RESEND_API_KEY", "")
    recipient = os.environ.get("RECIPIENT_EMAIL", "")
    if not api_key or not recipient:
        print("  Email: secrets manquants, skip")
        return

    import requests as req_lib

    syn     = briefing.get("synthese", {})
    points  = syn.get("points", [])
    metrics = briefing.get("marches", {}).get("metrics", [])

    metrics_html = ""
    for m in metrics:
        color = "#2d6e45" if m.get("dir") == "up" else "#c0392b" if m.get("dir") == "down" else "#7a7570"
        metrics_html += f"""<td style="width:50%;padding:6px 4px;vertical-align:top">
          <div style="background:#f9f6f1;border:1px solid rgba(26,26,26,0.1);border-radius:6px;padding:10px 12px">
            <div style="font-size:9px;letter-spacing:.1em;text-transform:uppercase;color:#7a7570;margin-bottom:3px">{m.get('label','')}</div>
            <div style="font-family:Georgia,serif;font-size:18px;font-weight:600;color:#1a1a1a">{m.get('value','--')}</div>
            <div style="font-size:11px;font-weight:500;color:{color};margin-top:2px">{m.get('change','')}</div>
          </div></td>"""

    metrics_rows = ""
    items = [x for x in metrics_html.split('<td style="width:50%') if x.strip()]
    for i in range(0, len(items), 2):
        pair = items[i:i+2]
        cells = "".join(['<td style="width:50%' + p for p in pair])
        if len(pair) == 1: cells += '<td style="width:50%;padding:6px 4px"></td>'
        metrics_rows += f"<tr>{cells}</tr>"

    points_html = ""
    for p in points:
        titre = p.get("titre", "")
        parts = titre.split(" - ", 1)
        label = parts[0].strip() if len(parts) > 1 else ""
        title = parts[1].strip() if len(parts) > 1 else titre
        points_html += f"""<div style="border-bottom:1px solid rgba(26,26,26,0.07);padding:10px 0">
          {"<div style='font-size:9px;font-weight:500;letter-spacing:.1em;text-transform:uppercase;color:#b5602a;margin-bottom:3px'>" + label + "</div>" if label else ""}
          <div style="font-family:Georgia,serif;font-size:13px;color:#1a1a1a;margin-bottom:3px">{title}</div>
          <div style="font-size:12px;color:#7a7570;line-height:1.55">{p.get('detail','')}</div>
        </div>"""

    curiosity_html = ""
    chiffre = curiosity.get("chiffre_du_jour", {})
    ephem   = curiosity.get("ephemeride", {})
    if chiffre:
        curiosity_html += f"""<div style="background:#fff8f0;border-left:3px solid #d4924e;padding:12px 16px;margin-bottom:10px;border-radius:0 6px 6px 0">
          <div style="font-size:9px;font-weight:500;letter-spacing:.1em;text-transform:uppercase;color:#b5602a;margin-bottom:4px">Chiffre du jour</div>
          <div style="font-family:Georgia,serif;font-size:22px;font-weight:600;color:#1a1a1a;margin-bottom:4px">{chiffre.get('chiffre','')}</div>
          <div style="font-size:12px;color:#7a7570;line-height:1.55">{chiffre.get('contexte','')}</div>
        </div>"""
    if ephem:
        curiosity_html += f"""<div style="background:#f5f2ed;border-radius:6px;padding:12px 16px;margin-bottom:10px">
          <div style="font-size:9px;font-weight:500;letter-spacing:.1em;text-transform:uppercase;color:#7a7570;margin-bottom:4px">Ephemeride economique</div>
          <div style="font-family:Georgia,serif;font-size:13px;color:#1a1a1a;margin-bottom:3px">{ephem.get('evenement','')}</div>
          <div style="font-size:12px;color:#7a7570">{ephem.get('impact','')}</div>
        </div>"""

    sections = [("marches","Marches"),("entreprises","Entreprises"),("ma","M&A"),
                ("macro","Macro"),("politique","Politique"),("taux","Taux")]
    articles_html = ""
    for key, label in sections:
        arts = briefing.get(key, {}).get("articles", [])[:3]
        if not arts: continue
        articles_html += f"""<div style="margin-bottom:20px">
          <div style="font-size:9px;font-weight:500;letter-spacing:.12em;text-transform:uppercase;color:#7a7570;border-bottom:1px solid rgba(26,26,26,0.12);padding-bottom:5px;margin-bottom:8px">{label}</div>"""
        for a in arts:
            url, titre, resume = a.get("url",""), a.get("titre",""), a.get("resume","")
            src, heure = a.get("source",""), a.get("heure","")
            lo = f'<a href="{url}" style="text-decoration:none;color:inherit">' if url else ""
            lc = "</a>" if url else ""
            cta = '<div style="font-size:9px;letter-spacing:.06em;text-transform:uppercase;color:#b5602a;margin-top:5px;font-weight:500">Lire</div>' if url else ""
            articles_html += f"""<div style="border-bottom:1px solid rgba(26,26,26,0.06);padding:8px 0">
              <div style="font-size:9px;color:#7a7570;margin-bottom:3px">{src} {heure}</div>
              {lo}<div style="font-family:Georgia,serif;font-size:13px;color:#1a1a1a;line-height:1.4;margin-bottom:3px">{titre}</div>{lc}
              {"<div style='font-size:11px;color:#7a7570;line-height:1.55'>" + resume + "</div>" if resume else ""}
              {cta}</div>"""
        articles_html += "</div>"

    html = f"""<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f0ede8;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif">
<div style="max-width:600px;margin:0 auto;padding:20px 16px">
  <div style="background:#1a1a1a;border-radius:8px 8px 0 0;padding:22px 26px 18px">
    <div style="font-size:9px;letter-spacing:.18em;text-transform:uppercase;color:rgba(255,255,255,.35);margin-bottom:5px">{today}</div>
    <div style="font-family:Georgia,serif;font-size:26px;color:#fff;font-weight:400;line-height:1">Morning <em style="font-style:italic;color:#d4924e">Brief</em></div>
  </div>
  <div style="background:#fff;padding:22px 26px;border-left:1px solid rgba(26,26,26,.1);border-right:1px solid rgba(26,26,26,.1)">
    <div style="font-family:Georgia,serif;font-size:15px;line-height:1.8;color:#2a2520;border-bottom:1px solid rgba(26,26,26,.1);padding-bottom:14px;margin-bottom:14px">{syn.get('resume','')}</div>
    {points_html}
  </div>
  <div style="background:#fff;padding:18px 26px;border-left:1px solid rgba(26,26,26,.1);border-right:1px solid rgba(26,26,26,.1);border-top:1px solid rgba(26,26,26,.06)">
    <div style="font-size:9px;font-weight:500;letter-spacing:.12em;text-transform:uppercase;color:#7a7570;margin-bottom:10px">Indices et taux</div>
    <table style="width:100%;border-collapse:collapse">{metrics_rows}</table>
  </div>
  {"<div style='background:#fff;padding:18px 26px;border-left:1px solid rgba(26,26,26,.1);border-right:1px solid rgba(26,26,26,.1);border-top:1px solid rgba(26,26,26,.06)'>" + curiosity_html + "</div>" if curiosity_html else ""}
  <div style="background:#fff;padding:18px 26px 26px;border:1px solid rgba(26,26,26,.1);border-top:1px solid rgba(26,26,26,.06);border-radius:0 0 8px 8px">
    <div style="font-size:9px;font-weight:500;letter-spacing:.12em;text-transform:uppercase;color:#7a7570;border-bottom:1px solid rgba(26,26,26,.12);padding-bottom:7px;margin-bottom:14px">Articles du jour</div>
    {articles_html}
  </div>
  <div style="text-align:center;padding:14px 0;font-size:9px;color:rgba(26,26,26,.25);letter-spacing:.06em">MORNING BRIEF - {ts} - Genere automatiquement</div>
</div></body></html>"""

    try:
        resp = req_lib.post(
            "https://api.resend.com/emails",
            json={"from": "Morning Brief <onboarding@resend.dev>", "to": [recipient],
                  "subject": f"Morning Brief - {today}", "html": html},
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
                     "User-Agent": "Mozilla/5.0"},
            timeout=15
        )
        if resp.status_code in (200, 201): print(f"  Email envoye -> {recipient}")
        else: print(f"  Email erreur {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        print(f"  Email erreur: {e}")

# ── MAIN ──
def main():
    now = datetime.now()
    days   = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]
    months = ["janvier","fevrier","mars","avril","mai","juin",
              "juillet","aout","septembre","octobre","novembre","decembre"]
    today = f"{days[now.weekday()]} {now.day} {months[now.month-1]} {now.year}"
    ts    = now.strftime("%Hh%M")

    print(f"Generation -- {today} {ts}")

    print("-> RSS economie...")
    rss_articles = get_rss_from_list(RSS_SOURCES, hours=36)
    print(f"  RSS eco total: {len(rss_articles)} articles")

    print("-> Perigon (Echos + Figaro)...")
    perigon_articles = get_perigon_articles()

    seen = set()
    articles = []
    for a in rss_articles + perigon_articles:
        if a["url"] not in seen:
            seen.add(a["url"])
            articles.append(a)
    print(f"-> Total eco: {len(articles)} articles")

    if not articles:
        print("ERREUR: aucun article")
        raise SystemExit(1)

    print("-> Droit des affaires...")
    droit_articles = get_rss_from_list(RSS_DROIT, hours=72, max_total=15)
    print(f"  Droit: {len(droit_articles)} articles")

    print("-> Vatican News...")
    vatican_articles = get_rss_from_list(RSS_VATICAN, hours=72, max_total=15)
    print(f"  Vatican: {len(vatican_articles)} articles")

    print("-> Courbe OAT...")
    oat_curve = fetch_oat_curve()

    print("-> Calendrier economique...")
    calendar = fetch_economic_calendar()

    print("-> Curiosite & culture eco...")
    curiosity = generate_curiosity(today, ts)

    print("-> Haiku classification...")
    classified = synthesize(articles, today, ts)

    briefing = build_briefing(classified, articles)
    briefing["taux"]["courbe"]  = oat_curve
    briefing["calendrier"]      = calendar
    briefing["curiosite"]       = curiosity
    briefing["droit"]           = {"articles": droit_articles}
    briefing["vatican"]         = {"articles": vatican_articles}

    for key in ["synthese","marches","entreprises","ma","macro","politique","taux"]:
        if key not in briefing:
            briefing[key] = {"articles":[]} if key != "synthese" else {"resume":"","points":[]}
    if "calendrier" not in briefing: briefing["calendrier"] = []
    if "curiosite"  not in briefing: briefing["curiosite"]  = {}

    for k in ["marches","entreprises","ma","macro","politique","taux","droit","vatican"]:
        n = len(briefing.get(k,{}).get("articles",[]))
        print(f"  {k}: {n} articles")

    with open("briefing.json", "w", encoding="utf-8") as f:
        json.dump(briefing, f, ensure_ascii=False, indent=2)
    print(f"OK -- briefing.json {len(json.dumps(briefing))} chars")

    print("-> Envoi email...")
    send_email(briefing, curiosity, today, ts)

if __name__ == "__main__":
    main()
