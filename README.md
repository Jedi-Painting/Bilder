# Bilder

Gemäldegalerie von Jedi Painting: <https://jedi-painting.github.io/Bilder/>

## Neues Bild veröffentlichen

1. Foto des Gemäldes in den Ordner [`bilder/`](bilder/) legen – auf github.com über **Add file → Upload files** oder lokal mit `git add`, `git commit`, `git push`.
2. Fertig. GitHub baut die Galerie automatisch neu; nach etwa einer Minute ist das Bild online.

## Dateinamen

| Dateiname | Titel | Datum |
|---|---|---|
| `2026-11-15_Herbstwald_im_Nebel.jpg` | Herbstwald im Nebel | November 2026 |
| `2025_Stillleben.png` | Stillleben | 2025 |
| `Skizze.jpg` | Skizze | Tag des Hochladens |

- Neueste Bilder stehen oben.
- Optional eine gleichnamige `.txt` daneben: 1. Zeile = Titel, weitere Zeilen = Beschreibung (z. B. „Öl auf Leinwand, 60 × 80 cm“).
- Die Galerie zeigt verkleinerte Kopien ohne EXIF-Daten. Die Originale in `bilder/` sind in einem öffentlichen Repo aber ebenfalls abrufbar.

## Lokal ansehen

```bash
pip install -r requirements.txt
python3 build.py
```

Danach `_site/index.html` im Browser öffnen.

## Einmalige Einrichtung

Im Repo unter **Settings → Pages → Build and deployment → Source** den Eintrag **GitHub Actions** wählen.
