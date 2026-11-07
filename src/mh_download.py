"""Descarcă resursele MakeHuman (licență CC0) în assets_src/ — o singură dată, ~560 MB.

  * corpul de bază, țintele de deformare și scheletul: depozitul GitHub makehumancommunity/makehuman (doar folderele necesare);
  * pachetele de haine, păr și pantofi de pe makehumancommunity.org (asset packs CC0).

Apoi: python src/mh_build.py  (creează build_cache/mh.pack)  și  python src/build.py
"""
import pathlib, subprocess, sys, urllib.request, zipfile
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = pathlib.Path(__file__).resolve().parent.parent
DST = ROOT / "assets_src"
PACKS = ["makehuman_system_assets", "shirts01", "pants01", "dress01", "skirts01", "shoes01", "suits01"]
MIRRORS = ["https://files2.makehumancommunity.org", "https://files.makehumancommunity.org"]
REPO_DIRS = ["makehuman/data/3dobjs", "makehuman/data/targets/macrodetails", "makehuman/data/targets/measure",
             "makehuman/data/targets/breast", "makehuman/data/targets/stomach", "makehuman/data/rigs"]


def repo():
    d = DST / "mh_repo"
    if not d.exists():
        subprocess.run(["git", "clone", "-q", "--depth", "1", "--filter=blob:none", "--sparse",
                        "https://github.com/makehumancommunity/makehuman.git", str(d)], check=True)
    subprocess.run(["git", "sparse-checkout", "set", *REPO_DIRS], cwd=d, check=True)
    print("corp + ținte + schelet: gata")


def packs():
    (DST / "zips").mkdir(parents=True, exist_ok=True)
    for p in PACKS:
        z, out = DST / "zips" / f"{p}_cc0.zip", DST / "packs" / ("system" if p == "makehuman_system_assets" else p)
        if out.exists() and any(out.iterdir()):
            print(f"{p}: există"); continue
        for m in MIRRORS:
            try:
                print(f"{p}: descarc de pe {m} …")
                urllib.request.urlretrieve(f"{m}/asset_packs/{p}/{p}_cc0.zip", z)
                with zipfile.ZipFile(z) as f:
                    for name in f.namelist():            # doar căi relative, fără ieșiri din folder
                        if name.startswith("/") or ".." in pathlib.PurePosixPath(name).parts:
                            raise RuntimeError("arhivă suspectă: " + name)
                    f.extractall(out)
                break
            except Exception as e:
                print(f"   eșuat ({e}), încerc alt server")
        else:
            raise SystemExit(f"Nu am putut descărca {p}.")
    print("pachete: gata")


if __name__ == "__main__":
    DST.mkdir(exist_ok=True)
    repo()
    packs()
