import anthropic
import json
import re
import urllib.parse
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

PERIGON_KEY = "51d90d54-03df-4bec-910e-ac40924fb42e"
client = anthropic.Anthropic()

# ── COURBE DES TAUX OAT (BCE) ──
def fetch_oat_curve():
    """Fetch OAT France yield curve from ECB API with date and trend."""
    maturities = [
        ("2 ans",  "SR_2Y"),
        ("5 ans",  "SR_5Y"),
        ("10 ans", "SR_10Y"),
        ("20 ans", "SR_20Y"),
        ("30 ans", "SR_30Y"),
    ]
    curve = []
    for label, mat in maturities:
        # Fetch last 2 observations to get trend
        url = f"https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_A.SV_C_YM.{mat}?lastNObservations=2&format=jsondata"
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json"
            })
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read())
            series = data["dataSets"][0]["series"]["0:0:0:0:0:0:0"]["observations"]
            # Get dates from structure
            dates = data["structure"]["dimensions"]["observation"][0]["values"]
            obs_sorted = sorted(series.items(), key=lambda x: int(x[0]))
            latest_val  = float(obs_sorted[-1][1][0])
            prev_val    = float(obs_sorted[-2][1][0]) if len(obs_sorted) >= 2 else latest_val
            latest_date = dates[int(obs_sorted[-1][0])]["id"] if dates else ""
            trend = "up" if latest_val > prev_val + 0.001 else "down" if latest_val < prev_val - 0.001 else "flat"
            diff  = round(latest_val - prev_val, 3)
            curve.append({
                "maturity": label,
                "rate":     round(latest_val, 3),
                "prev":     round(prev_val, 3),
                "diff":     diff,
                "trend":    trend,
                "date":     latest_date
            })
            print(f"  OAT {label}: {latest_val:.3f}% ({trend}, date: {latest_date})")
        except Exception as e:
            print(f"  OAT {label}: erreur - {e}")
            curve.append({"maturity": label, "rate": None, "prev": None, "diff": None, "trend": "flat", "date": ""})
    return curve

# ── CALENDRIER ÉCONOMIQUE (EconDB) ──
def fetch_economic_calendar():
    """Fetch economic calendar for France and EU this week."""
    from datetime import date, timedelta
    today = date.today()
    # Get Monday and Friday of current week
    monday = today - timedelta(days=today.weekday())
    friday = monday + timedelta(days=4)

    url = (f"https://econdb.com/api/events/"
           f"?country=FR,EU,DE&"
           f"date_after={monday.isoformat()}&"
           f"date_before={friday.isoformat()}&"
           f"importance=2,3&"  # importance 2=medium, 3=high only
           f"format=json")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        events = []
        for e in data.get("results", []):
            events.append({
                "date":       e.get("date", ""),
                "time":       e.get("time", ""),
                "pays":       e.get("country", ""),
                "event":      e.get("event", ""),
                "importance": e.get("importance", 1),
                "previous":   e.get("previous", ""),
                "consensus":  e.get("consensus", ""),
                "actual":     e.get("actual", ""),
            })
        print(f"  Calendrier: {len(events)} events cette semaine")
        return sorted(events, key=lambda x: (x["date"], x["time"]))
    except Exception as e:
        print(f"  Calendrier erreur: {e}")
        return []

# ── DONNÉES DE MARCHÉ (Yahoo Finance depuis GitHub Actions) ──
YAHOO_SYMBOLS = {
    "CAC 40":        {"sym": "%5EFCHI",    "fmt": lambda v: f"{v:,.0f}".replace(",", " ")},
    "Eurostoxx 50":  {"sym": "%5ESTOXX50E","fmt": lambda v: f"{v:,.0f}".replace(",", " ")},
    "S&P 500":       {"sym": "%5EGSPC",    "fmt": lambda v: f"{v:,.0f}".replace(",", " ")},
    "Nasdaq":        {"sym": "%5EIXIC",    "fmt": lambda v: f"{v:,.0f}".replace(",", " ")},
    "EUR/USD":       {"sym": "EURUSD%3DX", "fmt": lambda v: f"{v:.4f}"},
    "Brent":         {"sym": "BZ%3DF",     "fmt": lambda v: f"{v:.1f} $"},
    "Or":            {"sym": "GC%3DF",     "fmt": lambda v: f"{v:,.0f}".replace(",", " ") + " $"},
}

def fetch_market_data():
    """Fetch market data via Stooq CSV API - no auth required."""
    QUOTES = [
        ("CAC 40",       "^cac",      lambda v: "{:,.0f}".format(v).replace(",", " ")),
        ("Eurostoxx 50", "^stoxx50",  lambda v: "{:,.0f}".format(v).replace(",", " ")),
        ("S&P 500",      "^spx",      lambda v: "{:,.0f}".format(v).replace(",", " ")),
        ("Nasdaq",       "^ndq",      lambda v: "{:,.0f}".format(v).replace(",", " ")),
        ("EUR/USD",      "eurusd",    lambda v: "{:.4f}".format(v)),
        ("Brent",        "lco.f",     lambda v: "{:.1f} $".format(v)),
        ("Or",           "xauusd",    lambda v: "{:,.0f} $".format(v).replace(",", " ")),
        ("Euribor 3M",   "euribor3m", lambda v: "{:.3f}%".format(v)),
        ("Euribor 6M",   "euribor6m", lambda v: "{:.3f}%".format(v)),
    ]
    metrics = []
    for label, sym, fmt in QUOTES:
        url = f"https://stooq.com/q/l/?s={sym}&f=sd2t2ohlcv&h&e=csv"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                text = resp.read().decode("utf-8")
            lines = text.strip().split("\n")
            if len(lines) < 2:
                raise ValueError("empty response")
            vals = lines[1].split(",")
            close = float(vals[4])
            open_ = float(vals[3])
            if close <= 0:
                raise ValueError("zero price")
            pct  = (close - open_) / open_ * 100
            dir_ = "up" if pct > 0.05 else "down" if pct < -0.05 else "flat"
            metrics.append({"label": label, "value": fmt(close), "change": "{:+.2f}%".format(pct), "dir": dir_})
            print(f"  {label}: {fmt(close)} ({pct:+.2f}%)")
        except Exception as e:
            print(f"  {label}: erreur Stooq - {e}")
            metrics.append({"label": label, "value": "-", "change": "-", "dir": "flat"})
    return metrics

def parse_date(s):
    if not s:
        return None
    s = s.strip()
    formats = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S GMT",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%SZ",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except:
            pass
    # Try fromisoformat
    try:
        s2 = s.replace("Z", "+00:00")
        return datetime.fromisoformat(s2).astimezone(timezone.utc)
    except:
        pass
    return None

def is_recent(pub_str, hours=36):
    """True if article published within last N hours."""
    dt = parse_date(pub_str)
    if not dt:
        return True  # keep if can't parse
    now = datetime.now(timezone.utc)
    return (now - dt) < timedelta(hours=hours)

def fmt_heure(pub_str):
    dt = parse_date(pub_str)
    if not dt:
        return ""
    paris = dt + timedelta(hours=2)
    return f"{paris.hour:02d}h{paris.minute:02d}"

# ── RSS SOURCES (gratuits, fiables, économie FR) ──
RSS_SOURCES = [
    # Reuters - flux valides
    ("Reuters France",  "https://feeds.reuters.com/reuters/frenchNews"),
    ("Reuters France",  "https://feeds.reuters.com/reuters/businessNews"),
    # BFM Business
    ("BFM Business",    "https://www.bfmtv.com/rss/news-flux-rss/all-news/economie/"),
    ("BFM Business",    "https://www.bfmtv.com/rss/news-flux-rss/all-news/bourse/"),
    # Le Monde
    ("Le Monde Éco",    "https://www.lemonde.fr/economie/rss_full.xml"),
    ("Le Monde Éco",    "https://www.lemonde.fr/entreprises/rss_full.xml"),
    ("Le Monde Éco",    "https://www.lemonde.fr/politique/rss_full.xml"),
    # Challenges
    ("Challenges",      "https://www.challenges.fr/rss.xml"),
    # Politico
    ("L'Express",       "https://www.lexpress.fr/arc/outboundfeeds/rss/"),
    ("Le Point",         "https://www.lepoint.fr/rss.xml"),
]

def fetch_rss(source, url):
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (compatible; briefing-bot/1.0)"}
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = resp.read()
        root = ET.fromstring(data)
        items = []
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link  = (item.findtext("link")  or "").strip()
            pub   = (item.findtext("pubDate") or "").strip()
            desc  = (item.findtext("description") or "").strip()
            # Strip HTML from description
            desc = re.sub(r"<[^>]+>", "", desc)[:250]
            if title and link and is_recent(pub, hours=36):
                items.append({
                    "source": source, "titre": title,
                    "url": link, "resume": desc,
                    "pub": pub, "heure": fmt_heure(pub)
                })
        return items
    except Exception as e:
        print(f"  RSS {source}: {e}")
        return []

def get_rss_articles():
    all_articles = []
    seen_urls = set()
    for source, url in RSS_SOURCES:
        items = fetch_rss(source, url)
        for a in items:
            if a["url"] not in seen_urls:
                seen_urls.add(a["url"])
                all_articles.append(a)
    print(f"  RSS total: {len(all_articles)} articles")
    return all_articles

# ── PERIGON (uniquement Les Echos + Le Figaro) ──
def get_perigon_articles():
    articles = []
    queries = [
        {"source": "lesechos.fr", "nom": "Les Echos", "q": "economie finance marches", "pageSize": 20},
        {"source": "lesechos.fr", "nom": "Les Echos", "q": "entreprises resultats strategie", "pageSize": 15},
        {"source": "lesechos.fr", "nom": "Les Echos", "q": "fusion acquisition M&A taux BCE", "pageSize": 15},
        {"source": "lefigaro.fr", "nom": "Le Figaro", "q": "economie finance marches", "pageSize": 20},
        {"source": "lefigaro.fr", "nom": "Le Figaro", "q": "entreprises politique budget", "pageSize": 15},
        {"source": "lefigaro.fr", "nom": "Le Figaro", "q": "taux OAT BCE inflation conjoncture", "pageSize": 15},
    ]
    for q in queries:
        try:
            params = urllib.parse.urlencode({
                "apiKey":   PERIGON_KEY,
                "language": "fr",
                "sortBy":   "date",
                "pageSize": q.get("pageSize", 15),
                "source":   q["source"],
                "q":        q.get("q", ""),
            })
            url = f"https://api.goperigon.com/v1/all?{params}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            arts = data.get("articles", [])
            count = 0
            for a in arts:
                titre = (a.get("title") or "").strip()
                url_  = (a.get("url") or "").strip()
                pub   = (a.get("pubDate") or a.get("addDate") or "").strip()
                desc  = (a.get("description") or a.get("shortSummary") or "").strip()
                if titre and url_ and is_recent(pub, hours=36):
                    articles.append({
                        "source": q["nom"],
                        "titre":  titre,
                        "url":    url_,
                        "resume": desc[:250],
                        "pub":    pub,
                        "heure":  fmt_heure(pub),
                    })
                    count += 1
            print(f"  Perigon {q['nom']}: {count} articles récents")
        except Exception as e:
            print(f"  Perigon {q['nom']}: {e}")
    return articles

# ── CLAUDE HAIKU : classification + synthèse ──
def parse_json(text):
    s = text.find('{')
    if s == -1:
        raise ValueError(f"No JSON: {text[:200]}")
    depth, in_str, i = 0, False, s
    while i < len(text):
        c = text[i]
        if c == '"' and (i == 0 or text[i-1] != '\\'):
            in_str = not in_str
        elif not in_str:
            if c == '{': depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    raw = text[s:i+1]
                    try:
                        return json.loads(raw)
                    except:
                        raw = re.sub(r',(\s*[}\]])', r'\1', raw)
                        return json.loads(raw)
        i += 1
    raise ValueError("Unmatched braces")

def synthesize(articles, today, ts):
    date_short = datetime.now().strftime("%d/%m/%Y")
    ctx = "\n".join(
        f"[{i}] {a['source']} | {a['heure']} | {a['titre']}"
        for i, a in enumerate(articles)
    )
    prompt = f"""Analyste M&A senior à Paris. Date: {today} {ts}.

{len(articles)} vrais articles d'aujourd'hui :
{ctx}

Génère le briefing JSON. Pour chaque section mets les INDEX les plus pertinents (5-7 par section, pas de répétition inutile). Remplis TOUTES les sections.

JSON sans backticks :
{{
  "timestamp": "{ts} le {date_short}",
  "alerte": null,
  "synthese": {{
    "resume": "4 phrases synthèse actu éco du jour, chiffres précis",
    "points": [
      {{"titre": "Marchés", "detail": "analyse avec chiffres"}},
      {{"titre": "Macro", "detail": "conjoncture avec chiffres"}},
      {{"titre": "Entreprises / M&A", "detail": "actu corporate"}},
      {{"titre": "Politique / Géo", "detail": "impact économique"}}
    ]
  }},
  "marches": {{"indices": [0,1,2,3,4]}},
  "entreprises": {{"indices": [0,1,2,3,4]}},
  "ma":          {{"indices": [0,1,2,3,4]}},
  "macro":       {{"indices": [0,1,2,3,4]}},
  "politique":   {{"indices": [0,1,2,3,4]}},
  "taux":        {{"indices": [0,1,2,3,4]}}
}}

RÈGLES IMPORTANTES :
- "macro" = UNIQUEMENT indicateurs économiques (PIB, inflation, chômage, conjoncture)
- "politique" = UNIQUEMENT politique (gouvernement FR, UE, géopolitique, budget)
- "taux" = UNIQUEMENT articles sur taux d'intérêt, OAT, Bund, spread, crédit, BCE, obligations
- Aucun article en anglais — uniquement presse française
- Ces sections doivent avoir des articles DIFFÉRENTS
- "ma" = UNIQUEMENT deals, transactions, LBO, PE, rachats
- "entreprises" = résultats, nominations, stratégie (PAS de deals M&A)"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )
    text = "".join(b.text for b in response.content if hasattr(b, "text"))
    print(f"  Haiku: {len(text)} chars")
    return parse_json(text)

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
        "taux":        {"articles": []},
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
                        "source": a["source"],
                        "heure":  a.get("heure", ""),
                        "titre":  a["titre"],
                        "resume": a.get("resume", ""),
                        "url":    a["url"],
                    })
    return briefing

def main():
    now = datetime.now()
    days   = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]
    months = ["janvier","février","mars","avril","mai","juin",
              "juillet","août","septembre","octobre","novembre","décembre"]
    today = f"{days[now.weekday()]} {now.day} {months[now.month-1]} {now.year}"
    ts    = now.strftime("%Hh%M")

    print(f"Génération — {today} {ts}")

    # 1. RSS (sources gratuites)
    print("→ RSS...")
    rss_articles = get_rss_articles()

    # 2. Perigon (Les Echos + Le Figaro uniquement)
    print("→ Perigon (Echos + Figaro)...")
    perigon_articles = get_perigon_articles()

    # 3. Merge + dédoublonnage
    all_articles = rss_articles + perigon_articles
    seen = set()
    articles = []
    for a in all_articles:
        if a["url"] not in seen:
            seen.add(a["url"])
            articles.append(a)

    print(f"→ Total: {len(articles)} articles uniques et récents")

    if not articles:
        print("ERREUR: aucun article")
        raise SystemExit(1)

    # 4. Données de marché live
    print("→ Données de marché...")
    market_metrics = fetch_market_data()

    # 5b. Courbe des taux OAT
    print("→ Courbe des taux OAT...")
    oat_curve = fetch_oat_curve()

    # 5c. Calendrier économique
    print("→ Calendrier économique...")
    calendar = fetch_economic_calendar()

    # 5. Haiku: classification + synthèse
    print("→ Haiku classification...")
    classified = synthesize(articles, today, ts)

    # 5. Build final briefing
    briefing = build_briefing(classified, articles)
    briefing["marches"]["metrics"] = market_metrics
    briefing["taux"]["courbe"] = oat_curve
    briefing["calendrier"] = calendar

    # 6. Vérification sections vides
    for key in ["synthese","marches","entreprises","ma","macro","politique","taux"]:
        if key not in briefing:
            briefing[key] = {"articles":[]} if key != "synthese" else {"resume":"","points":[]}
    if "calendrier" not in briefing:
        briefing["calendrier"] = []

    # 7. Stats
    for k in ["marches","entreprises","ma","macro","politique","taux"]:
        n = len(briefing.get(k,{}).get("articles",[]))
        print(f"  {k}: {n} articles")

    with open("briefing.json", "w", encoding="utf-8") as f:
        json.dump(briefing, f, ensure_ascii=False, indent=2)

    print(f"✓ briefing.json — {len(json.dumps(briefing))} chars")

    # Envoi email
    print("→ Envoi email...")
    send_email(briefing, today, ts)

def send_email(briefing, today, ts):
    """Send beautiful HTML briefing email via Resend."""
    import os
    api_key = os.environ.get("RESEND_API_KEY", "")
    recipient = os.environ.get("RECIPIENT_EMAIL", "")
    if not api_key or not recipient:
        print("  Email: RESEND_API_KEY ou RECIPIENT_EMAIL manquant, skip")
        return

    syn = briefing.get("synthese", {})
    points = syn.get("points", [])
    metrics = briefing.get("marches", {}).get("metrics", [])

    # Build metrics HTML
    metrics_html = ""
    for m in metrics:
        color = "#2d6e45" if m.get("dir") == "up" else "#c0392b" if m.get("dir") == "down" else "#7a7570"
        metrics_html += f"""
        <td style="width:50%;padding:8px 4px;vertical-align:top">
          <div style="background:#f9f6f1;border:1px solid rgba(26,26,26,0.1);border-radius:6px;padding:12px 14px">
            <div style="font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:#7a7570;margin-bottom:4px">{m.get('label','')}</div>
            <div style="font-family:Georgia,serif;font-size:20px;font-weight:600;color:#1a1a1a">{m.get('value','—')}</div>
            <div style="font-size:12px;font-weight:500;color:{color};margin-top:2px">{m.get('change','')}</div>
          </div>
        </td>"""

    # Wrap metrics in rows of 2
    metrics_rows = ""
    metric_items = metrics_html.split('<td style="width:50%')
    metric_items = [x for x in metric_items if x.strip()]
    for i in range(0, len(metric_items), 2):
        pair = metric_items[i:i+2]
        row_cells = ''.join(['<td style="width:50%' + p for p in pair])
        if len(pair) == 1:
            row_cells += '<td style="width:50%;padding:8px 4px"></td>'
        metrics_rows += f"<tr>{row_cells}</tr>"

    # Build points HTML
    points_html = ""
    for p in points:
        titre = p.get("titre", "")
        parts = titre.split("—")
        label = parts[0].strip() if len(parts) > 1 else ""
        title = parts[1].strip() if len(parts) > 1 else titre
        points_html += f"""
        <div style="border-bottom:1px solid rgba(26,26,26,0.07);padding:12px 0">
          {"<div style='font-size:10px;font-weight:500;letter-spacing:.1em;text-transform:uppercase;color:#b5602a;margin-bottom:3px'>" + label + "</div>" if label else ""}
          <div style="font-family:Georgia,serif;font-size:14px;color:#1a1a1a;margin-bottom:4px">{title}</div>
          <div style="font-size:12px;color:#7a7570;line-height:1.6">{p.get('detail','')}</div>
        </div>"""

    # Build top articles (3 per section)
    sections = [
        ("marches",     "Marchés"),
        ("entreprises", "Entreprises"),
        ("ma",          "M&A"),
        ("macro",       "Macro"),
        ("politique",   "Politique"),
        ("taux",        "Taux"),
    ]
    articles_html = ""
    for key, label in sections:
        arts = briefing.get(key, {}).get("articles", [])[:3]
        if not arts:
            continue
        articles_html += f"""
        <div style="margin-bottom:24px">
          <div style="font-size:10px;font-weight:500;letter-spacing:.12em;text-transform:uppercase;color:#7a7570;border-bottom:1px solid rgba(26,26,26,0.12);padding-bottom:6px;margin-bottom:10px">{label}</div>"""
        for a in arts:
            url = a.get("url", "")
            titre = a.get("titre", "")
            resume = a.get("resume", "")
            src = a.get("source", "")
            heure = a.get("heure", "")
            link_open = f'<a href="{url}" style="text-decoration:none;color:inherit">' if url else ""
            link_close = "</a>" if url else ""
            cta = f'<div style="font-size:10px;letter-spacing:.06em;text-transform:uppercase;color:#b5602a;margin-top:6px;font-weight:500">Lire →</div>' if url else ""
            articles_html += f"""
          <div style="border-bottom:1px solid rgba(26,26,26,0.06);padding:10px 0">
            <div style="font-size:10px;color:#7a7570;margin-bottom:4px">{src} {heure}</div>
            {link_open}<div style="font-family:Georgia,serif;font-size:14px;color:#1a1a1a;line-height:1.45;margin-bottom:4px">{titre}</div>{link_close}
            {"<div style='font-size:12px;color:#7a7570;line-height:1.6'>" + resume + "</div>" if resume else ""}
            {cta}
          </div>"""
        articles_html += "</div>"

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f0ede8;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif">
  <div style="max-width:600px;margin:0 auto;padding:20px 16px">

    <!-- HEADER -->
    <div style="background:#1a1a1a;border-radius:8px 8px 0 0;padding:24px 28px 20px">
      <div style="font-size:10px;letter-spacing:.18em;text-transform:uppercase;color:rgba(255,255,255,.35);margin-bottom:6px">{today}</div>
      <div style="font-family:Georgia,serif;font-size:28px;color:#fff;font-weight:400;line-height:1">Morning <em style="font-style:italic;color:#d4924e">Brief</em></div>
    </div>

    <!-- SYNTHESE -->
    <div style="background:#fff;padding:24px 28px;border-left:1px solid rgba(26,26,26,0.1);border-right:1px solid rgba(26,26,26,0.1)">
      <div style="font-family:Georgia,serif;font-size:16px;line-height:1.8;color:#2a2520;border-bottom:1px solid rgba(26,26,26,0.1);padding-bottom:16px;margin-bottom:16px">{syn.get('resume','')}</div>
      {points_html}
    </div>

    <!-- MARCHES -->
    <div style="background:#fff;padding:20px 28px;border-left:1px solid rgba(26,26,26,0.1);border-right:1px solid rgba(26,26,26,0.1);border-top:1px solid rgba(26,26,26,0.06)">
      <div style="font-size:10px;font-weight:500;letter-spacing:.12em;text-transform:uppercase;color:#7a7570;margin-bottom:12px">Indices & taux</div>
      <table style="width:100%;border-collapse:collapse">{metrics_rows}</table>
    </div>

    <!-- ARTICLES -->
    <div style="background:#fff;padding:20px 28px 28px;border:1px solid rgba(26,26,26,0.1);border-top:1px solid rgba(26,26,26,0.06);border-radius:0 0 8px 8px">
      <div style="font-size:10px;font-weight:500;letter-spacing:.12em;text-transform:uppercase;color:#7a7570;border-bottom:1px solid rgba(26,26,26,0.12);padding-bottom:8px;margin-bottom:16px">Articles du jour</div>
      {articles_html}
    </div>

    <!-- FOOTER -->
    <div style="text-align:center;padding:16px 0;font-size:10px;color:rgba(26,26,26,.3);letter-spacing:.06em">
      MORNING BRIEF · {ts} · Généré automatiquement
    </div>
  </div>
</body>
</html>"""

    try:
        import requests as req_lib
    except ImportError:
        import subprocess, sys
        subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "-q"])
        import requests as req_lib

    try:
        resp = req_lib.post(
            "https://api.resend.com/emails",
            json={
                "from": "Morning Brief <onboarding@resend.dev>",
                "to": [recipient],
                "subject": f"Morning Brief — {today}",
                "html": html
            },
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            timeout=15
        )
        if resp.status_code == 200 or resp.status_code == 201:
            result = resp.json()
            print(f"  Email envoye -> {recipient} (id: {result.get('id','')})")
        else:
            print(f"  Email erreur {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        print(f"  Email erreur: {e}")


if __name__ == "__main__":
    main()
