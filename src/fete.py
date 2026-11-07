"""Unelte pentru fețele avatarurilor DoinaDress.

Fiecare față este aliniată după cei doi ochi (aceeași regulă ca în aplicație):
ochii devin orizontali, distanța dintre ei = 1024/2.6 px, mijlocul lor la 50% lățime și 40% înălțime.
Rezultat: fete/<id>.jpg, 1024 x 1280 px.

Comenzi:
  python src/fete.py toate
      regenerează toate fețele din modele/baza_modele.json (câmpul "sursa")
  python src/fete.py grila FOTO [X0 Y0 X1 Y1]
      salvează FOTO_grila.png cu grilă de coordonate, ca să citești poziția ochilor
  python src/fete.py adauga --id ion --rol Bunic --nume Ion --gen m --varsta adult \
                            --foto poze/ion.jpg --ochi 812 640 905 644 [--sablon barbat]
      adaugă (sau actualizează) un model în bază și îi generează fața
"""
import argparse, json, math, pathlib, statistics, sys
from PIL import Image, ImageDraw, ImageFilter, ImageOps

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = pathlib.Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "modele" / "baza_modele.json"
FW, FH, EYE_Y = 1024, 1280, 0.40
IOD = FW / 2.6


def open_photo(path):
    p = pathlib.Path(path)
    if not p.is_absolute():
        p = ROOT / p
    return ImageOps.exif_transpose(Image.open(p)).convert("RGB")


def align(img, left, right):
    (x1, y1), (x2, y2) = sorted([tuple(left), tuple(right)])
    ang = math.atan2(y2 - y1, x2 - x1)
    s = math.hypot(x2 - x1, y2 - y1) / IOD
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    a, b = s * math.cos(ang), -s * math.sin(ang)
    d, e = s * math.sin(ang), s * math.cos(ang)
    c = mx - a * FW / 2 - b * FH * EYE_Y
    f = my - d * FW / 2 - e * FH * EYE_Y
    out = img.transform((FW, FH), Image.AFFINE, (a, b, c, d, e, f), resample=Image.BICUBIC)
    if s < 1:  # sursa e mai mică decât ținta -> mărire; reîmprospătăm detaliile
        out = out.filter(ImageFilter.UnsharpMask(radius=2, percent=70, threshold=2))
    return out


def skin_of(face):
    px = []
    for box in [(int(FW * .28), int(FH * .52), int(FW * .40), int(FH * .62)),
                (int(FW * .60), int(FH * .52), int(FW * .72), int(FH * .62))]:
        reg = face.crop(box)
        px += list(reg.get_flattened_data() if hasattr(reg, 'get_flattened_data') else reg.getdata())
    med = [statistics.median(ch) for ch in zip(*px)]
    return "#%02x%02x%02x" % tuple(int(v) for v in med)


def make_face(model):
    src = model.get("sursa") or {}
    if not src.get("foto") or not src.get("ochi"):
        print(f"  {model['id']}: fără 'sursa' -> sar peste"); return
    face = align(open_photo(src["foto"]), *src["ochi"])
    out = ROOT / "fete" / f"{model['id']}.jpg"
    out.parent.mkdir(exist_ok=True)
    face.save(out, quality=92)
    model["face"] = f"fete/{model['id']}.jpg"
    model["skin"] = skin_of(face)
    print(f"  {model['id']}: {out.name}  piele {model['skin']}")


def load_db():
    return json.loads(DB_PATH.read_text(encoding="utf-8"))


def save_db(db):
    DB_PATH.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")


def cmd_toate(_):
    db = load_db()
    for m in db["modele"]:
        make_face(m)
    save_db(db)


def cmd_grila(a):
    img = open_photo(a.foto)
    x0, y0, x1, y1 = a.zona or (0, 0, img.width, img.height)
    c = img.crop((x0, y0, x1, y1))
    d = ImageDraw.Draw(c)
    step = 20 if (x1 - x0) < 800 else 50
    for gx in range((x0 // step + 1) * step, x1, step):
        major = gx % (step * 5) == 0
        d.line([(gx - x0, 0), (gx - x0, c.height)], fill=(0, 255, 0) if major else (0, 120, 0))
        if major: d.text((gx - x0 + 2, 2), str(gx), fill=(255, 255, 0))
    for gy in range((y0 // step + 1) * step, y1, step):
        major = gy % (step * 5) == 0
        d.line([(0, gy - y0), (c.width, gy - y0)], fill=(0, 255, 0) if major else (0, 120, 0))
        if major: d.text((2, gy - y0 + 2), str(gy), fill=(255, 255, 0))
    out = pathlib.Path(a.foto).with_name(pathlib.Path(a.foto).stem + "_grila.png")
    c.save(out); print("grila salvată:", out)


def cmd_adauga(a):
    db = load_db()
    models = db["modele"]
    tpl = next((m for m in models if m["id"] == a.sablon), None) \
        or next((m for m in models if m["gen"] == a.gen and m["varsta"] == a.varsta), None) or models[0]
    m = next((x for x in models if x["id"] == a.id), None)
    if m is None:
        m = json.loads(json.dumps(tpl)); m["id"] = a.id; models.append(m)
    m.update(rol=a.rol or m.get("rol", ""), nume=a.nume or "", gen=a.gen, varsta=a.varsta)
    m["faceAdj"] = m.get("faceAdj") or {"scale": 1, "dy": 0, "bright": 1}
    m["sursa"] = {"foto": a.foto, "ochi": [a.ochi[0:2], a.ochi[2:4]]}
    make_face(m)
    db["revizie"] = int(db.get("revizie", 1)) + 1
    save_db(db)
    print(f"model '{a.id}' salvat. Rulează acum: python src/build.py")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("toate").set_defaults(fn=cmd_toate)
    g = sub.add_parser("grila"); g.add_argument("foto"); g.add_argument("zona", nargs="*", type=int); g.set_defaults(fn=cmd_grila)
    ad = sub.add_parser("adauga")
    ad.add_argument("--id", required=True); ad.add_argument("--rol", default="")
    ad.add_argument("--nume", default=""); ad.add_argument("--gen", choices=["m", "f"], required=True)
    ad.add_argument("--varsta", choices=["adult", "adolescent", "copil"], required=True)
    ad.add_argument("--foto", required=True); ad.add_argument("--ochi", nargs=4, type=int, required=True)
    ad.add_argument("--sablon", default=None); ad.set_defaults(fn=cmd_adauga)
    args = ap.parse_args()
    if getattr(args, "zona", None) is not None and args.cmd == "grila" and len(args.zona) not in (0, 4):
        sys.exit("zona = X0 Y0 X1 Y1")
    args.fn(args)
