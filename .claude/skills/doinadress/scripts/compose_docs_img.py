"""Copiază capturile făcute cu shots.mjs în docs/img și compune familia.png și fete_3d.png.
Rulare: python compose_docs_img.py <dir_capturi>
"""
import pathlib, shutil, sys
from PIL import Image

src = pathlib.Path(sys.argv[1])
out = pathlib.Path(__file__).resolve().parents[4] / "docs" / "img"
for k in ["corp_realist", "fata_realist", "catalog", "panou", "telefon"]:
    shutil.copy(src / f"{k}.png", out / f"{k}.png")
# familia.png: banda 1000×300 din scena variantei simple (fără panoul din stânga)
Image.open(src / "familia_full.png").crop((382, 212, 1382, 512)).save(out / "familia.png")
# fete_3d.png: 3 prim-planuri de 500×570, fără bara de sus și butonul de jos
sheet = Image.new("RGB", (1500, 570))
for i, k in enumerate(["barbat", "femeie", "fetita"]):
    sheet.paste(Image.open(src / f"fata_{k}.png").convert("RGB").crop((0, 62, 500, 632)), (i * 500, 0))
sheet.save(out / "fete_3d.png")
for f in sorted(out.glob("*.png")):
    print(f.name, Image.open(f).size)
