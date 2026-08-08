 #!/usr/bin/env python3
"""Tygodnik v2.3: config-default + configi miast (nadpisania) + dziedziczenie "base"
(np. dzielnice Warszawy dziedziczą miasta/warszawa-base.json) + tresc.html (markery SEKCJA:n).
Równoległe RSS/API z cache (OK 6h / błąd 24h), filtr świeżości 14 dni, pamięć publikacji 90 dni."""
import json, re, glob, time, urllib.request, xml.etree.ElementTree as ET
from datetime import date, timedelta
from concurrent.futures import ThreadPoolExecutor
from email.utils import parsedate_to_datetime

UA = {'User-Agent': 'tygodnik-bot/2.3'}
CACHE_F = '.cache_feeds.json'
HIST_F = 'historia.json'
TTL_OK, TTL_FAIL = 6 * 3600, 24 * 3600
MAX_AGE = timedelta(days=14)
RETENCJA = timedelta(days=90)

CACHE_D = {}
try: CACHE_D = json.load(open(CACHE_F, encoding='utf-8'))
except Exception: pass
HIST = {}
try: HIST = json.load(open(HIST_F, encoding='utf-8'))
except Exception: pass

def fetch_raw(u):
    with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=15) as r:
        return r.read()

def item_date(it):
    s = (it.findtext('pubDate') or it.findtext('{http://www.w3.org/2005/Atom}updated') or '')
    try: return parsedate_to_datetime(s).date().isoformat()
    except Exception:
        try: return date.fromisoformat(s[:10]).isoformat()
        except Exception: return None

def rss_parse(txt, n=8):
    root = ET.fromstring(txt); out = []
    for it in (root.findall('.//item') or root.findall('.//{http://www.w3.org/2005/Atom}entry'))[:n]:
        t = (it.findtext('title') or '').strip(); l = (it.findtext('link') or '').strip()
        if t and l: out.append((t, l, item_date(it)))
    return out

def get_rss(url):
    e = CACHE_D.get(url); now = time.time()
    if e and now - e['ts'] < (TTL_OK if e.get('ok') else TTL_FAIL): return e.get('items', [])
    try: items, ok = rss_parse(fetch_raw(url)), True
    except Exception: items, ok = [], False
    CACHE_D[url] = {'ts': now, 'ok': ok, 'items': items}; return items

def get_events(api, a, b):
    key = api + '|' + str(a)
    e = CACHE_D.get(key); now = time.time()
    if e and now - e['ts'] < (TTL_OK if e.get('ok') else TTL_FAIL): return e.get('items', [])
    try:
        d = json.loads(fetch_raw(api + '?start_date=%s&end_date=%s' % (a, b)))
        items, ok = [(x.get('title', ''), x.get('url', '')) for x in d.get('events', [])], True
    except Exception: items, ok = [], False
    CACHE_D[key] = {'ts': now, 'ok': ok, 'items': items}; return items

def get_imgw():
    e = CACHE_D.get('imgw'); now = time.time()
    if e and now - e['ts'] < TTL_OK: return e.get('n')
    try:
        d = json.loads(fetch_raw('https://meteo.imgw.pl/api/data/SiteWarningsCollection'))
        n = len(d) if isinstance(d, list) else 0; ok = True
    except Exception: n, ok = None, False
    CACHE_D['imgw'] = {'ts': now, 'ok': ok, 'n': n}; return n

def weekend():
    d = date.today(); s = d + timedelta((5 - d.weekday()) % 7); return s, s + timedelta(1)
SAT, SUN = weekend(); TYDZIEN = date.today().isocalendar()[1]; IMGW = get_imgw()

# ---------- configi: default + base + miasto ----------
DEFAULT = json.load(open('config-default.json', encoding='utf-8'))

def load_city(cp):
    """Wczytuje config miasta; jeśli ma klucz "base", dokleja źródła z miasta/<base>-base.json."""
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

def merge_cfg(city):
    cfg = json.loads(json.dumps(DEFAULT))
    for k, v in city.items():
        if k == 'sekcje_override':
            for sid, ov in v.items():
                for s in cfg['sekcje']:
                    if s['id'] == int(sid): s.update(ov)
        elif k == 'reklamy_override': cfg['reklamy'].update(v)
        else: cfg[k] = v
    return cfg

def sources_all(cfg):
    out = []
    for v in cfg['zrodla'].values(): out += v
    return out
def find_src(cfg, frag):
    for z in sources_all(cfg):
        if frag.lower() in z['nazwa'].lower(): return z
    return None

def extract_blocks(path):
    try: txt = open(path, encoding='utf-8').read()
    except FileNotFoundError: return {}
    return {int(m.group(1)): m.group(2).strip()
            for m in re.finditer(r'(?s)<!--\s*SEKCJA:(\d+)\s*-->(.*?)<!--\s*/SEKCJA:\d+\s*-->', txt)}

# ---------- boksy systemowe i rotacje ----------
def box_klub(cfg):
    s14 = next((s for s in cfg['sekcje'] if s['typ'] == 'crowdfunding'), {})
    lk = s14.get('linki', {})
    l = ' '.join('<a href="%s" target="_blank">%s</a>' % (u, n) for n, u in lk.items() if u) or '<span class="meta">linki wkrótce</span>'
    return '<div class="ad"><h4>☕ Klub Czytelnika</h4><p>Ten tygodnik istnieje dzięki sąsiadom. Wesprzyj: %s</p></div>' % l
def box_apel():
    return '<div class="ad"><h4>📣 Apel o treści</h4><p>Widzisz akcję, remont, sąsiedzką inicjatywę? Napisz — to Twoja gazeta.</p></div>'
def box_referral():
    return '<div class="ad"><h4>🤝 Podziel się z sąsiadem</h4><p>Wyślij swój link polecający. 3 polecenia = darmowa kawa w lokalnej kawiarni.</p></div>'
def slot_reklama(cfg, tier):
    r = cfg['reklamy']
    if tier == 'tier1' and r['tier1'].get('sponsor'):
        return '<div class="ad t1"><p><b>Sponsorem wydania jest %s</b></p></div>' % r['tier1']['sponsor']
    if tier == 'tier2' and r['tier2'].get('aktywna'):
        return '<div class="ad"><h4>Reklama</h4><p>Tu stoi Ad Story sponsora.</p></div>'
    return box_klub(cfg) if TYDZIEN % 2 == 0 else (box_apel() if TYDZIEN % 4 in (1, 3) else box_referral())

# ---------- renderery 15 sekcji ----------
def sec_header(s, cfg, blk, auto):
    w = ['📅 %s–%s' % (SAT, SUN),
         '🌦️ IMGW: %s' % (('ostrzeżenia: %d' % IMGW) if IMGW else 'brak ostrzeżeń'),
         '<a href="https://powietrze.gios.gov.pl/" target="_blank">🌫️ powietrze</a>']
    sponsor = slot_reklama(cfg, 'tier1') if cfg['reklamy']['tier1'].get('sponsor') else ''
    return ('<header><p class="kicker">%s · wydanie weekendowe</p><h1>%s</h1><p class="widgets">%s</p>%s'
            '<p class="toc"><a href="index.html">← wszystkie miasta</a></p></header>'
            % (cfg['tytul'], ' · '.join(w), cfg['miasto'], sponsor))

def sec_flash(s, cfg, blk, auto):
    out = '<p class="sect">Puls tygodnia</p><h2>Ultra‑Local Flash</h2>'
    out += blk or '<div class="card"><h3>Temat tygodnia</h3><p>Uzupełnij w tresc.html (SEKCJA:2).</p></div>'
    li = ''.join('<li><a href="%s" target="_blank">%s</a> <span class="meta">· %s</span></li>' % (l, t, n) for n, l, t in auto['rss'][:4])
    return out + '<div class="card"><h3>W mijającym tygodniu</h3><ul class="src">%s</ul></div>' % li

def sec_weekend(s, cfg, blk, auto):
    out = '<p class="sect">Weekendownik</p><h2>Lokalny czas wolny</h2>' + (blk or '')
    ev = ''.join('<li>🎭 <a href="%s" target="_blank">%s</a></li>' % (l, t) for t, l in auto['events'])
    if ev: out += '<div class="card"><h3>Auto‑kalendarz (API)</h3><ul class="src">%s</ul></div>' % ev
    if s.get('polecajka_biblioteki') and 'polecajka' not in (blk or ''):
        b = find_src(cfg, 'biblioteka')
        out += '<div class="card"><span class="tag green">Polecajka z biblioteki</span><p>Miejsce na cotygodniową rekomendację (po umowie z biblioteką). %s</p></div>' % ('<a href="%s" target="_blank">↗</a>' % b['url'] if b else '')
    if s.get('wypady_Warszawa'):
        out += '<div class="card"><span class="tag blue">Wypad do Warszawy</span><p>30–40 min koleją: muzea, premiery, koncerty — dobierz redakcyjnie.</p></div>'
    return out

def sec_kanapa(s, cfg, blk, auto):
    return '<p class="sect">Płynność · lifestyle</p><h2>Kultura z kanapy (ogólnopolska)</h2>' + (blk or '<div class="card"><p>🎬 streaming · 📚 książka/audiobook · 🎧 podcast · 🎼 muzyka — wybór redakcji/AI. Sekcja rozszerza się, gdy lokalnych treści jest mało.</p></div>')

def sec_bazar(s, cfg, blk, auto):
    mod = {'praca': '💼 Praca (PUP/oferty)', 'nieruchomosci': '🏠 Nieruchomości — ceny',
           'licytacje': '⚖️ Licytacje komornicze', 'c2c': '🛋️ Ogłoszenia C2C', 'radar_cen': '🛒 Sąsiedzki radar cenowy'}
    tiles = ''.join('<div class="box"><h4>%s</h4><p>%s</p></div>' % (mod.get(m, m), 'dane: AI‑agent (etap 2)' if m in ('c2c', 'radar_cen') else 'uzupełnij w tresc.html lub podłącz agenta') for m in s.get('moduly', []))
    return '<p class="sect">Lokalny bazar i rynek</p><h2>Twoja kieszeń</h2>' + (blk or '<div class="grid">%s</div>' % tiles)

def sec_wspolnota(s, cfg, blk, auto):
    out = '<p class="sect">Echo sąsiedzkie</p><h2>Życie wspólnoty</h2>' + (blk or '')
    a = find_src(cfg, 'apteki')
    if a: out += '<div class="card"><h4>💊 Apteki dyżurne</h4><p><a href="%s" target="_blank">Harmonogram ↗</a></p></div>' % a['url']
    p = find_src(cfg, 'parafie')
    if p: out += '<div class="card"><h4>⛪ Ogłoszenia parafialne</h4><p><a href="%s" target="_blank">↗</a> + tablice (offline).</p></div>' % p['url']
    return out + slot_reklama(cfg, 'tier2')

def sec_edukacja(s, cfg, blk, auto):
    out = '<p class="sect">Edukacja blisko domu</p><h2>Edukacja, kursy, szkolenia</h2>'
    if blk: return out + blk
    chips = ''.join('<li><a href="%s" target="_blank">%s</a></li>' % (z['url'], z['nazwa']) for z in cfg['zrodla'].get('edukacja', []) if z.get('url'))
    return out + '<div class="card"><p>Fallback: lokalne → miejskie → regionalne → ogólnopolskie → online (≤15 min).</p><ul class="src">%s</ul></div>' % chips

def sec_sport(s, cfg, blk, auto):
    out = '<p class="sect">Dynamiczny</p><h2>Lokalny sport i zdrowie</h2>' + (blk or '<div class="card"><p>Wyniki A‑klasy → kluby regionalne; zdrowie: biegi, badania, joga. Brak danych → poradnik ogólnopolski.</p></div>')
    chips = ''.join('<li><a href="%s" target="_blank">%s</a></li>' % (z['url'], z['nazwa']) for z in cfg['zrodla'].get('kultura', []) if any(x in z['nazwa'].lower() for x in ('osir', 'sport', 'pogoń', 'azs', 'stomil')))
    return out + '<div class="card"><ul class="src">%s</ul></div>' % chips

def sec_uslugi(s, cfg, blk, auto):
    sold = cfg['reklamy']['tier3'].get('kafle', [])
    tiles = ''.join('<div class="box"><h4>%s</h4><p>%s</p></div>' % (k.get('nazwa', ''), k.get('opis', '')) for k in sold)
    for i in range(len(sold), s.get('kafle', 6)):
        tiles += box_referral() if i % 2 == 0 else box_klub(cfg)
    return '<p class="sect">Lokalny rynek usług</p><h2>Reklama 3 — rynek usług</h2><div class="grid">%s</div>' % tiles

def sec_magazyn(s, cfg, blk, auto):
    return '<p class="sect">Centralny magazyn</p><h2>Dodatek ogólnopolski</h2>' + (blk or '<div class="card"><p>🌍 3 apolityczne ciekawostki z wpływem na lokalność · 🧩 quiz + Lokalny Paszport · 🔗 linkowisko.</p></div>')

def sec_nostalgia(s, cfg, blk, auto):
    out = '<p class="sect">Tożsamość i pamięć</p><h2>Tożsamość i pamięć</h2>'
    if blk: return out + blk
    z = next((z for z in cfg['zrodla'].get('media_archiwum', []) if 'cyfrowa' in z['nazwa'].lower() or 'wmbc' in (z.get('url') or '')), None)
    return out + '<div class="card"><p>📜 Mikro‑ciekawostka historyczna lub „Kiedyś i Dziś". %s</p></div>' % ('<a href="%s" target="_blank">Archiwalia ↗</a>' % z['url'] if z else '')

def sec_apel(s, cfg, blk, auto): return '<p class="sect">Aktywizacja</p>' + box_apel()
def sec_referral(s, cfg, blk, auto): return '<p class="sect">System poleceń</p>' + box_referral()
def sec_klub(s, cfg, blk, auto): return '<p class="sect">Crowdfunding</p>' + box_klub(cfg)
def sec_footer(s, cfg, blk, auto):
    return '<footer>%s · linki: wypis · RODO · preferencje · %s · numery budowane automatycznie w czwartki.</footer>' % (s.get('firma', ''), cfg['tytul'])

RENDER = {1: sec_header, 2: sec_flash, 3: sec_weekend, 4: sec_kanapa, 5: sec_bazar, 6: sec_wspolnota,
          7: sec_edukacja, 8: sec_sport, 9: sec_uslugi, 10: sec_magazyn, 11: sec_nostalgia,
          12: sec_apel, 13: sec_referral, 14: sec_klub, 15: sec_footer}

# ---------- miasta + równoległe pobieranie ----------
city_files = sorted(glob.glob('miasta/*/config.json'))
cities = [merge_cfg(load_city(cp)) for cp in city_files]

urls, apis = set(), set()
for cfg in cities:
    for z in sources_all(cfg):
        if z.get('typ') == 'rss' and z.get('url'): urls.add(z['url'])
        if z.get('api'): apis.add(z['api'])

with ThreadPoolExecutor(max_workers=10) as ex:
    RSS = dict(zip(sorted(urls), ex.map(get_rss, sorted(urls))))
    EV = dict(zip(sorted(apis), ex.map(lambda a: get_events(a, SAT, SUN), sorted(apis))))
json.dump(CACHE_D, open(CACHE_F, 'w', encoding='utf-8'), ensure_ascii=False)

def build_auto(cfg):
    rss = []
    for z in sources_all(cfg):
        if z.get('typ') == 'rss' and z.get('url'):
            for t, l, d in RSS.get(z['url'], []):
                if l in HIST: continue                                              # już było
                if d and (date.today() - date.fromisoformat(d)) > MAX_AGE: continue # przeterminowane
                rss.append((z['nazwa'], l, t))
    ev = []
    for z in sources_all(cfg):
        if z.get('api'): ev += EV.get(z['api'], [])
    return {'rss': rss, 'events': ev}

SZABLON = open('szablon.html', encoding='utf-8').read()
miasta = []
for cp, cfg in zip(city_files, cities):
    folder = cp[:-len('/config.json')]
    blocks = extract_blocks(folder + '/tresc.html')
    auto = build_auto(cfg)
    parts = []
    for s in cfg['sekcje']:
        h = RENDER.get(s['id'])(s, cfg, blocks.get(s['id']), auto)
        if h: parts.append('<section>%s</section>' % h)
    html = SZABLON
    for k, v in {'{{TYTUL}}': cfg['tytul'], '{{MIASTO}}': cfg['miasto'],
                 '{{TYDZIEN}}': '%s – %s' % (SAT, SUN), '{{SEKCJE}}': '\n'.join(parts)}.items():
        html = html.replace(k, v)
    open(cfg['plik'], 'w', encoding='utf-8').write(html)
    for n, l, t in auto['rss']:
        HIST[l] = {'miasto': cfg['miasto'], 'ts': str(date.today()), 'tytul': t}
    miasta.append(cfg); print('✔', cfg['plik'])

cutoff = str(date.today() - RETENCJA)
HIST = {k: v for k, v in HIST.items() if v.get('ts', '9999-99-99') >= cutoff}
json.dump(HIST, open(HIST_F, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

try:
    idx = open('index.html', encoding='utf-8').read()
    lista = '\n'.join('<li><a href="%s">%s</a> · %s</li>' % (c['plik'], c['tytul'], c['miasto']) for c in miasta)
    idx = re.sub(r'(?s)<!-- MIASTA:START -->.*?<!-- MIASTA:KONIEC -->',
                 lambda m: '<!-- MIASTA:START -->\n' + lista + '\n<!-- MIASTA:KONIEC -->', idx)
    open('index.html', 'w', encoding='utf-8').write(idx)
except FileNotFoundError: pass
print('OK', SAT, SUN)
