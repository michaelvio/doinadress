"""Construiește aplicația DoinaDress din șablon + modele/baza_modele.json + fete/*.jpg + src/vendor (three.js).

Catalogul magazinului: catalog/catalog.json (+ pozele din catalog/poze/), inclus în aplicație.

Versiunea pentru clienții magazinului (--clienti): modele/baza_clienti.json (manechine, fără poze)
-> magazin/DoinaDress_Magazin.html + magazin/web/; aplicația Android: python src/build_magazin.py

Rezultate:
  DoinaDress_Cabina3D.html   fișier unic, complet offline (dublu-click pe calculator)
  web/                       aceeași aplicație ca PWA: index.html + manifest + service worker + iconițe
                             (se pune pe un server HTTPS și se instalează pe Android / iPhone din browser)
  mobile/assets/web/         copia folosită de aplicația nativă Flutter (Android APK / iPhone)

Baza primește o revizie nouă (AAAALLZZOOMM) la fiecare build, astfel încât aplicația deschisă
preia automat modelele noi / actualizate (upgrade).
"""
import base64, datetime, json, mimetypes, pathlib, shutil, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

root = pathlib.Path(__file__).resolve().parent.parent
src = root / "src"
VENDOR = {   # specificator de import -> fișier local (three.js r160, MIT)
    "three": "three.module.min.js",
    "three/addons/controls/OrbitControls.js": "OrbitControls.js",
    "three/addons/environments/RoomEnvironment.js": "RoomEnvironment.js",
    "three/addons/geometries/RoundedBoxGeometry.js": "RoundedBoxGeometry.js",
}


def b64(path, mime):
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def load_db(name="baza_modele.json"):
    db = json.loads((root / "modele" / name).read_text(encoding="utf-8"))
    for m in db["modele"]:
        f = m.get("face")
        if f and not f.startswith("data:"):
            p = root / f
            if p.exists():
                m["face"] = b64(p, mimetypes.guess_type(p.name)[0] or "image/jpeg")
            else:
                print("  lipsește fața:", f); m["face"] = None
    db["revizie"] = int(datetime.datetime.now().strftime("%Y%m%d%H%M"))
    return db


def embed_image(rel, max_side):
    """Poză din catalog (cale relativă) -> data URI JPEG redus; data URI-urile rămân neschimbate."""
    if not rel or rel.startswith("data:"):
        return rel
    p = root / rel
    if not p.exists():
        print("  lipsește poza:", rel); return None
    from PIL import Image, ImageOps
    import io
    im = ImageOps.exif_transpose(Image.open(p)).convert("RGB")
    im.thumbnail((max_side, max_side), Image.LANCZOS)
    buf = io.BytesIO(); im.save(buf, "JPEG", quality=86)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def load_catalog():
    """catalog/catalog.json: produse, prețuri, stoc, tabele de mărimi; pozele se includ în aplicație."""
    path = root / "catalog" / "catalog.json"
    if not path.exists():
        return {"app": "DoinaDress-catalog", "schema": 1, "produse": [], "tabele": {}, "revizie": 1}
    cat = json.loads(path.read_text(encoding="utf-8"))
    for pr in cat.get("produse", []):
        pr["poza"] = embed_image(pr.get("poza"), 900)
        if pr.get("desen") and pr["desen"].get("img"):
            pr["desen"]["img"] = embed_image(pr["desen"]["img"], 512)
    cat["revizie"] = int(datetime.datetime.now().strftime("%Y%m%d%H%M"))
    return cat


def make_icons(out):
    """Iconiță: rochie aurie pe fundal închis (generată, fără resurse externe)."""
    from PIL import Image, ImageDraw
    out.mkdir(parents=True, exist_ok=True)
    big = 1024
    im = Image.new("RGBA", (big, big), (20, 23, 29, 255))
    d = ImageDraw.Draw(im)
    gold = (212, 163, 90, 255)
    # umeraș
    d.arc((402, 120, 622, 300), 200, 360, fill=gold, width=34)
    d.line([(512, 270), (240, 420), (784, 420), (512, 270)], fill=gold, width=30, joint="curve")
    # rochie
    d.polygon([(420, 420), (604, 420), (580, 560), (760, 900), (264, 900), (444, 560)], fill=gold)
    d.rectangle((432, 545, 592, 575), fill=(20, 23, 29, 255))
    for size, name in [(512, "icon-512.png"), (192, "icon-192.png"), (180, "apple-touch-icon.png")]:
        im.resize((size, size), Image.LANCZOS).save(out / name)
    # varianta „maskable” (zonă de siguranță 80%)
    m = Image.new("RGBA", (big, big), (20, 23, 29, 255))
    m.paste(im.resize((int(big * .8),) * 2, Image.LANCZOS), (int(big * .1),) * 2)
    m.resize((512, 512), Image.LANCZOS).save(out / "icon-maskable-512.png")


def build(clienti=False, mobil=None, simplu_app=False):
    """clienti=True: versiunea pentru clienții magazinului (manechine, fără pozele familiei) în magazin/.
    mobil: copiază rezultatul în aplicația Flutter (implicit doar pentru versiunea internă).
    simplu_app: în aplicație intră varianta simplă (fără pachetul 3D) — vezi build_simplu.py."""
    if mobil is None:
        mobil = not clienti
    db = load_db("baza_clienti.json" if clienti else "baza_modele.json")
    cat = load_catalog()
    imports = {k: b64(src / "vendor" / v, "text/javascript") for k, v in VENDOR.items()}
    tpl = (src / "cabina3d.template.html").read_text(encoding="utf-8")
    assert "/*DB*/null" in tpl and "/*IMPORTMAP*/" in tpl and "/*CATALOG*/null" in tpl
    a = tpl.index("/*IMPORTMAP*/")
    b = tpl.index("</script>", a)
    html = tpl[:a] + json.dumps({"imports": imports}) + "\n" + tpl[b:]
    html = html.replace("/*DB*/null", json.dumps(db, ensure_ascii=False))
    html = html.replace("/*CATALOG*/null", json.dumps(cat, ensure_ascii=False))
    # corpul realist (MakeHuman): codul în pagină; pachetul inclus în fișierul unic, separat (mh.pack) în web/ și în aplicație
    mh_pack = root / "build_cache" / "mh.pack"
    rt = (src / "mh_runtime.js").read_text(encoding="utf-8")
    html_web = html.replace("/*MH_RUNTIME*/", rt)
    html = html.replace("/*MH_RUNTIME*/", rt.replace("/*MHPACK*/null", json.dumps(base64.b64encode(mh_pack.read_bytes()).decode()) if mh_pack.exists() else "null"))
    assert "/*MODE*/'intern'" in html
    html = html.replace("/*MODE*/'intern'", "'clienti'" if clienti else "'intern'")

    out_dir = root / "magazin" if clienti else root
    out_dir.mkdir(exist_ok=True)
    single = out_dir / ("DoinaDress_Magazin.html" if clienti else "DoinaDress_Cabina3D.html")
    single.write_text(html, encoding="utf-8")
    # varianta simplă: corpul de dinainte (fără MakeHuman), fișier mult mai mic
    simplu = single.with_name(single.stem + "_simplu.html")
    simplu.write_text(html_web.replace("/*MHOFF*/false", "true").replace("/*MODE*/'intern'", "'clienti'" if clienti else "'intern'"), encoding="utf-8")

    web = out_dir / "web"
    web.mkdir(exist_ok=True)
    (web / "index.html").write_text(html_web, encoding="utf-8")
    if mh_pack.exists():
        shutil.copy(mh_pack, web / "mh.pack")
    make_icons(web / "icons")
    (web / "manifest.webmanifest").write_text(json.dumps({
        "name": "DoinaDress – Cabina ta de probă 3D" if clienti else "DoinaDress – Cabină de probă 3D",
        "short_name": "DoinaDress",
        "start_url": "./index.html", "scope": "./", "display": "standalone", "orientation": "any",
        "background_color": "#14171d", "theme_color": "#14171d", "lang": "ro",
        "icons": [
            {"src": "icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "icons/icon-512.png", "sizes": "512x512", "type": "image/png"},
            {"src": "icons/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    (web / "sw.js").write_text((src / "sw.template.js").read_text(encoding="utf-8")
                               .replace("__REV__", str(db["revizie"])), encoding="utf-8")

    app_assets = root / "mobile" / "assets" / "web"
    if mobil and (root / "mobile" / "pubspec.yaml").exists():
        if app_assets.exists():
            shutil.rmtree(app_assets)
        shutil.copytree(web, app_assets, ignore=shutil.ignore_patterns("sw.js", *(["mh.pack"] if simplu_app else [])))
        if simplu_app:
            shutil.copy(simplu, app_assets / "index.html")

    print(f"{single.name}: {single.stat().st_size // 1024} KB, {len(db['modele'])} modele, {len(cat['produse'])} produse, revizie {db['revizie']}")
    print(f"{simplu.name}: {simplu.stat().st_size // 1024} KB (corpul simplu)")
    print(f"{web.relative_to(root)}/ (PWA) gata" + (", copiat în mobile/assets/web" if mobil and app_assets.exists() else ""))


if __name__ == "__main__":
    # python src/build.py              -> versiunea internă (familia), web/, aplicația Flutter
    # python src/build.py --clienti    -> versiunea pentru clienți (manechine) în magazin/
    # python src/build.py --clienti --mobil  -> la fel, plus copiere în aplicația Flutter (vezi build_magazin.py)
    build(clienti="--clienti" in sys.argv, mobil=True if "--mobil" in sys.argv else None)
