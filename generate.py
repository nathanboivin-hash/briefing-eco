import anthropic
import json
import re
from datetime import datetime

client = anthropic.Anthropic()

def call_with_search(prompt):
    """Call Claude with web search, handle multi-turn tool use."""
    messages = [{"role": "user", "content": prompt}]
    
    while True:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4000,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=messages
        )
        
        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": "Recherche effectuée."
                    })
            messages.append({"role": "user", "content": tool_results})
        else:
            text = "".join(b.text for b in response.content if hasattr(b, "text"))
            return text

def parse_json(text):
    """Extract and parse JSON from text, repair if truncated."""
    s = text.find("{")
    if s == -1:
        raise ValueError("Pas de JSON trouvé")
    raw = text[s:]
    e = raw.rfind("}")
    if e != -1:
        raw = raw[:e+1]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Repair truncated JSON
        raw = re.sub(r',\s*$', '', raw).rstrip('{')
        opens = raw.count('[') - raw.count(']')
        openb = raw.count('{') - raw.count('}')
        raw += ']' * max(0, opens)
        raw += '}' * max(0, openb)
        return json.loads(raw)

def make_search_url(source, titre):
    """Generate a reliable Google search URL as fallback."""
    import urllib.parse
    s = source.lower()
    q = urllib.parse.quote(titre)
    if 'echo' in s:
        return f"https://www.google.com/search?q=site%3Alesechos.fr+{q}"
    if 'figaro' in s:
        return f"https://www.google.com/search?q=site%3Alefigaro.fr+{q}"
    if 'agefi' in s:
        return f"https://www.google.com/search?q=site%3Aagefi.fr+{q}"
    if 'ft' in s or 'financial' in s:
        return f"https://www.google.com/search?q=site%3Aft.com+{q}"
    if 'reuters' in s:
        return f"https://www.google.com/search?q=site%3Areuters.com+{q}"
    if 'bloomberg' in s:
        return f"https://www.google.com/search?q=site%3Abloomberg.com+{q}"
    if 'monde' in s:
        return f"https://www.google.com/search?q=site%3Alemonde.fr+{q}"
    return f"https://www.google.com/search?q={urllib.parse.quote(source+' '+titre)}"


def fix_article_urls(articles):
    """Verify URLs look real; replace bad ones with Google search fallback."""
    import re
    fixed = []
    for a in articles:
        url = a.get('url', '')
        titre = a.get('titre', '')
        source = a.get('source', '')
        
        # Detect fake/placeholder URLs
        is_fake = (
            not url or
            url == 'null' or
            'URL-EXACTE' in url or
            'TROUVEE' in url or
            re.search(r'/article-[0-9]+$', url) and len(url) < 50 or
            url.count('/') < 3  # too short to be a real article path
        )
        
        if is_fake and titre:
            a['url'] = make_search_url(source, titre)
            a['url_type'] = 'search'
        else:
            a['url_type'] = 'direct'
        
        fixed.append(a)
    return fixed


def generate_section(section, today, now):
    """Generate one section with real web search."""
    
    queries = {
        "synthese_marches": "recherche les dernières actualités financières françaises et européennes d'aujourd'hui : cours CAC 40, OAT 10 ans, EUR/USD, Eurostoxx, Brent, et les articles de Les Échos et Le Figaro sur les marchés",
        "entreprises": "recherche sur lesechos.fr et lefigaro.fr les articles d'aujourd'hui sur les résultats d'entreprises, stratégie, nominations, publications de résultats",
        "ma": "recherche sur lesechos.fr et lefigaro.fr les articles d'aujourd'hui sur les fusions acquisitions, deals M&A, LBO, private equity, rachats d'entreprises en France et Europe",
        "macro": "recherche sur lesechos.fr et lefigaro.fr les articles d'aujourd'hui sur la macroéconomie, BCE, inflation, croissance, conjoncture France et zone euro",
        "politique": "recherche sur lesechos.fr et lefigaro.fr les articles d'aujourd'hui sur la politique économique française, les décisions gouvernementales, la géopolitique économique mondiale"
    }

    section_labels = {
        "entreprises": "résultats et vie des entreprises françaises et européennes",
        "ma": "fusions-acquisitions, LBO, private equity",
        "macro": "macroéconomie, BCE, conjoncture France et zone euro",
        "politique": "politique économique, géopolitique"
    }

    if section == "synthese_marches":
        prompt = f"""Date : {today}, {now}. 

{queries[section]}

Trouve les vrais articles publiés aujourd'hui sur lesechos.fr et lefigaro.fr avec leurs URLs exactes.

Génère ce JSON avec les vraies données trouvées. Pour chaque article, utilise le TITRE EXACT et l'URL EXACTE tels que trouvés sur le web :

{{
  "timestamp": "{now} le {today}",
  "alerte": null,
  "synthese": {{
    "resume": "4-5 phrases synthèse des marchés et de l'actualité économique du jour",
    "points": [
      {{"titre": "Point clé 1", "detail": "explication pour un professionnel finance/M&A"}},
      {{"titre": "Point clé 2", "detail": "explication pour un professionnel finance/M&A"}},
      {{"titre": "Point clé 3", "detail": "explication pour un professionnel finance/M&A"}},
      {{"titre": "Point clé 4", "detail": "explication pour un professionnel finance/M&A"}}
    ]
  }},
  "marches": {{
    "metrics": [
      {{"label": "CAC 40", "value": "VALEUR", "change": "VARIATION", "dir": "up|down|flat"}},
      {{"label": "Eurostoxx 50", "value": "VALEUR", "change": "VARIATION", "dir": "up|down|flat"}},
      {{"label": "S&P 500", "value": "VALEUR", "change": "VARIATION", "dir": "up|down|flat"}},
      {{"label": "OAT 10 ans", "value": "VALEUR%", "change": "VARIATION pb", "dir": "up|down|flat"}},
      {{"label": "Bund 10 ans", "value": "VALEUR%", "change": "VARIATION pb", "dir": "up|down|flat"}},
      {{"label": "Spread OAT/Bund", "value": "VALEUR pb", "change": "VARIATION pb", "dir": "up|down|flat"}},
      {{"label": "EUR/USD", "value": "VALEUR", "change": "VARIATION%", "dir": "up|down|flat"}},
      {{"label": "Brent", "value": "VALEUR $", "change": "VARIATION%", "dir": "up|down|flat"}}
    ],
    "articles": [
      {{"source": "Les Échos", "heure": "HHhMM", "titre": "TITRE EXACT de l'article trouvé", "resume": "résumé 2 phrases", "url": "https://URL-EXACTE-TROUVEE"}},
      {{"source": "Le Figaro", "heure": "HHhMM", "titre": "TITRE EXACT", "resume": "résumé 2 phrases", "url": "https://URL-EXACTE-TROUVEE"}},
      {{"source": "Reuters", "heure": "HHhMM", "titre": "TITRE EXACT", "resume": "résumé 2 phrases", "url": "https://URL-EXACTE-TROUVEE"}},
      {{"source": "Les Échos", "heure": "HHhMM", "titre": "TITRE EXACT", "resume": "résumé 2 phrases", "url": "https://URL-EXACTE-TROUVEE"}},
      {{"source": "Le Figaro", "heure": "HHhMM", "titre": "TITRE EXACT", "resume": "résumé 2 phrases", "url": "https://URL-EXACTE-TROUVEE"}},
      {{"source": "Bloomberg", "heure": "HHhMM", "titre": "TITRE EXACT", "resume": "résumé 2 phrases", "url": "https://URL-EXACTE-TROUVEE"}},
      {{"source": "FT", "heure": "HHhMM", "titre": "TITRE EXACT", "resume": "résumé 2 phrases", "url": "https://URL-EXACTE-TROUVEE"}},
      {{"source": "Boursorama", "heure": "HHhMM", "titre": "TITRE EXACT", "resume": "résumé 2 phrases", "url": "https://URL-EXACTE-TROUVEE"}}
    ]
  }}
}}

IMPORTANT : cherche vraiment les articles sur le web et utilise leurs vraies URLs. Réponds UNIQUEMENT en JSON valide sans texte ni backticks."""

    else:
        prompt = f"""Date : {today}, {now}.

{queries[section]}

Trouve les vrais articles publiés aujourd'hui sur lesechos.fr et lefigaro.fr sur le sujet : {section_labels[section]}.

Génère ce JSON avec les vrais articles trouvés. Utilise les TITRES EXACTS et URLs EXACTES :

{{
  "articles": [
    {{"source": "Les Échos", "heure": "HHhMM", "titre": "TITRE EXACT trouvé", "resume": "résumé 2 phrases", "url": "https://URL-EXACTE"}},
    {{"source": "Le Figaro", "heure": "HHhMM", "titre": "TITRE EXACT trouvé", "resume": "résumé 2 phrases", "url": "https://URL-EXACTE"}},
    {{"source": "L'Agefi", "heure": "HHhMM", "titre": "TITRE EXACT trouvé", "resume": "résumé 2 phrases", "url": "https://URL-EXACTE"}},
    {{"source": "Reuters", "heure": "HHhMM", "titre": "TITRE EXACT trouvé", "resume": "résumé 2 phrases", "url": "https://URL-EXACTE"}},
    {{"source": "Les Échos", "heure": "HHhMM", "titre": "TITRE EXACT trouvé", "resume": "résumé 2 phrases", "url": "https://URL-EXACTE"}},
    {{"source": "Le Figaro", "heure": "HHhMM", "titre": "TITRE EXACT trouvé", "resume": "résumé 2 phrases", "url": "https://URL-EXACTE"}},
    {{"source": "Bloomberg", "heure": "HHhMM", "titre": "TITRE EXACT trouvé", "resume": "résumé 2 phrases", "url": "https://URL-EXACTE"}},
    {{"source": "FT", "heure": "HHhMM", "titre": "TITRE EXACT trouvé", "resume": "résumé 2 phrases", "url": "https://URL-EXACTE"}}
  ]
}}

IMPORTANT : cherche vraiment sur le web et utilise les vraies URLs. Réponds UNIQUEMENT en JSON valide sans texte ni backticks."""

    text = call_with_search(prompt)
    return parse_json(text)


def main():
    now = datetime.now()
    days = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]
    months = ["janvier","février","mars","avril","mai","juin","juillet","août","septembre","octobre","novembre","décembre"]
    today = f"{days[now.weekday()]} {now.day} {months[now.month-1]} {now.year}"
    time_str = now.strftime("%Hh%M")

    print(f"Génération du briefing — {today} {time_str}")
    
    briefing = {}

    print("→ Synthèse + Marchés...")
    sm = generate_section("synthese_marches", today, time_str)
    briefing["timestamp"] = sm.get("timestamp", f"{time_str} le {now.strftime('%d/%m/%Y')}")
    briefing["alerte"] = sm.get("alerte")
    briefing["synthese"] = sm.get("synthese", {})
    briefing["marches"] = sm.get("marches", {})
    # Fix article URLs
    if briefing.get("marches", {}).get("articles"):
        briefing["marches"]["articles"] = fix_article_urls(briefing["marches"]["articles"])

    sections = ["entreprises", "ma", "macro", "politique"]
    for s in sections:
        print(f"→ {s}...")
        try:
            result = generate_section(s, today, time_str)
            # Fix URLs in each section
            if result.get("articles"):
                result["articles"] = fix_article_urls(result["articles"])
            briefing[s] = result
        except Exception as e:
            print(f"  Erreur {s}: {e}")
            briefing[s] = {"articles": []}

    with open("briefing.json", "w", encoding="utf-8") as f:
        json.dump(briefing, f, ensure_ascii=False, indent=2)

    print(f"✓ briefing.json généré ({len(json.dumps(briefing))} caractères)")

if __name__ == "__main__":
    main()


# This is appended - not used directly, see fix_urls below
