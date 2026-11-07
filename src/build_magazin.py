"""Aplicația Android pentru clienții magazinului: magazin/DoinaDress_Magazin.apk.

Pași: versiunea pentru clienți (manechine) -> mobile/assets/web -> flutter build apk (id ro.doinadress.magazin,
nume „DoinaDress Magazin”, se poate instala alături de aplicația internă) -> la final se refac resursele
aplicației interne, ca `flutter build apk` simplu să producă din nou versiunea familiei.
"""
import pathlib, shutil, subprocess, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build

root = build.root
build.build(clienti=True, mobil=True)
try:
    subprocess.run("flutter build apk --release -P magazin=true", cwd=root / "mobile", shell=True, check=True)
    apk = root / "magazin" / "DoinaDress_Magazin.apk"
    shutil.copy(root / "mobile" / "build" / "app" / "outputs" / "flutter-apk" / "app-release.apk", apk)
    print(f"{apk.relative_to(root)}: {apk.stat().st_size // (1024 * 1024)} MB")
finally:
    build.build()          # resursele aplicației interne la loc
