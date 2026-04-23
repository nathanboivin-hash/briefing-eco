import anthropic
import json
import re
import urllib.parse
from datetime import datetime

client = anthropic.Anthropic()

def make_link(source, titre):
    """Lien vers recherche du média — fiable avec session abonné."""
    q = urllib.parse.quote(titre)
    q_plus = urllib.parse.quote_plus(titre)
    s = source.lower()
    if 'echo' in s:
        return f"https://www.lesechos.fr/recherche?keywords={q_plus}"
    if 'figaro' in s:
        return f"https://recherche.lefigaro.fr/recherche/?q={q_plus}"
    if 'agefi' in s:
        return f"https://www.agefi.fr/search?q={q_plus}"
    if 'tribune' in s:
        return f"https://www.latribune.fr/recherche/?q={q_plus}"
    if 'bfm' in s:
        return f"https://www.bfmtv.com/recherche/?q={q_plus}"
    if 'capital' in s:
        return f"https://www.capital.fr/search?q={q_plus}"
    if 'challenges' in s:
        return f"https://www.challenges.fr/search?q={q_plus}"
    if 'monde' in s:
        return f"https://www.lemonde.fr/recherche/?keywords={q_plus}"
    if 'ft' in s or 'financial times' in s:
        return f"https://www.ft.com/search?q={q_plus}"
    if 'reuters' in s:
        return f"https://www.reuters.com/search/news?blob={q_plus}"
    if 'bloomberg' in s:
        return f"https://www.bloomberg.com/search?query={q_plus}"
    if 'wsj' in s:
        return f"https://www.wsj.com/search?query={q_plus}"
    if 'politico' in s:
        return f"https://www.politico.eu/search/{q}/"
    return f"https://www.google.com/search?q={urllib.parse.quote(source+' '+titre)}"

def enrich_urls(briefing):
    """Add search URL to every article."""
    for key in ["marches", "entreprises", "ma", "macro", "politique"]:
        section = briefing.get(key)
        if not section:
            continue
        articles = section.get("articles", []) if isinstance(section, dict) else []
        for a in articles:
            titre = a.get("titre", "")
            source = a.get("source", "")
            if titre and source:
                a["url"] = make_link(source, titre)
    return briefing

def parse_json(text):
    print(f"  Réponse: {len(text)} chars")
    s = text.find('{')
    if s == -1:
        raise ValueError(f"Pas de JSON: {repr(text[:300])}")
    raw = text[s:]
    e = raw.rfind('}')
    if e != -1:
        raw = raw[:e+1]
    try:
        return json.loads(raw)
    except json.JSONDecodeError as err:
        print(f"  Réparation JSON ({err})...")
        raw = re.sub(r',(\s*[}\]])', r'\1', raw)
        raw += ']' * max(0, raw.count('[') - raw.count(']'))
        raw += '}' * max(0, raw.count('{') - raw.count('}'))
        return json.loads(raw)

def generate_briefing(today, now, weekday):
    prompt = f"""Tu es un journaliste économique et financier senior, basé à Paris. Date : {today}, {now}.

Génère un briefing économique et financier matinal COMPLET, réaliste et de haute qualité pour un professionnel M&A dans un cabinet d'expertise comptable français.

CONTEXTE ÉCONOMIQUE ACTUEL (avril 2026) :
- Conflit au Moyen-Orient (Iran/USA) : impact sur pétrole, taux, risk-off
- BCE en mode attentiste face à l'inflation énergétique
- OAT 10 ans autour de 3,7%, spread OAT/Bund ~70pb
- EUR/USD autour de 1,17 (dollar faible structurellement)
- CAC 40 volatil autour de 7800-8200 pts
- Marché M&A France actif : cessions non-core, LBO mid-market
- Réforme budgétaire française sous tension (déficit ~5% PIB)
- Géopolitique : guerre commerciale USA/Europe atténuée mais surveillance

SOURCES À UTILISER (sources françaises prioritaires) :
Les Echos, Le Figaro, L'Agefi, La Tribune, BFM Business, Capital, Challenges, Le Monde Economie, AFP — puis Reuters, Bloomberg, FT, Politico Europe.

RÈGLES :
- Titres réalistes et précis (comme de vrais titres de journaux)
- Résumés informatifs de 2 phrases avec chiffres si pertinents
- 8 articles par section, sources variées, priorité aux médias français
- Contenu M&A : mentionner valorisations, multiples, secteurs actifs
- Contenu macro : chiffres précis (taux, indices, variations)
- NE PAS mettre de champ "url" dans les articles (il sera ajouté automatiquement)

Réponds UNIQUEMENT avec ce JSON valide, sans texte avant/après, sans backticks :

{{
  "timestamp": "{now} le {today}",
  "alerte": null,
  "synthese": {{
    "resume": "4-5 phrases couvrant l'essentiel : marchés, macro, M&A, géopolitique. Ton professionnel, chiffres inclus.",
    "points": [
      {{"titre": "Marchés : [sujet précis]", "detail": "explication avec chiffres, angle M&A/finance"}},
      {{"titre": "Macro : [sujet précis]", "detail": "explication avec chiffres, angle M&A/finance"}},
      {{"titre": "M&A : [sujet précis]", "detail": "explication avec chiffres, impact sur deals"}},
      {{"titre": "Politique/Géo : [sujet précis]", "detail": "explication avec impact économique concret"}}
    ]
  }},
  "marches": {{
    "metrics": [
      {{"label": "CAC 40", "value": "XXXX", "change": "+X.X%", "dir": "up"}},
      {{"label": "Eurostoxx 50", "value": "XXXX", "change": "+X.X%", "dir": "up"}},
      {{"label": "OAT 10 ans", "value": "X.XX%", "change": "+X pb", "dir": "up"}},
      {{"label": "Bund 10 ans", "value": "X.XX%", "change": "+X pb", "dir": "up"}},
      {{"label": "Spread OAT/Bund", "value": "XX pb", "change": "+X pb", "dir": "flat"}},
      {{"label": "EUR/USD", "value": "X.XXXX", "change": "+X.X%", "dir": "flat"}},
      {{"label": "Brent", "value": "XXX $", "change": "+X.X%", "dir": "up"}},
      {{"label": "S&P 500", "value": "XXXX", "change": "+X.X%", "dir": "up"}}
    ],
    "articles": [
      {{"source": "Les Echos", "heure": "07h30", "titre": "Titre précis article marchés", "resume": "Résumé 2 phrases avec chiffres."}},
      {{"source": "Le Figaro", "heure": "07h45", "titre": "Titre précis article marchés", "resume": "Résumé 2 phrases avec chiffres."}},
      {{"source": "Reuters", "heure": "06h15", "titre": "Titre précis article marchés", "resume": "Résumé 2 phrases avec chiffres."}},
      {{"source": "Bloomberg", "heure": "06h30", "titre": "Titre précis article marchés", "resume": "Résumé 2 phrases avec chiffres."}},
      {{"source": "BFM Business", "heure": "07h00", "titre": "Titre précis article marchés", "resume": "Résumé 2 phrases avec chiffres."}},
      {{"source": "Les Echos", "heure": "08h00", "titre": "Second article marchés Les Echos", "resume": "Résumé 2 phrases avec chiffres."}},
      {{"source": "La Tribune", "heure": "07h15", "titre": "Titre précis article marchés", "resume": "Résumé 2 phrases avec chiffres."}},
      {{"source": "FT", "heure": "06h00", "titre": "Titre précis article marchés FT", "resume": "Résumé 2 phrases avec chiffres."}}
    ]
  }},
  "entreprises": {{
    "articles": [
      {{"source": "Les Echos", "heure": "07h00", "titre": "Résultats/stratégie entreprise française précise", "resume": "Résumé 2 phrases avec chiffres."}},
      {{"source": "Le Figaro", "heure": "07h20", "titre": "Résultats/stratégie entreprise française précise", "resume": "Résumé 2 phrases avec chiffres."}},
      {{"source": "L'Agefi", "heure": "07h30", "titre": "Titre article entreprise L'Agefi", "resume": "Résumé 2 phrases avec chiffres."}},
      {{"source": "Reuters", "heure": "06h45", "titre": "Titre article entreprise Reuters", "resume": "Résumé 2 phrases avec chiffres."}},
      {{"source": "La Tribune", "heure": "07h10", "titre": "Titre article entreprise La Tribune", "resume": "Résumé 2 phrases avec chiffres."}},
      {{"source": "Les Echos", "heure": "08h15", "titre": "Second article entreprise Les Echos", "resume": "Résumé 2 phrases avec chiffres."}},
      {{"source": "Bloomberg", "heure": "06h30", "titre": "Titre article entreprise Bloomberg", "resume": "Résumé 2 phrases avec chiffres."}},
      {{"source": "Le Figaro", "heure": "08h30", "titre": "Second article entreprise Le Figaro", "resume": "Résumé 2 phrases avec chiffres."}}
    ]
  }},
  "ma": {{
    "articles": [
      {{"source": "Les Echos", "heure": "07h00", "titre": "Deal M&A précis avec société et montant", "resume": "Résumé deal : acquéreur, cible, montant, multiple."}},
      {{"source": "Le Figaro", "heure": "07h20", "titre": "Deal M&A précis avec société et montant", "resume": "Résumé deal : acquéreur, cible, montant, multiple."}},
      {{"source": "L'Agefi", "heure": "07h30", "titre": "Deal M&A ou LBO L'Agefi", "resume": "Résumé deal : acquéreur, cible, montant, multiple."}},
      {{"source": "Reuters", "heure": "06h00", "titre": "Deal M&A international Reuters", "resume": "Résumé deal : acquéreur, cible, montant, multiple."}},
      {{"source": "Bloomberg", "heure": "06h30", "titre": "Deal M&A ou PE Bloomberg", "resume": "Résumé deal : acquéreur, cible, montant, multiple."}},
      {{"source": "Les Echos", "heure": "08h00", "titre": "Second article M&A Les Echos", "resume": "Résumé deal : acquéreur, cible, montant, multiple."}},
      {{"source": "La Tribune", "heure": "07h15", "titre": "Deal M&A La Tribune", "resume": "Résumé deal : acquéreur, cible, montant, multiple."}},
      {{"source": "FT", "heure": "06h00", "titre": "Deal M&A européen FT", "resume": "Résumé deal : acquéreur, cible, montant, multiple."}}
    ]
  }},
  "macro": {{
    "articles": [
      {{"source": "Les Echos", "heure": "07h00", "titre": "Indicateur macro France ou zone euro précis", "resume": "Résumé 2 phrases avec chiffres et comparaison."}},
      {{"source": "Le Figaro", "heure": "07h15", "titre": "Indicateur macro ou décision BCE/Fed précis", "resume": "Résumé 2 phrases avec chiffres et comparaison."}},
      {{"source": "Reuters", "heure": "06h30", "titre": "Indicateur macro Reuters", "resume": "Résumé 2 phrases avec chiffres et comparaison."}},
      {{"source": "FT", "heure": "06h00", "titre": "Analyse macro FT Europe ou USA", "resume": "Résumé 2 phrases avec chiffres et comparaison."}},
      {{"source": "La Tribune", "heure": "07h10", "titre": "Conjoncture France La Tribune", "resume": "Résumé 2 phrases avec chiffres et comparaison."}},
      {{"source": "Les Echos", "heure": "08h00", "titre": "Second article macro Les Echos", "resume": "Résumé 2 phrases avec chiffres et comparaison."}},
      {{"source": "Bloomberg", "heure": "06h30", "titre": "Macro Bloomberg zone euro ou Fed", "resume": "Résumé 2 phrases avec chiffres et comparaison."}},
      {{"source": "Politico", "heure": "07h00", "titre": "Politique économique EU Politico", "resume": "Résumé 2 phrases avec chiffres et comparaison."}}
    ]
  }},
  "politique": {{
    "articles": [
      {{"source": "Les Echos", "heure": "07h00", "titre": "Politique économique française précise", "resume": "Résumé 2 phrases avec impact concret."}},
      {{"source": "Le Figaro", "heure": "07h15", "titre": "Politique ou géopolitique avec impact éco", "resume": "Résumé 2 phrases avec impact concret."}},
      {{"source": "AFP", "heure": "06h00", "titre": "Dépêche AFP politique ou géopolitique", "resume": "Résumé 2 phrases avec impact concret."}},
      {{"source": "Politico", "heure": "07h00", "titre": "Politique UE ou géopolitique Politico", "resume": "Résumé 2 phrases avec impact concret."}},
      {{"source": "FT", "heure": "06h00", "titre": "Géopolitique FT avec impact économique", "resume": "Résumé 2 phrases avec impact concret."}},
      {{"source": "Reuters", "heure": "06h30", "titre": "Géopolitique Reuters", "resume": "Résumé 2 phrases avec impact concret."}},
      {{"source": "Les Echos", "heure": "08h00", "titre": "Second article politique Les Echos", "resume": "Résumé 2 phrases avec impact concret."}},
      {{"source": "La Tribune", "heure": "07h15", "titre": "Politique économique La Tribune", "resume": "Résumé 2 phrases avec impact concret."}}
    ]
  }}
}}"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=6000,
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
    weekday = now.weekday()

    print(f"Génération — {today} {time_str}")

    briefing = generate_briefing(today, time_str, weekday)
    print(f"  Sections: {list(briefing.keys())}")

    # Vérification sections
    required = ["synthese", "marches", "entreprises", "ma", "macro", "politique"]
    for s in required:
        if s not in briefing:
            print(f"  MANQUANT: {s} — ajout section vide")
            briefing[s] = {"articles": []} if s != "synthese" else {"resume": "", "points": []}

    # Ajout des URLs de recherche
    briefing = enrich_urls(briefing)

    # Stats
    for key in ["marches", "entreprises", "ma", "macro", "politique"]:
        n = len(briefing.get(key, {}).get("articles", []))
        print(f"  {key}: {n} articles")

    with open("briefing.json", "w", encoding="utf-8") as f:
        json.dump(briefing, f, ensure_ascii=False, indent=2)

    print(f"OK — {len(json.dumps(briefing))} chars")

if __name__ == "__main__":
    main()
