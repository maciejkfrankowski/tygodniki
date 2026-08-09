#!/usr/bin/env python3
"""AI‑redaktor (ścieżka A): czyta nagłówki RSS miasta i generuje szkic tresc_ai.html (SEKCJA:2).
Człowiek ma pierwszeństwo: bloki z tresc.html nadpisują AI w buildzie.
Wymaga sekretu AI_API_KEY (endpoint OpenAI‑compatible, domyślnie DashScope/Qwen)."""
import json, glob, os, urllib.request, xml.etree.ElementTree as ET
from datetime import date

BASE_URL = os.environ.get('AI_BASE_URL', 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1')
MODEL = os.environ.get('AI_MODEL', 'qwen-plus')
UA = {'User-Agent': 'tygodnik-ai/1.0'}

def fetch(u):
    with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=15) as r:
        return r.read()

def rss_items(url, n=6):
    try:
        root = ET.fromstring(fetch(url)); out = []
        for it in (root.findall('.//item') or root.findall('.//{http://www.w3.org/2005/Atom}entry'))[:n]:
            t = (it.findtext('title') or '').strip(); l = (it.findtext('link') or '').strip()
            if t and l: out.append((t, l))
        return out
    except Exception: return []

def ai_complete(prompt, system):
    key = os.environ.get('AI_API_KEY')
    if not key: return None
    body = json.dumps({'model': MODEL, 'temperature': 0.7,
        'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': prompt}]}).encode()
    req = urllib.request.Request(BASE_URL + '/chat/completions', data=body,
        headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=90) as r: d = json.load(r)
        return d['choices'][0]['message']['content']
    except Exception as e:
        print('AI błąd:', e); return None

def load_city(cp):
    city = json.load(open(cp, encoding='utf-8'))
    base_name = city.pop('base', None)
    if base_name:
        base = json.load(open('miasta/%s-base.json' % base_name, encoding='utf-8'))
        z = {}
        for kat, items in base.get('zrodla', {}).items(): z[kat] = list(items)
        for kat, items in city.get('zrodla', {}).items():
            z.setdefault(kat, []); z[kat] += items
        city['zrodla'] = z
    return city

SYSTEM = ('Jesteś redaktorem lokalnego tygodnika w Polsce. Piszesz rzeczowe, apolityczne, sąsiedzkie '
          'leady do 7 zdań. Zawsze podajesz klikalne źródło. Nie wymyślaj faktów — korzystaj wyłącznie '
          'z podanych nagłówków i linków.')

def draft_for(cfg):
    nagl = []
    for z in sum(cfg['zrodla'].values(), []):
        if z.get('typ') == 'rss' and z.get('url'):
            for t, l in rss_items(z['url']): nagl.append((z['nazwa'], t, l))
    if not nagl: return None
    lista = '\n'.join('- [%s] %s — %s' % (n, t, l) for n, t, l in nagl[:12])
    prompt = ('Miasto: %s. Data: %s.\nNagłówki z lokalnych źródeł:\n%s\n\n'
              'Zwróć WYŁĄCZNIE poniższy fragment HTML:\n'
              '<!-- SEKCJA:2 -->\n'
              '<div class="card"><span class="tag">Temat tygodnia</span><h3>TYTUŁ</h3>'
              '<p>LEAD do 7 zdań</p><p class="meta">Źródło: <a href="LINK" target="_blank">NAZWA</a></p></div>\n'
              '+ dokładnie 2 kolejne karty newsów (span class="tag blue" oraz "green")\n'
              '<!-- /SEKCJA:2 -->' % (cfg['miasto'], date.today(), lista))
    out = ai_complete(prompt, SYSTEM)
    if out and '<!-- SEKCJA:2 -->' in out and '<!-- /SEKCJA:2 -->' in out: return out
    return None

def main():
    if not os.environ.get('AI_API_KEY'):
        print('Brak AI_API_KEY — pomijam szkice AI.'); return
    for cp in sorted(glob.glob('miasta/*/config.json')):
        cfg = load_city(cp)
        folder = cp[:-len('/config.json')]
        out = draft_for(cfg)
        if out:
            open(folder + '/tresc_ai.html', 'w', encoding='utf-8').write(out)
            print('✔ szkic AI:', cfg['plik'])
        else:
            print('– brak danych/szkicu:', cfg['plik'])

if __name__ == '__main__': main()
