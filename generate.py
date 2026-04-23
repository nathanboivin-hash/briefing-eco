import anthropic
import json
import re
import urllib.parse
from datetime import datetime

client = anthropic.Anthropic()

def search_url(source, titre):
    q = urllib.parse.quote_plus(titre)
    s = source.lower()
    if 'echo' in s:       return f"https://www.lesechos.fr/recherche?keywords={q}"
    if 'figaro' in s:     return f"https://recherche.lefigaro.fr/recherche/?q={q}"
    if 'tribune' in s:    return f"https://www.latribune.fr/recherche/?q={q}"
    if 'agefi' in s:      return f"https://www.agefi.fr/search?q={q}"
    if 'bfm' in s:        return f"https://www.bfmtv.com/recherche/?q={q}"
    if 'capital' in s:    return f"https://www.capital.fr/search?q={q}"
    if 'challenges' in s: return f"https://www.challenges.fr/search?q={q}"
    if 'boursorama' in s: return f"https://www.boursorama.com/bourse/actualites/recherche/?q={q}"
    if 'reuters' in s:    return f"https://fr.reuters.com/search/news?blob={q}"
    if 'bloomberg' in s:  return f"https://www.bloomberg.com/search?query={q}"
    if 'ft' in s:         return f"https://www.ft.com/search?q={q}"
    if 'politico' in s:   return f"https://www.politico.eu/search/{urllib.parse.quote(titre)}/"
    if 'monde' in s:      return f"https://www.lemonde.fr/recherche/?keywords={q}"
    return f"https://www.google.com/search?q={urllib.parse.quote(source+' '+titre)}"

def add_links(sections, keys):
    for key in keys:
        for a in sections.get(key, {}).get("articles", []):
            a["url"] = search_url(a.get("source",""), a.get("titre",""))

def parse_json(text):
    s = text.find('{')
    if s == -1: raise ValueError("No JSON")
    raw = text[s:]
    e = raw.rfind('}')
    if e != -1: raw = raw[:e+1]
    try:
        return json.loads(raw)
    except:
        raw = re.sub(r',(\s*[}\]])', r'\1', raw)
        raw += ']' * max(0, raw.count('[') - raw.count(']'))
        raw += '}' * max(0, raw.count('{') - raw.count('}'))
        return json.loads(raw)

def call(prompt):
    r = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}]
    )
    return "".join(b.text for b in r.content if hasattr(b, "text"))

CONTEXT = """Contexte avril 2026 : conflit Iran/USA impact pétrole+taux, BCE attentiste, OAT ~3.7%, spread OAT/Bund ~70pb, EUR/USD ~1.17, CAC ~8000, marché M&A France actif (cessions non-core, LBO mid-market), déficit FR ~5% PIB."""

ART = lambda src, titre: f'{{"source":"{src}","heure":"","titre":"{titre}","resume":"résumé 2 phrases précis avec chiffres."}}'

def call1(today, now):
    prompt = f"""Analyste M&A Paris. Date: {today} {now}. {CONTEXT}
Génère JSON briefing matinal. Sources françaises: Les Echos, Le Figaro, La Tribune, L'Agefi, BFM Business, Reuters, Bloomberg, FT.
Titres réalistes précis avec noms d'entreprises/chiffres. JSON uniquement sans backticks:
{{"timestamp":"{now} le {today}","alerte":null,
"synthese":{{"resume":"4 phrases synthèse marchés+macro+M&A+géopo avec chiffres","points":[
{{"titre":"Marchés: sujet précis","detail":"explication chiffres angle M&A"}},
{{"titre":"Macro: sujet précis","detail":"explication chiffres angle M&A"}},
{{"titre":"M&A: sujet précis","detail":"deal/tendance avec montant"}},
{{"titre":"Politique: sujet précis","detail":"impact économique concret"}}]}},
"marches":{{"metrics":[
{{"label":"CAC 40","value":"XXXX","change":"+X.X%","dir":"up"}},
{{"label":"Eurostoxx 50","value":"XXXX","change":"+X.X%","dir":"up"}},
{{"label":"OAT 10 ans","value":"X.XX%","change":"+X pb","dir":"up"}},
{{"label":"Bund 10 ans","value":"X.XX%","change":"+X pb","dir":"up"}},
{{"label":"Spread OAT/Bund","value":"XX pb","change":"+X pb","dir":"flat"}},
{{"label":"EUR/USD","value":"X.XXXX","change":"+X.X%","dir":"flat"}},
{{"label":"Brent","value":"XXX $","change":"+X.X%","dir":"up"}},
{{"label":"S&P 500","value":"XXXX","change":"+X.X%","dir":"up"}}],
"articles":[
{ART("Les Echos","titre marché précis")},
{ART("Le Figaro","titre marché précis")},
{ART("Reuters","titre marché précis")},
{ART("Bloomberg","titre marché précis")},
{ART("BFM Business","titre marché précis")},
{ART("La Tribune","titre marché précis")}]}},
"entreprises":{{"articles":[
{ART("Les Echos","résultats/stratégie entreprise française précise")},
{ART("Le Figaro","résultats/stratégie entreprise française précise")},
{ART("L'Agefi","titre entreprise L'Agefi")},
{ART("Reuters","titre entreprise Reuters")},
{ART("La Tribune","titre entreprise La Tribune")},
{ART("Bloomberg","titre entreprise Bloomberg")}]}},
"ma":{{"articles":[
{ART("Les Echos","deal M&A avec société et montant")},
{ART("Le Figaro","deal M&A avec société et montant")},
{ART("L'Agefi","deal M&A ou LBO L'Agefi")},
{ART("Reuters","deal M&A international")},
{ART("Bloomberg","deal PE ou M&A Bloomberg")},
{ART("La Tribune","deal M&A La Tribune")}]}}}}"""
    return parse_json(call(prompt))

def call2(today, now):
    prompt = f"""Analyste M&A Paris. Date: {today} {now}. {CONTEXT}
Génère JSON avec sections macro et politique. Sources: Les Echos, Le Figaro, FT, Reuters, Politico, La Tribune, BFM Business, L'Agefi.
Titres précis avec chiffres. JSON uniquement sans backticks:
{{"macro":{{"articles":[
{ART("Les Echos","indicateur macro France précis avec chiffre")},
{ART("Le Figaro","décision BCE ou Fed avec taux")},
{ART("FT","analyse macro zone euro ou US")},
{ART("Reuters","indicateur macro Reuters")},
{ART("La Tribune","conjoncture France La Tribune")},
{ART("Politico","politique économique EU Politico")},
{ART("Bloomberg","macro Bloomberg zone euro")},
{ART("Les Echos","second article macro Les Echos")}]}},
"politique":{{"articles":[
{ART("Les Echos","politique économique française précise")},
{ART("Le Figaro","politique ou géopolitique impact éco")},
{ART("FT","géopolitique FT impact économique")},
{ART("Reuters","géopolitique Reuters")},
{ART("Politico","politique UE Politico")},
{ART("La Tribune","politique économique La Tribune")},
{ART("BFM Business","politique économique BFM")},
{ART("Le Figaro","second article politique Le Figaro")}]}}}}"""
    return parse_json(call(prompt))

def main():
    now = datetime.now()
    days = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]
    months = ["janvier","février","mars","avril","mai","juin","juillet","août","septembre","octobre","novembre","décembre"]
    today = f"{days[now.weekday()]} {now.day} {months[now.month-1]} {now.year}"
    ts = now.strftime("%Hh%M")

    print(f"Génération — {today} {ts}")

    print("→ Appel 1 (synthèse+marchés+entreprises+M&A)...")
    p1 = call1(today, ts)
    print("→ Appel 2 (macro+politique)...")
    p2 = call2(today, ts)

    briefing = {**p1, **p2}

    # Vérification sections
    for key in ["synthese","marches","entreprises","ma","macro","politique"]:
        if key not in briefing:
            print(f"  MANQUANT: {key}")
            briefing[key] = {"articles":[]} if key != "synthese" else {"resume":"","points":[]}

    # Ajout URLs
    add_links(briefing, ["marches","entreprises","ma","macro","politique"])

    # Stats
    for k in ["marches","entreprises","ma","macro","politique"]:
        n = len(briefing.get(k,{}).get("articles",[]))
        print(f"  {k}: {n} articles")

    with open("briefing.json","w",encoding="utf-8") as f:
        json.dump(briefing, f, ensure_ascii=False, indent=2)
    print(f"OK — {len(json.dumps(briefing))} chars")

if __name__ == "__main__":
    main()
