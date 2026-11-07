"""Aplicația Android mică, doar cu corpul simplu (fără pachetul 3D MakeHuman): DoinaDress_Simplu.apk.

Pași: versiunea simplă -> mobile/assets/web (fără mh.pack) -> flutter build apk (id ro.doinadress.doinadress.simplu,
nume „DoinaDress Simplu”, se poate instala alături de aplicația realistă) -> la final se refac resursele
aplicației interne, ca `flutter build apk` simplu să producă din nou versiunea completă.
APK-ul e doar pentru arm64 (toate telefoanele Android din ultimii ~8 ani), ca să fie cât mai mic.

  python src/build_simplu.py             -> DoinaDress_Simplu.apk (familia)
  python src/build_simplu.py --clienti   -> magazin/DoinaDress_Magazin_Simplu.apk (manechine)
"""
import pathlib, shutil, subprocess, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build

root = build.root
clienti = "--clienti" in sys.argv
build.build(clienti=clienti, mobil=True, simplu_app=True)
try:
    subprocess.run("flutter build apk --release --split-per-abi --target-platform android-arm64 -P simplu=true" + (" -P magazin=true" if clienti else ""),
                   cwd=root / "mobile", shell=True, check=True)
    apk = root / ("magazin/DoinaDress_Magazin_Simplu.apk" if clienti else "DoinaDress_Simplu.apk")
    shutil.copy(root / "mobile" / "build" / "app" / "outputs" / "flutter-apk" / "app-arm64-v8a-release.apk", apk)
    print(f"{apk.relative_to(root)}: {apk.stat().st_size // (1024 * 1024)} MB")
finally:
    build.build()          # resursele aplicației interne (complete) la loc
