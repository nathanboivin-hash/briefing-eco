import anthropic
import json
import re
import time
import urllib.parse
from datetime import datetime

client = anthropic.Anthropic()

def call_with_search(prompt):
    messages = [{"role": "user", "content": prompt}]
    while True:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=3000,
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

def parse_json(text):
    s = text.find("{")
    if s == -1:
        raise ValueError("Pas de JSON")
    raw = text[s:]
    e = raw.rfind("}")
    if e != -1:
        raw = raw[:e+1]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raw = re.sub(r',\s*$', '', raw)
        raw += ']' * max(0, raw.count('[') - raw.count(']'))
        raw += '}' * max(0, raw.count('{') - raw.count('}'))
        return json.loads(raw)

def make_search_url(source, titre):
    q = urllib.parse.quote(titre)
    s = source.lower()
    if 'echo' in s:      return f"https://www.google.com/search?q=site%3Alesechos.fr+{q}"
    if 'figaro' in s:    return f"https://www.google.com/search?q=site%3Alefigaro.fr+{q}"
    if 'agefi' in s:     return f"https://www.google.com/search?q=site%3Aagefi.fr+{q}"
    if 'ft' in s:        return f"https://www.google.com/search?q=site%3Aft.com+{q}"
    if 'reuters' in s:   return f"https://www.google.com/search?q=site%3Areuters.com+{q}"
    if 'bloomberg' in s: return f"https://www.google.com/search?q=site%3Abloomberg.com+{q}"
    return f"https://www.google.com/search?q={urllib.parse.quote(source+' '+titre)}"

def fix_urls(articles):
    fixed = []
    for a in articles:
        url = str(a.get('url') or '')
        titre = a.get('titre', '')
        source = a.get('source', '')
        bad = (
            not url or
            url in ('null', 'None', '') or
            'URL-EXACTE' in url or
            'url-exacte' in url or
            url.count('/') < 3
        )
        if bad and titre:
            a['url'] = make_search_url(source, titre)
            a['is_search'] = True
        else:
            a['is_search'] = False
        fixed.append(a)
    return fixed

def generate_section(section, today, now):
    art5 = '[{"source":"Les Echos","heure":"","titre":"TITRE EXACT","resume":"2 phrases","url":"https://URL-EXACTE"},{"source":"Le Figaro","heure":"","titre":"TITRE EXACT","resume":"2 phrases","url":"https://URL-EXACTE"},{"source":"Reuters","heure":"","titre":"TITRE EXACT","resume":"2 phrases","url":"https://URL-EXACTE"},{"source":"Les Echos","heure":"","titre":"TITRE EXACT","resume":"2 phrases","url":"https://URL-EXACTE"},{"source":"Le Figaro","heure":"","titre":"TITRE EXACT","resume":"2 phrases","url":"https://URL-EXACTE"}]'

    if section == "synthese_marches":
        prompt = f"""Date : {today} {now}. Analyste financier senior.
Cherche sur le web les cours actuels (CAC40, OAT, EUR/USD, Brent) et 5 articles récents de lesechos.fr et lefigaro.fr.
JSON uniquement, sans backticks :
{{"timestamp":"{now} le {today}","alerte":null,"synthese":{{"resume":"3-4 phrases","points":[{{"titre":"...","detail":"..."}},{{"titre":"...","detail":"..."}},{{"titre":"...","detail":"..."}},{{"titre":"...","detail":"..."}}]}},"marches":{{"metrics":[{{"label":"CAC 40","value":"?","change":"?","dir":"up"}},{{"label":"Eurostoxx 50","value":"?","change":"?","dir":"up"}},{{"label":"OAT 10 ans","value":"?","change":"?","dir":"up"}},{{"label":"Bund 10 ans","value":"?","change":"?","dir":"up"}},{{"label":"Spread OAT/Bund","value":"?","change":"?","dir":"flat"}},{{"label":"EUR/USD","value":"?","change":"?","dir":"flat"}},{{"label":"Brent","value":"?","change":"?","dir":"up"}},{{"label":"S&P 500","value":"?","change":"?","dir":"up"}}],"articles":{art5}}}}}"""

    else:
        topics = {
            "entreprises": "resultats et strategie entreprises françaises/europeennes",
            "ma":          "fusions-acquisitions deals M&A LBO private equity France Europe",
            "macro":       "macroeconomie BCE inflation conjoncture France zone euro",
            "politique":   "politique economique française UE geopolitique economique"
        }
        prompt = f"""Date : {today} {now}. Analyste financier senior.
Cherche 5 articles récents de lesechos.fr et lefigaro.fr sur : {topics[section]}.
Utilise titres et URLs EXACTES trouvés sur le web.
JSON uniquement, sans backticks :
{{"articles":{art5}}}"""

    text = call_with_search(prompt)
    return parse_json(text)


def main():
    now = datetime.now()
    days = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]
    months = ["janvier","fevrier","mars","avril","mai","juin","juillet","aout","septembre","octobre","novembre","decembre"]
    today = f"{days[now.weekday()]} {now.day} {months[now.month-1]} {now.year}"
    time_str = now.strftime("%Hh%M")

    print(f"Generation — {today} {time_str}")
    briefing = {}

    print("-> Synthese + Marches...")
    try:
        sm = generate_section("synthese_marches", today, time_str)
        briefing["timestamp"] = sm.get("timestamp", f"{time_str} le {now.strftime('%d/%m/%Y')}")
        briefing["alerte"] = sm.get("alerte")
        briefing["synthese"] = sm.get("synthese", {})
        briefing["marches"] = sm.get("marches", {})
        if briefing["marches"].get("articles"):
            briefing["marches"]["articles"] = fix_urls(briefing["marches"]["articles"])
    except Exception as e:
        print(f"  Erreur: {e}")
        briefing.update({"timestamp": time_str, "alerte": None, "synthese": {}, "marches": {}})

    print("  Pause 30s...")
    time.sleep(30)

    for section in ["entreprises", "ma", "macro", "politique"]:
        print(f"-> {section}...")
        try:
            result = generate_section(section, today, time_str)
            if result.get("articles"):
                result["articles"] = fix_urls(result["articles"])
            briefing[section] = result
        except Exception as e:
            print(f"  Erreur {section}: {e}")
            briefing[section] = {"articles": []}
        print("  Pause 30s...")
        time.sleep(30)

    with open("briefing.json", "w", encoding="utf-8") as f:
        json.dump(briefing, f, ensure_ascii=False, indent=2)

    size = len(json.dumps(briefing))
    print(f"OK briefing.json ({size} chars)")

if __name__ == "__main__":
    main()
