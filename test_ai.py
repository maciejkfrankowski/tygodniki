import os, json, urllib.request

print('=== TEST AI ===')
print('AI_API_KEY:', 'TAK' if os.environ.get('AI_API_KEY') else 'BRAK')
print('AI_BASE_URL:', os.environ.get('AI_BASE_URL', '(domyślny)'))
print('AI_MODEL:', os.environ.get('AI_MODEL', '(domyślny)'))

key = os.environ.get('AI_API_KEY')
if not key:
    print('BRAK KLUCZA W ENV — sprawdź sekrety')
    raise SystemExit(1)

base = os.environ.get('AI_BASE_URL', 'https://openrouter.ai/api/v1')
model = os.environ.get('AI_MODEL', 'qwen/qwen-plus')

print(f'Próbuję wywołać: {base}/chat/completions z modelem {model}')

body = json.dumps({
    'model': model,
    'messages': [{'role': 'user', 'content': 'Odpowiedz jednym słowem: OK'}]
}).encode()

req = urllib.request.Request(
    base + '/chat/completions',
    data=body,
    headers={
        'Authorization': 'Bearer ' + key,
        'Content-Type': 'application/json'
    }
)

try:
    with urllib.request.urlopen(req, timeout=30) as r:
        resp = json.load(r)
        print('SUKCES:', resp['choices'][0]['message']['content'])
except urllib.error.HTTPError as e:
    print(f'BŁĄD HTTP {e.code}: {e.read().decode()}')
except Exception as e:
    print(f'BŁĄD: {e}')
