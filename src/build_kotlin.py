"""Aplicațiile Android native (Kotlin, android_kotlin/): toate cele 4 variante dintr-o singură comandă.

  python src/build_kotlin.py

Pași: pagina web a fiecărei variante (familie / magazin × realist / simplu) -> android_kotlin/app/src/<variantă>/assets/web
-> gradlew assembleRelease -> APK-urile în kotlin_apk/. La final se refac resursele aplicației Flutter (versiunea familiei).
"""
import pathlib, shutil, subprocess, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build

root = build.root
K = root / "android_kotlin"
OUT = root / "kotlin_apk"
NUME = {"familieRealist": "DoinaDress.apk", "familieSimplu": "DoinaDress_Simplu.apk",
        "magazinRealist": "DoinaDress_Magazin.apk", "magazinSimplu": "DoinaDress_Magazin_Simplu.apk"}


def assets(public):
    clienti = public == "magazin"
    build.build(clienti=clienti, mobil=False)
    web = root / ("magazin/web" if clienti else "web")
    simplu = root / ("magazin/DoinaDress_Magazin_simplu.html" if clienti else "DoinaDress_Cabina3D_simplu.html")
    for corp in ("Realist", "Simplu"):
        dst = K / "app" / "src" / f"{public}{corp}" / "assets" / "web"
        if dst.exists():
            shutil.rmtree(dst)
        skip = ["sw.js"] + (["mh.pack"] if corp == "Simplu" else [])     # fără service worker; simplu: fără pachetul 3D
        shutil.copytree(web, dst, ignore=shutil.ignore_patterns(*skip))
        if corp == "Simplu":
            shutil.copy(simplu, dst / "index.html")


try:
    assets("familie")
    assets("magazin")
    gradlew = K / ("gradlew.bat" if sys.platform == "win32" else "gradlew")
    subprocess.run([str(gradlew), "assembleRelease", "--console=plain"], cwd=K, check=True)
    OUT.mkdir(exist_ok=True)
    for v, nume in NUME.items():
        apk = next((K / "app" / "build" / "outputs" / "apk").glob(f"{v}/release/*.apk"))
        shutil.copy(apk, OUT / nume)
        print(f"kotlin_apk/{nume}: {(OUT / nume).stat().st_size / 2**20:.1f} MB")
finally:
    build.build()          # resursele aplicației Flutter (familia) la loc
