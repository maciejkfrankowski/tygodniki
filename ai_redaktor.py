 #!/usr/bin/env python3
"""AI‑redaktor: bierzemy zbalansowaną próbkę z każdego źródła (3 nagłówki/źródło)."""
import json, glob, os, urllib.request, xml.etree.ElementTree as ET
from datetime import date
import re

BASE_URL = os.environ.get('AI_BASE_URL', 'https://openrouter.ai/api/v1')
MODEL = os.environ.get('AI_MODEL', 'qwen/qwen-plus')
UA = {'User-Agent': 'tygodnik-ai/1.0'}

# Słowa kluczowe do wykluczenia (nawigacja, menu, byliny)
BLACKLIST = [
    'przejdź do', 'menu', 'zaloguj', 'rejestracja', 'kontakt', 'o nas', 'cookies',
    'ustawienia', 'stopka', 'nawigacja', 'treści głównej', 'prenumerata', 'pakiet',
    'firmy i instytucje', 'czytelnicy indywidualni', 'moje zakupy', 'zrealizuj voucher',
    'preferencje treści', 'program —', 'wiadomości z', 'news from', 'gorzów wielkopolski',
    'lidzbark warmiński', 'nowe miasto lubawskie', 'z życia', 'kongres przyszłości',
    'wybierz prenumeratę', 'dzisiejsza gazeta', 'kobieta - serwis', 'reportaże multimedialne',
    'tylko na', 'tematy dnia', 'regionalny system ostrzegania', 'pszoek', 'praca grodzisk',
    'pogoda, ostrzeżenia', 'jakość powietrza', 'apteki w', 'informacje z warmii'
]

def fetch(u):
    with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=15) as r:
        return r.read()

def rss_items(url, n=3):
    """Próbuje parsować RSS/XML; jeśli failuje, wyciąga nagłówki z HTML. BIERZE MAX 3."""
    try:
        content = fetch(url)
        root = ET.fromstring(content)
        out = []
        for it in (root.findall('.//item') or root.findall('.//{http://www.w3.org/2005/Atom}entry'))[:n]:
            t = (it.findtext('title') or '').strip(); l = (it.findtext('link') or '').strip()
            if t and l: out.append((t, l))
        if out: return out
    except Exception as e:
        print(f'  RSS/XML fail dla {url}: {e}')
    
    # Fallback: scraping HTML z filtrami
    try:
        content = fetch(url).decode('utf-8', errors='ignore')
        titles = re.findall(r'<(?:h[23]|a)[^>]*>([^<]{15,120})</(?:h[23]|a)>', content, re.I)
        out = []
        seen = set()
        for t in titles:
            t = t.strip()
            # Filtr 1: długość (min 20 znaków - wyklucza nazwiska, tagi)
            if len(t) < 25 or len(t) > 120: continue
            # Filtr 2: blacklist
            t_lower = t.lower()
            if any(bl in t_lower for bl in BLACKLIST): continue
            # Filtr 3: brak duplikatów
            if t in seen: continue
            # Filtr 4: wyklucz prawdopodobne nazwiska autorów (brak czasowników, krótkie)
            if len(t.split()) < 4: continue
            seen.add(t)
            out.append((t, url))
            if len(out) >= n: break
        print(f'  HTML scraping: znaleziono {len(out)} sensownych nagłówków')
        return out
    except Exception as e:
        print(f'  HTML scraping fail dla {url}: {e}')
        return []

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

SYSTEM = ('Jesteś redaktorem lokalnego tygodnika w Polsce. Piszesz KONKRETNE, sąsiedzkie leady do 7 zdań. '
          'Styl: rzeczowy, apolityczny, "co się dzieje na ulicy obok". Zawsze podajesz klikalne źródło. '
          'Nie wymyślaj faktów — korzystaj wyłącznie z podanych nagłówków i linków. '
          'Priorytet: newsy lokalne (dzielnica/miasto), nie ogólnopolskie. '
          'ZAKAZ HALUCYNACJI: NIE WYMYŚLAJ nazw firm, sklepów, ulic, dat, godzin, liczb których nie ma w nagłówku. '
          'Jeśli nagłówek mówi "serwisy rowerowe" bez nazw, pisz "lokalne serwisy rowerowe", nie wymyślaj nazw. '
          'Jeśli nagłówek mówi "cukiernie" bez nazw, pisz "cukiernie w dzielnicy", nie wymyślaj nazw.')

def draft_for(cfg):
    print(f'Pobieranie nagłówków dla: {cfg["miasto"]}')
    nagl = []
    for z in sum(cfg['zrodla'].values(), []):
        if z.get('typ') == 'rss' and z.get('url'):
            items = rss_items(z['url'], n=3)  # BIERZE MAX 3 z każdego źródła
            for t, l in items:
                nagl.append((z['nazwa'], t, l))
            if items:
                print(f'  {z["nazwa"]}: {len(items)} nagłówków')
    
    if not nagl:
        print(f'  Brak nagłówków dla {cfg["miasto"]}')
        return None
    
    lista = '\n'.join('- [%s] %s — %s' % (n, t, l) for n, t, l in nagl[:15])
    print('=== NAGŁÓWKI DLA AI ===')
    print(lista)
    print('=== KONIEC NAGŁÓWKÓW ===')
    
    prompt = ('Miasto: %s. Data: %s.\nNagłówki z lokalnych źródeł:\n%s\n\n'
              'Zwróć WYŁĄCZNIE poniższy fragment HTML:\n'
              '<!-- SEKCJA:2 -->\n'
              '<div class="card"><span class="tag">Temat tygodnia</span><h3>TYTUŁ</h3>'
              '<p>LEAD do 7 zdań (styl sąsiedzki, konkretny: co się dzieje, gdzie, kiedy, kto)</p>'
              '<p class="meta">Źródło: <a href="LINK" target="_blank">NAZWA</a></p></div>\n'
              '+ dokładnie 2 kolejne karty newsów (span class="tag blue" oraz "green")\n'
              'Priorytet: newsy lokalne (dzielnica/miasto), nie ogólnopolskie. '
              'Unikaj newsów typu "preferencje treści", "vouchery", "prenumerata".\n'
              '<!-- /SEKCJA:2 -->' % (cfg['miasto'], date.today(), lista))
    out = ai_complete(prompt, SYSTEM)
    if out and '<!-- SEKCJA:2 -->' in out and '<!-- /SEKCJA:2 -->' in out:
        print(f'  ✔ Szkic AI wygenerowany dla {cfg["miasto"]}')
        return out
    print(f'  ✗ AI nie zwrócił poprawnego HTML dla {cfg["miasto"]}')
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
            print('✔ zapisano:', folder + '/tresc_ai.html')
        else:
            print('– brak szkicu dla:', cfg['plik'])

if __name__ == '__main__': main()
