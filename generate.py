import anthropic
import json
import re
import urllib.parse
from datetime import datetime

client = anthropic.Anthropic()

def parse_json(text):
    s = text.find('{')
    if s == -1:
        raise ValueError(f"No JSON in: {text[:200]}")
    depth = 0
    in_str = False
    i = s
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
                    except json.JSONDecodeError:
                        raw = re.sub(r',(\s*[}\]])', r'\1', raw)
                        return json.loads(raw)
        i += 1
    raise ValueError("Unmatched braces")

def call_with_search(prompt):
    messages = [{"role": "user", "content": prompt}]
    while True:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=5000,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=messages
        )
        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = [
                {"type": "tool_result", "tool_use_id": b.id, "content": "ok"}
                for b in response.content if b.type == "tool_use"
            ]
            messages.append({"role": "user", "content": tool_results})
        else:
            return "".join(b.text for b in response.content if hasattr(b, "text"))

def make_link(source, titre):
    q = urllib.parse.quote_plus(titre)
    s = source.lower()
    if 'reuters' in s:    return f"https://fr.reuters.com/search/news?blob={q}"
    if 'bfm' in s:        return f"https://www.bfmtv.com/recherche/?q={q}"
    if 'tribune' in s:    return f"https://www.latribune.fr/recherche/?q={q}"
    if 'agefi' in s:      return f"https://www.agefi.fr/search?q={q}"
    if 'capital' in s:    return f"https://www.capital.fr/search?q={q}"
    if 'challenges' in s: return f"https://www.challenges.fr/search?q={q}"
    if 'boursorama' in s: return f"https://www.boursorama.com/bourse/actualites/recherche/?q={q}"
    if 'monde' in s:      return f"https://www.lemonde.fr/recherche/?keywords={q}"
    if 'politico' in s:   return f"https://www.politico.eu/search/{urllib.parse.quote(titre)}/"
    if 'echo' in s:       return f"https://www.lesechos.fr/recherche?keywords={q}"
    if 'figaro' in s:     return f"https://recherche.lefigaro.fr/recherche/?q={q}"
    return f"https://www.google.com/search?q={urllib.parse.quote(source+' '+titre)}"

def main():
    now = datetime.now()
    days = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]
    months = ["janvier","février","mars","avril","mai","juin",
              "juillet","août","septembre","octobre","novembre","décembre"]
    today = f"{days[now.weekday()]} {now.day} {months[now.month-1]} {now.year}"
    ts = now.strftime("%Hh%M")
    date_short = now.strftime("%d/%m/%Y")

    print(f"Génération — {today} {ts}")

    prompt = f"""Tu es un journaliste économique senior à Paris. Date du jour : {today}, {ts}.

MISSION : Génère un briefing économique et financier matinal en cherchant les VRAIES actualités du jour.

SOURCES AUTORISÉES (toutes gratuites, françaises prioritaires) :
- Reuters France (fr.reuters.com)
- BFM Business (bfmtv.com)  
- La Tribune (latribune.fr)
- L'Agefi (agefi.fr)
- Boursorama (boursorama.com)
- Capital (capital.fr)
- Challenges (challenges.fr)
- Le Monde Économie (lemonde.fr/economie)
- Politico Europe (politico.eu)
- AFP via Boursorama

RÈGLES STRICTES :
1. Cherche sur le web les articles publiés AUJOURD'HUI ({today})
2. Utilise UNIQUEMENT des articles réels trouvés — pas d'inventions
3. Si pas d'article trouvé pour une section, mets 3 articles minimum avec ce que tu trouves
4. Données marchés : cherche les cours actuels du jour
5. Titres : copie le titre EXACT de l'article trouvé
6. URLs : NE PAS inclure d'URL dans le JSON (elles seront générées automatiquement)

Génère ce JSON (sans backticks, sans texte autour) :
{{
  "timestamp": "{ts} le {date_short}",
  "alerte": null,
  "synthese": {{
    "resume": "4-5 phrases résumant l'essentiel du jour : marchés, macro, entreprises, géopolitique. Chiffres précis.",
    "points": [
      {{"titre": "Marchés — [titre précis]", "detail": "analyse avec chiffres, angle professionnel M&A"}},
      {{"titre": "Macro — [titre précis]", "detail": "analyse avec chiffres, angle professionnel M&A"}},
      {{"titre": "M&A / Entreprises — [titre précis]", "detail": "deal ou tendance avec montant si possible"}},
      {{"titre": "Géopolitique / Politique — [titre précis]", "detail": "impact économique concret"}}
    ]
  }},
  "marches": {{
    "metrics": [
      {{"label": "CAC 40", "value": "XXXX", "change": "+X.X%", "dir": "up|down|flat"}},
      {{"label": "Eurostoxx 50", "value": "XXXX", "change": "+X.X%", "dir": "up|down|flat"}},
      {{"label": "OAT 10 ans", "value": "X.XX%", "change": "+X pb", "dir": "up|down|flat"}},
      {{"label": "Bund 10 ans", "value": "X.XX%", "change": "+X pb", "dir": "up|down|flat"}},
      {{"label": "Spread OAT/Bund", "value": "XX pb", "change": "+X pb", "dir": "up|down|flat"}},
      {{"label": "EUR/USD", "value": "X.XXXX", "change": "+X.X%", "dir": "up|down|flat"}},
      {{"label": "Brent", "value": "XXX $", "change": "+X.X%", "dir": "up|down|flat"}},
      {{"label": "S&P 500", "value": "XXXX", "change": "+X.X%", "dir": "up|down|flat"}}
    ],
    "articles": [
      {{"source": "SOURCE", "heure": "HHhMM", "titre": "TITRE EXACT article trouvé"}},
      {{"source": "SOURCE", "heure": "HHhMM", "titre": "TITRE EXACT article trouvé"}},
      {{"source": "SOURCE", "heure": "HHhMM", "titre": "TITRE EXACT article trouvé"}},
      {{"source": "SOURCE", "heure": "HHhMM", "titre": "TITRE EXACT article trouvé"}},
      {{"source": "SOURCE", "heure": "HHhMM", "titre": "TITRE EXACT article trouvé"}}
    ]
  }},
  "entreprises": {{
    "articles": [
      {{"source": "SOURCE", "heure": "HHhMM", "titre": "TITRE EXACT", "resume": "2 phrases résumé."}},
      {{"source": "SOURCE", "heure": "HHhMM", "titre": "TITRE EXACT", "resume": "2 phrases résumé."}},
      {{"source": "SOURCE", "heure": "HHhMM", "titre": "TITRE EXACT", "resume": "2 phrases résumé."}},
      {{"source": "SOURCE", "heure": "HHhMM", "titre": "TITRE EXACT", "resume": "2 phrases résumé."}},
      {{"source": "SOURCE", "heure": "HHhMM", "titre": "TITRE EXACT", "resume": "2 phrases résumé."}}
    ]
  }},
  "ma": {{
    "articles": [
      {{"source": "SOURCE", "heure": "HHhMM", "titre": "TITRE EXACT deal M&A", "resume": "acquéreur, cible, montant."}},
      {{"source": "SOURCE", "heure": "HHhMM", "titre": "TITRE EXACT deal M&A", "resume": "acquéreur, cible, montant."}},
      {{"source": "SOURCE", "heure": "HHhMM", "titre": "TITRE EXACT deal M&A", "resume": "acquéreur, cible, montant."}},
      {{"source": "SOURCE", "heure": "HHhMM", "titre": "TITRE EXACT deal M&A", "resume": "acquéreur, cible, montant."}},
      {{"source": "SOURCE", "heure": "HHhMM", "titre": "TITRE EXACT deal M&A", "resume": "acquéreur, cible, montant."}}
    ]
  }},
  "macro": {{
    "articles": [
      {{"source": "SOURCE", "heure": "HHhMM", "titre": "TITRE EXACT macro", "resume": "2 phrases avec chiffres."}},
      {{"source": "SOURCE", "heure": "HHhMM", "titre": "TITRE EXACT macro", "resume": "2 phrases avec chiffres."}},
      {{"source": "SOURCE", "heure": "HHhMM", "titre": "TITRE EXACT macro", "resume": "2 phrases avec chiffres."}},
      {{"source": "SOURCE", "heure": "HHhMM", "titre": "TITRE EXACT macro", "resume": "2 phrases avec chiffres."}},
      {{"source": "SOURCE", "heure": "HHhMM", "titre": "TITRE EXACT macro", "resume": "2 phrases avec chiffres."}}
    ]
  }},
  "politique": {{
    "articles": [
      {{"source": "SOURCE", "heure": "HHhMM", "titre": "TITRE EXACT politique", "resume": "2 phrases impact éco."}},
      {{"source": "SOURCE", "heure": "HHhMM", "titre": "TITRE EXACT politique", "resume": "2 phrases impact éco."}},
      {{"source": "SOURCE", "heure": "HHhMM", "titre": "TITRE EXACT politique", "resume": "2 phrases impact éco."}},
      {{"source": "SOURCE", "heure": "HHhMM", "titre": "TITRE EXACT politique", "resume": "2 phrases impact éco."}},
      {{"source": "SOURCE", "heure": "HHhMM", "titre": "TITRE EXACT politique", "resume": "2 phrases impact éco."}}
    ]
  }}
}}"""

    print("→ Appel Claude Sonnet + web_search...")
    text = call_with_search(prompt)
    print(f"  Réponse: {len(text)} chars")

    briefing = parse_json(text)

    # Vérification et fallback sections manquantes
    for key in ["synthese","marches","entreprises","ma","macro","politique"]:
        if key not in briefing:
            print(f"  MANQUANT: {key} — ajout vide")
            briefing[key] = {"articles":[]} if key != "synthese" else {"resume":"","points":[]}

    # Ajout URLs de recherche pour chaque article
    for key in ["marches","entreprises","ma","macro","politique"]:
        section = briefing.get(key, {})
        articles = section.get("articles", []) if isinstance(section, dict) else []
        for a in articles:
            titre = a.get("titre","")
            source = a.get("source","")
            if titre and source:
                a["url"] = make_link(source, titre)
            # Ajouter résumé vide si manquant (section marchés n'en a pas)
            if "resume" not in a:
                a["resume"] = ""

    # Stats
    for k in ["marches","entreprises","ma","macro","politique"]:
        n = len(briefing.get(k,{}).get("articles",[]))
        print(f"  {k}: {n} articles")

    with open("briefing.json", "w", encoding="utf-8") as f:
        json.dump(briefing, f, ensure_ascii=False, indent=2)

    print(f"✓ briefing.json — {len(json.dumps(briefing))} chars")

if __name__ == "__main__":
    main()
