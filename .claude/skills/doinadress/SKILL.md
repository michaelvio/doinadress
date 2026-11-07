---
name: doinadress
description: Lucrul pe DoinaDress (D:\CladeCode\DoinaDress), cabina de probă 3D (three.js + MakeHuman) cu avatare cu fețe din poze. Acoperă fețele modelelor (aliniere după ochi, înlocuire cu poze generice), reconstruirea tuturor variantelor (HTML, PWA, Flutter și Kotlin; familie/magazin × realist/simplu), capturile din docs/img, ghidul md/docx și publicarea pe GitHub. Folosește-l când utilizatorul cere să schimbe fețele sau modelele, să refacă build-urile sau APK-urile, să refacă ghidul sau capturile, ori să urce DoinaDress pe GitHub.
---

# DoinaDress

Proiectul are mai multe variante, construite toate din aceeași sursă: `src/cabina3d.template.html` + `modele/*.json` + `fete/*.jpg` + `catalog/`. Ghidul complet pentru utilizator este `Ghid_utilizare_DoinaDress.md`. Citește capitolul relevant înainte să modifici ceva.

## Variante

| Public | Corp | Ce se produce | Comanda |
|---|---|---|---|
| familie | realist (MakeHuman, `build_cache/mh.pack`) | `DoinaDress_Cabina3D.html`, `web/`, `mobile/assets/web/` | `python src/build.py` |
| familie | simplu | `DoinaDress_Cabina3D_simplu.html` (se face odată cu build.py) | idem |
| magazin (manechine, `modele/baza_clienti.json`, fără fețe) | ambele | `magazin/…html`, `magazin/web/` | `python src/build.py --clienti` |
| Flutter APK familie | realist | `DoinaDress.apk` | build.py, apoi `cd mobile && flutter build apk --release`, copiezi `build/app/outputs/flutter-apk/app-release.apk` |
| Flutter APK | simplu | `DoinaDress_Simplu.apk` / `magazin/DoinaDress_Magazin_Simplu.apk` | `python src/build_simplu.py [--clienti]` |
| Flutter APK magazin | realist | `magazin/DoinaDress_Magazin.apk` | `python src/build_magazin.py` |
| Kotlin APK, toate 4 | — | `kotlin_apk/*.apk` | `python src/build_kotlin.py` |

Fețele apar doar la **familie**. După o schimbare de fețe sau modele, rulează `scripts/build_all.sh`. Scriptul construiește secvențial tot ce conține familia. Comenzile nu se pot rula în paralel: `build_kotlin`, `build_simplu` și `build_magazin` rescriu `web/` și `mobile/assets/web/`, iar la final pun la loc resursele familiei. APK-ul Flutter complet se construiește ultimul. Durează aproximativ 10–15 minute, deci rulează-l în fundal.

## Fețele

- `src/fete.py` aliniază fiecare față după ochi. Ochii ajung orizontali, la distanța 1024/2,6 px, cu mijlocul la (50 %, 40 %), iar rezultatul este `fete/<id>.jpg` de 1024×1280. Tot scriptul calculează și `skin`.
- Sursa fiecărui model este în `modele/baza_modele.json`: `"sursa": {"foto": ..., "ochi": [[xS,yS],[xD,yD]]}`. Refaci toate fețele cu `python src/fete.py toate`.
- Coordonatele ochilor le citești de pe grilă: rulezi `python src/fete.py grila FOTO X0 Y0 X1 Y1` și te uiți la PNG. Pupila se citește cu o precizie de ~5 px. Fețele StyleGAN/FFHQ de 1024 px au ochii aproape de (385, 482) și (637, 482).
- După ce refaci fețele, verifică-le pe o foaie de contact: ochii trebuie să cadă pe linia de 40 %. Pune `faceAdj.bright` la 1 pentru poze noi.

### Poze generice (fără persoane reale)

Repo-ul este **public**. Nu pune niciodată în repo poze ale familiei utilizatorului: originalele stau în `D:\CladeCode\DoinaDress_poze_familie\`, în afara repo-ului. Fețele generice sunt în `poze_generice/`, iar sursele și licențele în `poze_generice/SURSE.md`.

Ca să găsești alte fețe generice:
- Folosește Wikimedia Commons, categoria `AI-generated realistic faces`, cu fișierele „Man 2”, „Woman 1”, „Boy 1” etc. (domeniu public sau CC0). Trimite un User-Agent descriptiv și fă cereri rare, cu pauze de 5–15 s, pentru că upload.wikimedia.org răspunde 429.
- thispersondoesnotexist.com blochează clienții automați. Nu încerca să ocolești blocarea.
- Evită imaginile CC BY-SA sau cele cu adnotări pe față.

## Capturile din documentație

Capturile din `docs/img` se fac în doi pași, după build:

```
node scripts/shots.mjs <dir_temp> [nume...]         # Chrome headless prin CDP (swiftshader), ~2 min
python scripts/compose_docs_img.py <dir_temp>       # copiază în docs/img, decupează familia.png, compune fete_3d.png
```

- `shots.mjs` folosește link-urile directe ale aplicației: `#<id>`, `#<id>-fata`, `#panou`.
- Cu `[nume...]` refaci doar unele capturi, de exemplu `catalog` sau `fata` pentru toate prim-planurile.
- Catalogul are nevoie de ~25 s ca să randeze pozele produselor. A doua linie rămâne goală, la fel ca în originalul din ghid.
- Uită-te la fiecare imagine înainte de `compose_docs_img.py`.

`magazin.png` arată manechinele și nu trebuie refăcută la schimbarea fețelor.

## Ghidul docx

Generează-l din md cu pandoc. Fișierul `reference.docx` global dă A4 cu margini Narrow.

```
pandoc Ghid_utilizare_DoinaDress.md -o Ghid_utilizare_DoinaDress.docx --resource-path=.
```

Verifică apoi `<w:pgSz w:w="11906" w:h="16838">` și `pgMar` = 720 în `word/document.xml`.

## Git și GitHub

- Repo-ul public este `michaelvio/doinadress`. Istoricul vechi, care conține poze de familie, este în repo-ul privat `michaelvio/doinadress-privat`. Nu-l face public.
- Git nu are identitate globală. Ia numele și emailul din ultimul commit (`git log -1 --format='%an|%ae'`) și dă-le cu `git -c user.name=… -c user.email=… commit`.
- Rămân în afara git: `*.apk`, `DoinaDress_Cabina3D.html` și `magazin/DoinaDress_Magazin.html` (~20 MB), plus `build_cache/`, `assets_src/` și `kotlin_apk/`.
- Înainte de push, rulează `git ls-files | grep -iE '\.(jpe?g|png)$'` și verifică că nu apare nicio poză reală.

## Particularități pe Windows

- Pune `PYTHONIOENCODING=utf-8` pe orice script Python care afișează diacritice. Consola folosește cp1252, iar scriptul se oprește înainte să salveze.
- `python -I` nu vede PIL, care e instalat în site-packages al utilizatorului.
- OpenCV 5 nu mai are `CascadeClassifier`. Pentru ochi folosește grila.
