import anthropic
import json
import re
import urllib.parse
from datetime import datetime

client = anthropic.Anthropic()

def make_search_url(source, titre):
    q = urllib.parse.quote(titre)
    s = source.lower()
    if 'echo' in s:      return f"https://www.google.com/search?q=site%3Alesechos.fr+{q}"
    if 'figaro' in s:    return f"https://www.google.com/search?q=site%3Alefigaro.fr+{q}"
    if 'agefi' in s:     return f"https://www.google.com/search?q=site%3Aagefi.fr+{q}"
    if 'ft' in s:        return f"https://www.google.com/search?q=site%3Aft.com+{q}"
    if 'reuters' in s:   return f"https://www.google.com/search?q=site%3Areuters.com+{q}"
    if 'bloomberg' in s: return f"https://www.google.com/search?q=site%3Abloomberg.com+{q}"
    if 'monde' in s:     return f"https://www.google.com/search?q=site%3Alemonde.fr+{q}"
    return f"https://www.google.com/search?q={urllib.parse.quote(source + ' ' + titre)}"

def fix_urls(articles):
    result = []
    for a in articles:
        titre = a.get('titre', '')
        source = a.get('source', '')
        s = source.lower()
        # Toujours Google search pour Les Echos et Le Figaro (URLs inventées = fausses)
        # Pour les autres sources, garder l'URL si elle semble valide
        force_search = 'echo' in s or 'figaro' in s
        url = str(a.get('url') or '')
        bad = not url or url in ('null','None','') or url.count('/') < 3
        if (force_search or bad) and titre:
            a['url'] = make_search_url(source, titre)
        result.append(a)
    return result

def parse_json(text):
    print(f"  Réponse brute ({len(text)} chars): {text[:200]}...")
    s = text.find('{')
    if s == -1:
        raise ValueError(f"Pas de JSON dans la réponse: {text[:300]}")
    raw = text[s:]
    e = raw.rfind('}')
    if e != -1:
        raw = raw[:e+1]
    try:
        return json.loads(raw)
    except json.JSONDecodeError as err:
        print(f"  JSON decode error: {err}, tentative de réparation...")
        raw = re.sub(r',\s*}', '}', raw)
        raw = re.sub(r',\s*]', ']', raw)
        opens_bracket = raw.count('[') - raw.count(']')
        opens_brace = raw.count('{') - raw.count('}')
        raw += ']' * max(0, opens_bracket)
        raw += '}' * max(0, opens_brace)
        return json.loads(raw)

def generate_briefing(today, now):
    prompt = f"""Tu es un analyste financier senior à Paris. Date du jour : {today}, {now}.

Génère un briefing économique et financier matinal complet et réaliste pour cette date.
Base-toi sur le contexte économique actuel : géopolitique, BCE, marchés européens, actualité M&A française.

Réponds UNIQUEMENT avec le JSON suivant, sans texte avant ou après, sans backticks markdown :

{{
  "timestamp": "{now} le {today}",
  "alerte": null,
  "synthese": {{
    "resume": "4 phrases synthétisant l'essentiel de l'actualité économique et financière du jour",
    "points": [
      {{"titre": "Point macro clé", "detail": "explication concrète pour un professionnel M&A"}},
      {{"titre": "Point marché clé", "detail": "explication concrète pour un professionnel M&A"}},
      {{"titre": "Point M&A / entreprise", "detail": "explication concrète pour un professionnel M&A"}},
      {{"titre": "Point géopolitique / politique", "detail": "explication concrète pour un professionnel M&A"}}
    ]
  }},
  "marches": {{
    "metrics": [
      {{"label": "CAC 40", "value": "VALEUR", "change": "VARIATION", "dir": "up"}},
      {{"label": "Eurostoxx 50", "value": "VALEUR", "change": "VARIATION", "dir": "up"}},
      {{"label": "OAT 10 ans", "value": "VALEUR%", "change": "VARIATION pb", "dir": "up"}},
      {{"label": "Bund 10 ans", "value": "VALEUR%", "change": "VARIATION pb", "dir": "up"}},
      {{"label": "Spread OAT/Bund", "value": "VALEUR pb", "change": "VARIATION pb", "dir": "flat"}},
      {{"label": "EUR/USD", "value": "VALEUR", "change": "VARIATION%", "dir": "flat"}},
      {{"label": "Brent", "value": "VALEUR $", "change": "VARIATION%", "dir": "up"}},
      {{"label": "S&P 500", "value": "VALEUR", "change": "VARIATION%", "dir": "up"}}
    ],
    "articles": [
      {{"source": "Les Echos", "heure": "07h30", "titre": "Titre article marchés Les Echos", "resume": "Résumé 2 phrases."}},
      {{"source": "Le Figaro", "heure": "07h45", "titre": "Titre article marchés Le Figaro", "resume": "Résumé 2 phrases."}},
      {{"source": "Reuters", "heure": "06h00", "titre": "Titre article Reuters", "resume": "Résumé 2 phrases."}},
      {{"source": "Bloomberg", "heure": "06h30", "titre": "Titre article Bloomberg", "resume": "Résumé 2 phrases."}},
      {{"source": "Les Echos", "heure": "08h00", "titre": "Second article marchés Les Echos", "resume": "Résumé 2 phrases."}}
    ]
  }},
  "entreprises": {{
    "articles": [
      {{"source": "Les Echos", "heure": "07h00", "titre": "Titre article entreprise", "resume": "Résumé 2 phrases."}},
      {{"source": "Le Figaro", "heure": "07h15", "titre": "Titre article entreprise", "resume": "Résumé 2 phrases."}},
      {{"source": "Reuters", "heure": "06h45", "titre": "Titre article entreprise", "resume": "Résumé 2 phrases."}},
      {{"source": "Les Echos", "heure": "08h15", "titre": "Second article entreprise", "resume": "Résumé 2 phrases."}},
      {{"source": "Le Figaro", "heure": "08h30", "titre": "Second article Le Figaro entreprise", "resume": "Résumé 2 phrases."}}
    ]
  }},
  "ma": {{
    "articles": [
      {{"source": "Les Echos", "heure": "07h00", "titre": "Titre deal M&A", "resume": "Résumé deal avec montant si possible."}},
      {{"source": "Le Figaro", "heure": "07h20", "titre": "Titre deal M&A", "resume": "Résumé deal avec montant si possible."}},
      {{"source": "L'Agefi", "heure": "07h30", "titre": "Titre deal M&A Agefi", "resume": "Résumé deal avec montant si possible."}},
      {{"source": "Reuters", "heure": "06h00", "titre": "Titre deal M&A Reuters", "resume": "Résumé deal avec montant si possible."}},
      {{"source": "Bloomberg", "heure": "06h30", "titre": "Titre deal M&A Bloomberg", "resume": "Résumé deal avec montant si possible."}}
    ]
  }},
  "macro": {{
    "articles": [
      {{"source": "Les Echos", "heure": "07h00", "titre": "Titre article macro", "resume": "Résumé 2 phrases."}},
      {{"source": "Le Figaro", "heure": "07h15", "titre": "Titre article macro", "resume": "Résumé 2 phrases."}},
      {{"source": "FT", "heure": "06h00", "titre": "Titre article macro FT", "resume": "Résumé 2 phrases."}},
      {{"source": "Reuters", "heure": "06h30", "titre": "Titre article macro Reuters", "resume": "Résumé 2 phrases."}},
      {{"source": "Les Echos", "heure": "08h00", "titre": "Second article macro Les Echos", "resume": "Résumé 2 phrases."}}
    ]
  }},
  "politique": {{
    "articles": [
      {{"source": "Les Echos", "heure": "07h00", "titre": "Titre article politique éco", "resume": "Résumé 2 phrases."}},
      {{"source": "Le Figaro", "heure": "07h15", "titre": "Titre article politique éco", "resume": "Résumé 2 phrases."}},
      {{"source": "AFP", "heure": "06h00", "titre": "Titre article AFP politique", "resume": "Résumé 2 phrases."}},
      {{"source": "FT", "heure": "06h30", "titre": "Titre article FT politique", "resume": "Résumé 2 phrases."}},
      {{"source": "Le Figaro", "heure": "08h00", "titre": "Second article Le Figaro politique", "resume": "Résumé 2 phrases."}}
    ]
  }}
}}"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )
    text = "".join(b.text for b in response.content if hasattr(b, "text"))
    return parse_json(text)


def main():
    now = datetime.now()
    days = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]
    months = ["janvier","février","mars","avril","mai","juin","juillet","août","septembre","octobre","novembre","décembre"]
    today = f"{days[now.weekday()]} {now.day} {months[now.month-1]} {now.year}"
    time_str = now.strftime("%Hh%M")

    print(f"Génération — {today} {time_str}")

    briefing = generate_briefing(today, time_str)
    print(f"  Sections générées : {list(briefing.keys())}")

    # Ajouter URLs Google pour Les Echos et Le Figaro
    for key in ["marches", "entreprises", "ma", "macro", "politique"]:
        section = briefing.get(key, {})
        articles = section.get("articles", []) if isinstance(section, dict) else []
        if articles:
            briefing[key]["articles"] = fix_urls(articles)
            print(f"  {key}: {len(articles)} articles")

    with open("briefing.json", "w", encoding="utf-8") as f:
        json.dump(briefing, f, ensure_ascii=False, indent=2)

    size = len(json.dumps(briefing))
    print(f"OK — briefing.json généré ({size} chars)")

if __name__ == "__main__":
    main()
