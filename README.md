# Tygodniki Lokalne — warsztat (v2.2)

Format  kuratorskie leady (do 7 zdań) + klikalne źródła + stałe rubryki,
15 sekcji układu weekendowego, rotacje reklam i fallbacki.

## Struktura
- `config-default.json` — wspólne: 15 sekcji, rotacje, fallback_chain (zmiana layoutu = 1 plik)
- `miasta/<miasto>/config.json` — spec miasta: nazwa, plik, `sekcje_override`, źródła (9 kategorii)
- `miasta/<miasto>/tresc.html` — cotygodniowa kuracja w markerach `<!-- SEKCJA:n --> … <!-- /SEKCJA:n -->`
- `miasta/<miasto>/img/` — ilustracje redakcyjne
- `szablon.html` — wspólny wygląd (CSS + placeholdery)
- `build_newsletter.py` — silnik: merge configów, równoległe RSS/API, cache, świeżość (14 dni),
  pamięć publikacji `historia.json` (90 dni), aktualizacja `index.html`
- `panel.html` — panel redakcyjny (statusy numerów, checklista, biblioteka źródeł)
- `olsztyn.html`, `grodzisk.html` — WYNIKI builda (nie edytuj ręcznie)

## Start (GitHub Pages + Actions)
1. Utwórz publiczne repo, wgraj folder.
2. Settings → Actions → General → Workflow permissions → „Read and write permissions”.
3. Settings → Pages → Deploy from branch → `main` / root.
4. Actions → „czwartkowy-build” → Run workflow. Od tej pory build sam co czwartek 07:00 PL.

## Cotygodniowy rytm
- czw 7:00 — bot odświeża sekcje auto (RSS/API/IMGW) z filtrami świeżości i bez powtórek,
- czw/pt — edytujesz `tresc.html` (ołówkiem w przeglądarce) → commit → Run workflow,
- pt — publikacja: strona / PDF (Ctrl+P) / social media.

## Nowe miasto
1. Skopiuj `miasta/grodzisk/` → `miasta/<nazwa>/`.
2. Uzupełnij `config.json` (miasto, tytuł, plik, źródła; sekcje dziedziczy z defaultu).
3. Wpisz kurację do `tresc.html` (albo zostaw puste — numer i tak wyjdzie w trybie „auto”).
Build wygeneruje `<plik>.html` i dopisze miasto do `index.html`.

## Dodawanie źródeł
W `config.json` miasta, w odpowiedniej kategorii `zrodla`, dopisz obiekt:
`{"nazwa","url","status":"ok|warn|todo","typ":"strona|rss|api|fb|offline|ai"[,"notatka"][,"api"]}`.
Martwe feedy nie wysypują buildu; `status` to etykieta redakcyjna.
