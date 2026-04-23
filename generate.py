import anthropic
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone

PERIGON_KEY = "51d90d54-03df-4bec-910e-ac40924fb42e"
client = anthropic.Anthropic()

# ── PERIGON ──
def perigon_fetch(params):
    """Fetch articles from Perigon API."""
    base = "https://api.goperigon.com/v1/all?"
    params["language"] = "fr"
    params["sortBy"] = "date"
    params["pageSize"] = params.get("pageSize", 10)
    url = base + urllib.parse.urlencode(params)
    # Try both auth methods
    for headers in [
        {"User-Agent": "Mozilla/5.0", "x-api-key": PERIGON_KEY},
        {"User-Agent": "Mozilla/5.0", "Authorization": f"Bearer {PERIGON_KEY}"},
    ]:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                if data.get("articles"):
                    return data
        except urllib.error.HTTPError as e:
            body = e.read().decode()[:200]
            print(f"  HTTP {e.code}: {body}")
        except Exception as e:
            print(f"  Erreur: {e}")
    # Last attempt with apiKey param
    url2 = url + f"&apiKey={PERIGON_KEY}"
    req = urllib.request.Request(url2, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())

def get_articles():
    """Fetch articles by topic from Perigon."""
    all_articles = []

    queries = [
        # Marchés & Finance
        {"q": "bourse CAC marchés financiers taux", "pageSize": 8},
        # Entreprises
        {"q": "résultats entreprise stratégie acquisition France", "pageSize": 8},
        # M&A
        {"q": "fusion acquisition rachat cession LBO private equity", "pageSize": 8},
        # Macro
        {"q": "BCE inflation croissance conjoncture économie France zone euro", "pageSize": 8},
        # Politique
        {"q": "politique économique budget France gouvernement géopolitique", "pageSize": 8},
    ]

    for q in queries:
        try:
            data = perigon_fetch(q)
            arts = data.get("articles", [])
            if arts:
                # Log all keys on first article for debugging
                print(f"  Sample keys: {list(arts[0].keys())}")
                print(f"  Sample values: { {k: str(v)[:50] for k,v in arts[0].items()} }")
            for a in arts:
                # Perigon field mapping (from observed keys)
                src_obj = a.get("source", {})
                source = src_obj.get("name","") if isinstance(src_obj, dict) else str(src_obj)
                titre  = (a.get("title") or a.get("name") or a.get("headline") or a.get("authorsByline") or "").strip()
                url    = (a.get("url") or a.get("link") or "").strip()
                desc   = (a.get("description") or a.get("summary") or a.get("content") or "").strip()
                pub    = (a.get("pubDate") or a.get("publishedAt") or a.get("addDate") or "").strip()
                if url and source:  # au minimum URL + source
                    all_articles.append({
                        "source": source,
                        "titre":  titre or url,
                        "url":    url,
                        "resume": desc[:200] if desc else "",
                        "pub":    pub,
                        "query":  q["q"]
                    })
            print(f"  '{q['q'][:40]}': {len(arts)} articles")
        except Exception as e:
            print(f"  Erreur Perigon ({q['q'][:30]}): {e}")

    # Dédoublonnage par URL (garder même si URL vide)
    seen = set()
    unique = []
    for a in all_articles:
        key = a["url"] if a["url"] else a["titre"]
        if key and key not in seen:
            seen.add(key)
            unique.append(a)
        elif not key:
            unique.append(a)

    print(f"  Total unique: {len(unique)} articles")
    return unique

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
    """Single Haiku call: classify articles into sections + generate synthesis."""

    # Pass articles as numbered list
    ctx = "\n".join(
        f"[{i}] {a['source']} | {a['titre']}" + (f" | {a['resume'][:80]}" if a['resume'] else "")
        for i, a in enumerate(articles)
    )

    date_short = datetime.now().strftime("%d/%m/%Y")

    prompt = f"""Tu es analyste financier senior à Paris. Date: {today} {ts}.

Voici {len(articles)} vrais articles récupérés aujourd'hui :
{ctx}

Génère un briefing JSON. Pour chaque section, utilise les INDEX des articles les plus pertinents.
Les articles gardent leur URL originale — ne les modifie pas.

JSON uniquement sans backticks :
{{
  "timestamp": "{ts} le {date_short}",
  "alerte": null,
  "synthese": {{
    "resume": "4 phrases synthèse de l'actu éco du jour avec chiffres clés",
    "points": [
      {{"titre": "Marchés", "detail": "analyse marchés avec chiffres"}},
      {{"titre": "Macro", "detail": "conjoncture avec chiffres"}},
      {{"titre": "Entreprises / M&A", "detail": "actu corporate du jour"}},
      {{"titre": "Politique / Géo", "detail": "impact politique-économique"}}
    ]
  }},
  "marches": {{
    "metrics": [
      {{"label": "CAC 40", "value": "?", "change": "?", "dir": "up"}},
      {{"label": "Eurostoxx 50", "value": "?", "change": "?", "dir": "up"}},
      {{"label": "OAT 10 ans", "value": "?%", "change": "? pb", "dir": "up"}},
      {{"label": "Bund 10 ans", "value": "?%", "change": "? pb", "dir": "up"}},
      {{"label": "Spread OAT/Bund", "value": "? pb", "change": "? pb", "dir": "flat"}},
      {{"label": "EUR/USD", "value": "?", "change": "?", "dir": "flat"}},
      {{"label": "Brent", "value": "? $", "change": "?", "dir": "up"}},
      {{"label": "S&P 500", "value": "?", "change": "?", "dir": "up"}}
    ],
    "indices": [0,1,2,3,4]
  }},
  "entreprises": {{"indices": [0,1,2,3,4]}},
  "ma":          {{"indices": [0,1,2,3,4]}},
  "macro":       {{"indices": [0,1,2,3,4]}},
  "politique":   {{"indices": [0,1,2,3,4]}}
}}

Choisis les indices les plus pertinents pour chaque section (5-7 par section).
Remplis absolument toutes les sections."""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )
    text = "".join(b.text for b in response.content if hasattr(b, "text"))
    print(f"  Haiku réponse: {len(text)} chars")
    return parse_json(text)

def build_briefing(classified, articles):
    """Replace indices with real article objects."""
    briefing = {
        "timestamp":  classified.get("timestamp", ""),
        "alerte":     classified.get("alerte"),
        "synthese":   classified.get("synthese", {}),
        "marches":    {"metrics": classified.get("marches", {}).get("metrics", []), "articles": []},
        "entreprises":{"articles": []},
        "ma":         {"articles": []},
        "macro":      {"articles": []},
        "politique":  {"articles": []},
    }

    sections = ["marches", "entreprises", "ma", "macro", "politique"]
    for key in sections:
        indices = classified.get(key, {}).get("indices", [])
        seen = set()
        for idx in indices:
            if isinstance(idx, int) and 0 <= idx < len(articles):
                a = articles[idx]
                if a["url"] not in seen:
                    seen.add(a["url"])
                    briefing[key]["articles"].append({
                        "source": a["source"],
                        "heure":  fmt_date(a.get("pub","")),
                        "titre":  a["titre"],
                        "resume": a["resume"],
                        "url":    a["url"],
                    })

    return briefing

def fmt_date(pub):
    """Extract HHhMM from ISO date string."""
    if not pub:
        return ""
    try:
        # Handle various ISO formats
        pub = pub.replace("Z", "+00:00")
        dt = datetime.fromisoformat(pub)
        # Convert to Paris time (UTC+2 in summer, +1 in winter — approx)
        local_hour = (dt.hour + 2) % 24
        return f"{local_hour:02d}h{dt.minute:02d}"
    except:
        return ""

def main():
    now = datetime.now()
    days   = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]
    months = ["janvier","février","mars","avril","mai","juin",
              "juillet","août","septembre","octobre","novembre","décembre"]
    today = f"{days[now.weekday()]} {now.day} {months[now.month-1]} {now.year}"
    ts    = now.strftime("%Hh%M")

    print(f"Génération — {today} {ts}")

    # 1. Fetch real articles from Perigon
    print("→ Perigon: récupération des articles...")
    articles = get_articles()

    if not articles:
        print("ERREUR: aucun article récupéré")
        raise SystemExit(1)
    print(f"  {len(articles)} articles uniques récupérés")

    # 2. Single Haiku call for classification + synthesis
    print("→ Haiku: classification et synthèse...")
    classified = synthesize(articles, today, ts)

    # 3. Build final briefing with real URLs
    briefing = build_briefing(classified, articles)

    # 4. Stats
    for k in ["marches","entreprises","ma","macro","politique"]:
        n = len(briefing.get(k,{}).get("articles",[]))
        print(f"  {k}: {n} articles")

    # 5. Save
    with open("briefing.json", "w", encoding="utf-8") as f:
        json.dump(briefing, f, ensure_ascii=False, indent=2)

    print(f"✓ briefing.json — {len(json.dumps(briefing))} chars")

if __name__ == "__main__":
    main()
