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
    QUOTES = [
        ("CAC 40",       "^FCHI",      lambda v: "{:,.0f}".format(v).replace(",", " ")),
        ("Eurostoxx 50", "^STOXX50E",  lambda v: "{:,.0f}".format(v).replace(",", " ")),
        ("S&P 500",      "^GSPC",      lambda v: "{:,.0f}".format(v).replace(",", " ")),
        ("Nasdaq",       "^IXIC",      lambda v: "{:,.0f}".format(v).replace(",", " ")),
        ("EUR/USD",      "EURUSD=X",   lambda v: "{:.4f}".format(v)),
        ("Brent",        "BZ=F",       lambda v: "{:.1f} $".format(v)),
        ("Or",           "GC=F",       lambda v: "{:,.0f} $".format(v).replace(",", " ")),
    ]
    sym_str = ",".join(q[1] for q in QUOTES)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json,*/*",
        "Accept-Language": "fr-FR,fr;q=0.9",
        "Referer": "https://finance.yahoo.com/",
    }
    results = {}
    for base in ["query1", "query2"]:
        url = f"https://{base}.finance.yahoo.com/v7/finance/quote?symbols={sym_str}&fields=regularMarketPrice,regularMarketChangePercent"
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            raw = data.get("quoteResponse", {}).get("result", [])
            if raw:
                results = {r["symbol"]: r for r in raw}
                print(f"  Yahoo OK ({base})")
                break
        except Exception as e:
            print(f"  Yahoo {base}: {e}")

    metrics = []
    for label, sym, fmt in QUOTES:
        r = results.get(sym)
        if r:
            price = r.get("regularMarketPrice", 0)
            pct   = r.get("regularMarketChangePercent", 0)
            dir_  = "up" if pct > 0.05 else "down" if pct < -0.05 else "flat"
            metrics.append({"label": label, "value": fmt(price), "change": "{:+.2f}%".format(pct), "dir": dir_})
            print(f"  {label}: {fmt(price)} ({pct:+.2f}%)")
        else:
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
    ("Reuters France",  "https://fr.reuters.com/news/rss/topNews"),
    ("Reuters France",  "https://fr.reuters.com/news/rss/businessNews"),
    ("BFM Business",    "https://www.bfmtv.com/rss/economie/"),
    ("BFM Business",    "https://www.bfmtv.com/rss/bourse/"),
    ("La Tribune",      "https://www.latribune.fr/rss/rubriques/economie.html"),
    ("La Tribune",      "https://www.latribune.fr/rss/rubriques/entreprises-finance.html"),
    ("La Tribune",      "https://www.latribune.fr/rss/rubriques/actualite-des-societes.html"),
    ("Boursorama",      "https://www.boursorama.com/rss/actualites/"),
    ("Boursorama",      "https://www.boursorama.com/rss/marches/"),
    ("Le Monde Éco",    "https://www.lemonde.fr/economie/rss_full.xml"),
    ("Le Monde Éco",    "https://www.lemonde.fr/entreprises/rss_full.xml"),
    ("Le Monde Éco",    "https://www.lemonde.fr/politique/rss_full.xml"),
    ("Challenges",      "https://www.challenges.fr/rss.xml"),
    ("Capital",         "https://www.capital.fr/feed"),
    ("L'Agefi",         "https://www.agefi.fr/rss/finance.xml"),
    ("L'Agefi",         "https://www.agefi.fr/rss/marches.xml"),
    ("Politico EU",     "https://www.politico.eu/rss"),
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

    # 5. Haiku: classification + synthèse
    print("→ Haiku classification...")
    classified = synthesize(articles, today, ts)

    # 5. Build final briefing
    briefing = build_briefing(classified, articles)
    briefing["marches"]["metrics"] = market_metrics

    # 6. Vérification sections vides
    for key in ["synthese","marches","entreprises","ma","macro","politique","taux"]:
        if key not in briefing:
            briefing[key] = {"articles":[]} if key != "synthese" else {"resume":"","points":[]}

    # 7. Stats
    for k in ["marches","entreprises","ma","macro","politique","taux"]:
        n = len(briefing.get(k,{}).get("articles",[]))
        print(f"  {k}: {n} articles")

    with open("briefing.json", "w", encoding="utf-8") as f:
        json.dump(briefing, f, ensure_ascii=False, indent=2)

    print(f"✓ briefing.json — {len(json.dumps(briefing))} chars")

if __name__ == "__main__":
    main()
