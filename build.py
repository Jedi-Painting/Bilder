#!/usr/bin/env python3
"""Erzeugt aus dem Ordner bilder/ eine statische Galerie in _site/.

Aufruf:  python3 build.py [--bilder ORDNER] [--ziel ORDNER]

Dateinamen steuern Titel und Reihenfolge:
    2026-11-15_Herbstwald_im_Nebel.jpg  ->  Titel "Herbstwald im Nebel", November 2026
    2025_Stillleben.png                 ->  Titel "Stillleben", 2025
    Skizze.jpg                          ->  Titel "Skizze", Datum aus Git bzw. Dateidatum

Optional liegt neben dem Bild eine gleichnamige .txt-Datei:
    1. Zeile = Titel (ersetzt den Titel aus dem Dateinamen)
    weitere Zeilen = Beschreibung (Technik, Format, ...)
"""

import argparse
import datetime as dt
import html
import re
import shutil
import subprocess
import unicodedata
from pathlib import Path

from PIL import Image, ImageOps

BASIS = Path(__file__).resolve().parent
ENDUNGEN = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}
VORSCHAU_KANTE = 800    # px, längste Kante der Vorschaubilder
GROSS_KANTE = 2400      # px, längste Kante der Großansicht
MONATE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
          "August", "September", "Oktober", "November", "Dezember"]
NAMENSMUSTER = re.compile(r"^(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?[_\s-]+(.+)$")


def slug(text):
    text = text.replace("ß", "ss").replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
    text = text.replace("Ä", "Ae").replace("Ö", "Oe").replace("Ü", "Ue")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower() or "bild"


def git_datum(datei):
    """Datum, an dem die Datei ins Repo kam (None, falls unbekannt)."""
    try:
        aus = subprocess.run(
            ["git", "log", "--diff-filter=A", "--follow", "--format=%aI", "--", datei.name],
            cwd=datei.parent, capture_output=True, text=True, timeout=20).stdout.split()
        return dt.datetime.fromisoformat(aus[-1]).date() if aus else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def lies_bild(datei):
    """Liefert Titel, Beschreibung, Sortierschlüssel und Datumsanzeige."""
    treffer = NAMENSMUSTER.match(datei.stem)
    if treffer:
        jahr, monat, tag, rest = treffer.groups()
        monat_i = int(monat) if monat and 1 <= int(monat) <= 12 else None
        sortierung = f"{jahr}-{monat_i or 0:02d}-{int(tag or 0):02d}"
        anzeige = f"{MONATE[monat_i - 1]} {jahr}" if monat_i else jahr
    else:
        rest = datei.stem
        datum = git_datum(datei) or dt.date.fromtimestamp(datei.stat().st_mtime)
        sortierung = datum.isoformat()
        anzeige = f"{MONATE[datum.month - 1]} {datum.year}"
    titel = re.sub(r"[_\s]+", " ", rest).strip()

    beschreibung = ""
    text = datei.with_suffix(".txt")
    if text.exists():
        zeilen = text.read_text(encoding="utf-8-sig").strip().splitlines()
        if zeilen:
            titel = zeilen[0].strip() or titel
            beschreibung = " ".join(z.strip() for z in zeilen[1:] if z.strip())
    return titel, beschreibung, sortierung, anzeige


def speichere(bild, kante, ziel):
    kopie = bild.copy()
    kopie.thumbnail((kante, kante), Image.LANCZOS)
    # Neu kodieren ohne EXIF: keine GPS-/Kameradaten in der Galerie
    kopie.save(ziel, "JPEG", quality=86, optimize=True, progressive=True)
    return kopie.size


def baue(bilder_ordner, ziel):
    if ziel.exists():
        shutil.rmtree(ziel)
    (ziel / "vorschau").mkdir(parents=True)
    (ziel / "gross").mkdir()

    dateien = sorted(d for d in bilder_ordner.rglob("*")
                     if d.is_file() and d.suffix.lower() in ENDUNGEN) if bilder_ordner.is_dir() else []
    eintraege, vergeben = [], set()
    for datei in dateien:
        try:
            with Image.open(datei) as roh:
                bild = ImageOps.exif_transpose(roh)
                if bild.mode in ("RGBA", "LA", "P"):
                    bild = bild.convert("RGBA")
                    grund = Image.new("RGB", bild.size, "white")
                    grund.paste(bild, mask=bild.split()[-1])
                    bild = grund
                else:
                    bild = bild.convert("RGB")
                name = basis = slug(datei.stem)
                zaehler = 2
                while name in vergeben:
                    name, zaehler = f"{basis}-{zaehler}", zaehler + 1
                vergeben.add(name)
                breite, hoehe = speichere(bild, VORSCHAU_KANTE, ziel / "vorschau" / f"{name}.jpg")
                speichere(bild, GROSS_KANTE, ziel / "gross" / f"{name}.jpg")
        except OSError as fehler:
            print(f"  übersprungen: {datei.name} ({fehler})")
            continue
        titel, beschreibung, sortierung, anzeige = lies_bild(datei)
        eintraege.append(dict(name=name, titel=titel, beschreibung=beschreibung,
                              sortierung=sortierung, anzeige=anzeige, b=breite, h=hoehe))
        print(f"  {datei.name}  ->  {titel} ({anzeige})")

    eintraege.sort(key=lambda e: (e["sortierung"], e["name"]), reverse=True)
    (ziel / "index.html").write_text(seite(eintraege), encoding="utf-8")
    (ziel / "info.html").write_text(INFOSEITE, encoding="utf-8")
    (ziel / ".nojekyll").touch()
    print(f"{len(eintraege)} Bilder -> {ziel / 'index.html'}")


def seite(eintraege):
    e = html.escape
    kacheln = []
    for i, x in enumerate(eintraege):
        unterzeile = " · ".join(t for t in (x["anzeige"], x["beschreibung"]) if t)
        lazy = "" if i < 6 else ' loading="lazy"'
        kacheln.append(
            f'<figure style="--r:{x["b"] / x["h"]:.4f}">'
            f'<a href="gross/{x["name"]}.jpg" data-titel="{e(x["titel"])}" data-info="{e(unterzeile)}">'
            f'<img src="vorschau/{x["name"]}.jpg" width="{x["b"]}" height="{x["h"]}" '
            f'alt="{e(x["titel"])}"{lazy}></a>'
            f'<figcaption><strong>{e(x["titel"])}</strong><span>{e(unterzeile)}</span></figcaption>'
            f'</figure>')
    inhalt = ('<main class="galerie">' + "\n".join(kacheln) + "</main>") if kacheln else \
        '<p class="leer">Noch keine Bilder – die ersten Gemälde folgen bald.</p>'
    anzahl = f"{len(eintraege)} Gemälde" if eintraege else ""
    return VORLAGE.replace("{{INHALT}}", inhalt).replace("{{ANZAHL}}", anzahl)


VORLAGE = """<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Jedi Painting – Bilder</title>
<meta name="description" content="Gemäldegalerie von Jedi Painting">
<style>
:root{--grund:#f3f0ea;--text:#22201d;--leise:#6f6a62;--linie:#d9d4ca;--rahmen:#fff}
@media (prefers-color-scheme:dark){:root{--grund:#151413;--text:#ece8e1;--leise:#9a948a;--linie:#33302c;--rahmen:#201e1c}}
*{box-sizing:border-box}
body{margin:0;background:var(--grund);color:var(--text);font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
header{padding:56px 24px 28px;text-align:center}
h1{margin:0;font:400 clamp(2rem,6vw,3.4rem)/1.1 Georgia,"Times New Roman",serif;letter-spacing:.01em}
header p{margin:10px 0 0;color:var(--leise);font-size:.85rem;letter-spacing:.14em;text-transform:uppercase}
.galerie{display:flex;flex-wrap:wrap;gap:28px 20px;max-width:1500px;margin:0 auto;padding:16px 24px 64px}
.galerie::after{content:"";flex-grow:1000000}
figure{margin:0;min-width:0;flex-grow:calc(var(--r)*100);flex-basis:calc(var(--r)*300px)}
figure a{display:block;background:var(--rahmen);padding:8px;box-shadow:0 1px 2px rgba(0,0,0,.08),0 8px 24px rgba(0,0,0,.10);transition:transform .2s,box-shadow .2s}
figure a:hover,figure a:focus-visible{transform:translateY(-3px);box-shadow:0 2px 4px rgba(0,0,0,.1),0 14px 34px rgba(0,0,0,.18)}
figure img{display:block;width:100%;height:auto;aspect-ratio:var(--r);object-fit:cover}
figcaption{padding:10px 2px 0;font-size:.9rem}
figcaption strong{display:block;font:400 1.05rem/1.3 Georgia,serif}
figcaption span{color:var(--leise);font-size:.8rem}
.leer{text-align:center;color:var(--leise);padding:60px 24px}
footer{border-top:1px solid var(--linie);padding:24px;text-align:center;color:var(--leise);font-size:.8rem}
footer a{color:inherit}
dialog{border:0;padding:0;margin:0;width:100vw;height:100dvh;max-width:none;max-height:none;background:rgba(12,11,10,.96);color:#eee}
dialog::backdrop{background:#000}
dialog[open]{display:flex;flex-direction:column;align-items:center;justify-content:center}
dialog img{max-width:calc(100vw - 24px);max-height:calc(100dvh - 96px);object-fit:contain;box-shadow:0 10px 60px rgba(0,0,0,.6)}
dialog p{margin:0;padding:12px 60px 0;text-align:center;font-size:.9rem;min-height:48px}
dialog p b{font:400 1.05rem Georgia,serif;margin-right:.6em}
dialog p span{color:#aaa}
dialog button{position:absolute;border:0;background:none;color:#ddd;font-size:2rem;line-height:1;width:56px;height:56px;cursor:pointer;opacity:.75}
dialog button:hover{opacity:1}
#zu{top:6px;right:8px}#vor{right:4px;top:50%;margin-top:-28px}#rueck{left:4px;top:50%;margin-top:-28px}
@media (max-width:600px){.galerie{padding:8px 14px 48px;gap:22px 14px}figure{flex-basis:calc(var(--r)*220px)}header{padding-top:36px}}
</style>
</head>
<body>
<header>
<h1>Jedi Painting</h1>
<p>{{ANZAHL}}</p>
</header>
{{INHALT}}
<footer>© Andreas Jedek · Alle Rechte an den Bildern vorbehalten · <a href="info.html">Über diese Seite &amp; Datenschutz</a></footer>
<dialog id="lupe" aria-label="Großansicht">
<button id="zu" aria-label="Schließen">×</button>
<button id="rueck" aria-label="Vorheriges Bild">‹</button>
<button id="vor" aria-label="Nächstes Bild">›</button>
<img alt="">
<p><b></b><span></span></p>
</dialog>
<script>
(function(){
  var links=[].slice.call(document.querySelectorAll('.galerie a')),lupe=document.getElementById('lupe');
  if(!links.length||!lupe.showModal)return;
  var bild=lupe.querySelector('img'),titel=lupe.querySelector('b'),info=lupe.querySelector('span'),nr=0;
  function zeige(i){
    nr=(i+links.length)%links.length;var a=links[nr];
    bild.src=a.href;bild.alt=a.dataset.titel;titel.textContent=a.dataset.titel;info.textContent=a.dataset.info;
    var n=links[(nr+1)%links.length];new Image().src=n.href;
  }
  links.forEach(function(a,i){a.addEventListener('click',function(e){e.preventDefault();zeige(i);lupe.showModal();});});
  document.getElementById('zu').onclick=function(){lupe.close();};
  document.getElementById('vor').onclick=function(){zeige(nr+1);};
  document.getElementById('rueck').onclick=function(){zeige(nr-1);};
  lupe.addEventListener('click',function(e){if(e.target===lupe)lupe.close();});
  lupe.addEventListener('keydown',function(e){if(e.key==='ArrowRight')zeige(nr+1);if(e.key==='ArrowLeft')zeige(nr-1);});
  var x0=null;
  lupe.addEventListener('touchstart',function(e){x0=e.touches[0].clientX;},{passive:true});
  lupe.addEventListener('touchend',function(e){if(x0===null)return;var d=e.changedTouches[0].clientX-x0;x0=null;if(Math.abs(d)>50)zeige(nr+(d<0?1:-1));});
  lupe.addEventListener('close',function(){links[nr].focus();});
})();
</script>
</body>
</html>
"""

INFOSEITE = """<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Über diese Seite – Jedi Painting</title>
<style>
:root{--grund:#f3f0ea;--text:#22201d;--leise:#6f6a62}
@media (prefers-color-scheme:dark){:root{--grund:#151413;--text:#ece8e1;--leise:#9a948a}}
body{margin:0;background:var(--grund);color:var(--text);font:16px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:680px;margin:0 auto;padding:48px 24px 64px}
h1{font:400 2.2rem/1.2 Georgia,serif;margin:0 0 24px}
h2{font:400 1.35rem/1.3 Georgia,serif;margin:36px 0 8px}
a{color:inherit}
.zurueck{color:var(--leise);font-size:.9rem}
</style>
</head>
<body>
<main>
<p class="zurueck"><a href="./">← Zur Galerie</a></p>
<h1>Über diese Seite</h1>
<p>Diese Galerie ist ein rein privates, nicht kommerzielles Hobby-Projekt von <strong>Andreas Jedek</strong>.
Die gezeigten Gemälde stehen nicht zum Verkauf; die Seite enthält keine Werbung.</p>
<p>Kontakt: über das GitHub-Profil <a href="https://github.com/Jedi-Painting">github.com/Jedi-Painting</a>.</p>

<h2>Urheberrecht</h2>
<p>Alle Gemälde und Fotos auf dieser Seite stammen von Andreas Jedek und sind urheberrechtlich geschützt.
Eine Verwendung, Vervielfältigung oder Bearbeitung ist nur mit vorheriger Zustimmung erlaubt.</p>

<h2>Datenschutz</h2>
<p>Verantwortlich für diese Seite ist Andreas Jedek (Kontakt siehe oben).</p>
<p>Diese Seite verwendet keine Cookies, keine Analyse- oder Tracking-Dienste und lädt keine Inhalte von Drittanbietern.
Es gibt keine Formulare; es werden von mir keine personenbezogenen Daten erhoben oder gespeichert.</p>
<p>Die Seite wird über GitHub Pages bereitgestellt, einen Dienst der GitHub, Inc. (USA).
Beim Aufruf verarbeitet GitHub technisch notwendige Zugriffsdaten, insbesondere die IP-Adresse,
um die Seite auszuliefern und den Dienst abzusichern. Rechtsgrundlage ist das berechtigte Interesse
an einer sicheren und zuverlässigen Bereitstellung (Art. 6 Abs. 1 lit. f DSGVO). Auf diese Daten habe ich keinen Zugriff.
Näheres steht in der
<a href="https://docs.github.com/de/site-policy/privacy-policies/github-general-privacy-statement">Datenschutzerklärung von GitHub</a>.</p>
<p>Nach der DSGVO haben Sie das Recht auf Auskunft, Berichtigung, Löschung, Einschränkung der Verarbeitung und Widerspruch
sowie das Recht, sich bei einer Datenschutz-Aufsichtsbehörde zu beschweren.</p>
</main>
</body>
</html>
"""

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Baut die Bildergalerie.")
    p.add_argument("--bilder", type=Path, default=BASIS / "bilder", help="Ordner mit den Originalbildern")
    p.add_argument("--ziel", type=Path, default=BASIS / "_site", help="Ausgabeordner (wird neu angelegt)")
    a = p.parse_args()
    baue(a.bilder.resolve(), a.ziel.resolve())
