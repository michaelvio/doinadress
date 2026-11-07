"""Construiește pachetul 3D realist (MakeHuman, CC0) folosit de aplicație: build_cache/mh.pack

Conține:
  * corpul de bază (19158 vârfuri, fețele corpului cu UV), în decimetri;
  * țintele de deformare: gen × vârstă (medie a celor 3 rase), greutate min/max, măsuri (bust, sub bust, talie, șold, coapsă);
  * buclele de măsurare ale MakeHuman (bust, talie, șold…), greutățile brațelor (pentru a coborî brațele) și ochii;
  * hainele alese din pachetele CC0, separate pe piese, legate de corp prin .mhclo (se potrivesc pe orice corp);
  * părul (10 coafuri) și texturile de relief (normal map + „detaliu” = cute, cusături, tricot) reduse la 512 px.

Formatul: 'MHPK' + uint32 lungime JSON + JSON (index) + blob binar; JSON-ul dă pentru fiecare tablou (offset, tip, lungime).
Rulare: python src/mh_build.py   (are nevoie de assets_src/, descărcat o singură dată — vezi ghidul)
"""
import io, json, pathlib, struct, sys
import numpy as np
from PIL import Image, ImageFilter, ImageOps
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mh_lib as L

ROOT = pathlib.Path(__file__).resolve().parent.parent
PACKS = ROOT / "assets_src" / "packs"
OUT = ROOT / "build_cache" / "mh.pack"
TEX = 512

# ------------------------------------------------------------------ alegerea hainelor
# id: (fișier .mhclo, componente (None = toate; listă = indicii componentelor conexe, după mărime), detaliu, opțiuni)
#   detaliu: 'ao' = harta de umbrire a hainei; 'lum' = luminozitatea texturii (tricot, cute); None = fără (texturi cu imprimeu)
GARMENTS = {
    # sus
    "tricou_m":   ("elvs_crude_t-shirt_male", None, "lum", {}),
    "tricou_f":   ("joepal_crude_t-shirt_female", None, "lum", {}),
    "bluza_f":    ("female_elegantsuit01", [0], "ao", {}),
    "camasa":     ("male_casualsuit03", [0], "ao", {}),
    "polo":       ("namuhekam_male_polo_shirt", None, "lum", {}),
    "pulover":    ("toigo_fisherman_sweater", None, "lum", {}),
    # jos
    "pantaloni":  ("toigo_wool_pants", None, "lum", {}),
    "blugi":      ("male_casualsuit02", [1], "ao", {}),
    "scurti":     ("cortu_jeans_shorts", None, "lum", {}),
    "fusta":      ("female_elegantsuit01", [1], "ao", {}),
    "fusta_lunga": ("toigo_long_full_skirt", None, None, {}),
    # rochii
    "rochie":     ("toigo_cut_out_dress", None, None, {}),
    "rochie_scurta": ("wdg_mycenaean_tunic", None, "lum", {}),
    "rochie_lunga": ("toigo_halter_dress_with_fluted_skirt", None, None, {}),
    "sarafan":    ("toigo_shift_dress", None, "lum", {}),
    # strat exterior
    "geaca":      ("male_casualsuit05", [0], "ao", {}),
    "sacou_m":    ("toigo_male_suit_3", [0], "lum", {}),
    "sacou_f":    ("toigo_female_suit", [0], "lum", {}),
    "vesta":      ("toigo_male_suit_3", [0], "lum", {"no_arms": True}),
    "palton_m":   ("toigo_male_double-breasted_suit", "top", "lum", {}),
    "palton_f":   ("toigo_female_double-breasted_suit", [1], "lum", {}),
    # încălțăminte
    "pantofi_m":  ("shoes01", None, "lum", {}),
    "pantofi_f":  ("toigo_mj_cloth_shoes", None, "lum", {}),
    "adidasi":    ("shoes05", None, "lum", {}),
    "cizme_m":    ("shoes03", None, "lum", {}),
    "cizme_f":    ("toigo_ankle_boots_female", None, "lum", {}),
    "balerini":   ("toigo_ballet_flats", None, "lum", {}),
    "toc":        ("toigo_stiletto_booties", None, "lum", {}),
    "sandale":    ("cortu_t-bar", None, "lum", {}),
}
HAIR = {"scurt": "short02", "tepi": "short04", "pixie": "short01", "bob": "bob01", "lung": "long01",
        "coada": "ponytail01", "impletitura": "braid01", "afro": "afro01", "scurt3": "short03", "bob2": "bob02"}
RACES = ("african", "asian", "caucasian")
MEASURES = {   # buclele riglei MakeHuman (plugins/0_modeling_a_measurement.py), CC0
    "bust": [8439,8455,8462,8446,8478,8494,8557,8510,8526,8542,10720,10601,10603,10602,10612,10611,10610,10613,10604,10605,10606,3942,3941,3940,3950,3947,3948,3949,3938,3939,3937,4065,1870,1854,1838,1885,1822,1806,1774,1790,1783,1767,1799,8471],
    "underbust": [10750,10744,10724,10725,10748,10722,10640,10642,10641,10651,10650,10649,10652,10643,10644,10645,10646,10647,10648,3988,3987,3986,3985,3984,3983,3982,3992,3989,3990,3991,3980,3981,3979,4067,4098,4073,4072,4094,4100,4082,4088,4088],
    "waist": [4121,10760,10757,10777,10776,10779,10780,10778,10781,10771,10773,10772,10775,10774,10814,10834,10816,10817,10818,10819,10820,10821,4181,4180,4179,4178,4177,4176,4175,4196,4173,4131,4132,4129,4130,4128,4138,4135,4137,4136,4133,4134,4108,4113,4118,4121],
    "hips": [4341,10968,10969,10971,10970,10967,10928,10927,10925,10926,10923,10924,10868,10875,10861,10862,4228,4227,4226,4242,4234,4294,4293,4296,4295,4297,4298,4342,4345,4346,4344,4343,4361,4341],
    "thigh": [11071,11080,11081,11086,11076,11077,11074,11075,11072,11073,11069,11070,11087,11085,11084,12994,11083,11082,11079,11071],
}


class Pack:
    def __init__(self):
        self.blob = io.BytesIO(); self.index = {}

    def arr(self, a, dtype):
        a = np.asarray(a)
        if np.issubdtype(np.dtype(dtype), np.integer) and a.size:      # fără depășiri tăcute (ex. ținta „copil feminin”)
            lim = np.iinfo(dtype)
            if a.min() < lim.min or a.max() > lim.max:
                raise ValueError(f"valori în afara {np.dtype(dtype).name}: {a.min()}..{a.max()}")
        a = np.ascontiguousarray(a.astype(dtype).ravel())
        while self.blob.tell() % 4:
            self.blob.write(b"\0")
        off = self.blob.tell(); self.blob.write(a.tobytes())
        return {"o": off, "t": np.dtype(dtype).name, "n": int(a.size)}

    def raw(self, data, mime):
        while self.blob.tell() % 4:
            self.blob.write(b"\0")
        off = self.blob.tell(); self.blob.write(data)
        return {"o": off, "n": len(data), "mime": mime}

    def save(self, path):
        j = json.dumps(self.index, separators=(",", ":")).encode()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            f.write(b"MHPK"); f.write(struct.pack("<I", len(j))); f.write(j)
            f.write(b"\0" * ((-(8 + len(j))) % 4)); f.write(self.blob.getvalue())


def jpeg(im, q=86):
    b = io.BytesIO(); im.save(b, "JPEG", quality=q); return b.getvalue()


def png(im):
    b = io.BytesIO(); im.save(b, "PNG", optimize=True); return b.getvalue()


def render_mesh(faces, vt, keep=None):
    """Fețe (quad/tri) -> vârfuri de randare unice (v, vt), triunghiuri."""
    key, rv, ruv, tris = {}, [], [], []
    for vi, ti, _ in faces:
        if keep is not None and not keep(vi):
            continue
        ids = []
        for a, t in zip(vi, ti):
            k = (a, t)
            if k not in key:
                key[k] = len(rv); rv.append(a); ruv.append(vt[t] if t >= 0 else (0, 0))
            ids.append(key[k])
        for i in range(1, len(ids) - 1):
            tris.append((ids[0], ids[i], ids[i + 1]))
    return np.array(rv), np.array(ruv), np.array(tris)


def components(nv, faces):
    par = list(range(nv))
    def f(x):
        while par[x] != x:
            par[x] = par[par[x]]; x = par[x]
        return x
    for vi, _, _ in faces:
        for a in vi[1:]:
            par[f(a)] = f(vi[0])
    roots = {}
    for i in range(nv):
        roots.setdefault(f(i), []).append(i)
    return sorted(roots.values(), key=len, reverse=True)


def load_tex(path):
    try:
        return ImageOps.exif_transpose(Image.open(path))
    except Exception:
        return None


def detail_map(mat_dir, mat, mode):
    """Hartă de detaliu în tonuri de gri, medie 1 (codată 0..255 cu 0.5 = 128 -> factor ×2 în shader)."""
    src = None
    if mode == "ao":
        cand = list(mat_dir.glob("*_ao.png"))
        src = load_tex(cand[0]) if cand else None
    if src is None and mode in ("ao", "lum") and mat.get("diffuseTexture"):
        src = load_tex(mat_dir / mat["diffuseTexture"])
    if src is None:
        return None
    g = src.convert("L").resize((TEX, TEX), Image.LANCZOS)
    a = np.asarray(g, dtype=np.float32) + 8
    # filtru „trece-sus”: împărțim la media locală, ca să rămână doar cutele, cusăturile și tricotul,
    # nu și petele mari de culoare / imprimeurile din textura originală
    blur = np.asarray(Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(18 if mode == "lum" else 40)), dtype=np.float32) + 8
    a = np.clip(1 + (a / blur - 1) * 0.8, 0.55, 1.35)
    a = np.clip(a * 0.5, 0, 1) * 255
    return Image.fromarray(a.astype(np.uint8))


def normal_map(mat_dir, mat):
    for k in ("normalmapTexture", "bumpTexture"):
        if mat.get(k):
            im = load_tex(mat_dir / mat[k])
            if im is not None:
                im = im.convert("RGB").resize((TEX, TEX), Image.LANCZOS)
                a = np.asarray(im)
                if a[..., 2].mean() > 150 and abs(a[..., 0].mean() - 128) < 40:     # pare hartă de normale (albăstruie)
                    return im
    return None


def bind_arrays(clo, sel):
    refs = clo["refs"][sel]; w = clo["weights"][sel]; off = clo["offsets"][sel]
    return refs, w, off


BODY_NB = {}


def body_neighbors(base_f, nb=13380):
    if not BODY_NB:
        for vi, _, g in base_f:
            if g != "body":
                continue
            for k, a in enumerate(vi):
                BODY_NB.setdefault(a, set()).update(vi[:k] + vi[k + 1:])
    return BODY_NB


HELPER_NEAR = {}


def helper_to_body(base_v, nb=13380):
    """Vârfurile ajutătoare (colanți, fustă, păr) -> cel mai apropiat vârf al corpului."""
    if not HELPER_NEAR:
        B = base_v[:nb]
        for s in range(nb, len(base_v), 512):
            H = base_v[s:s + 512]
            d = ((H[:, None, :] - B[None, :, :]) ** 2).sum(-1)
            for k, j in enumerate(d.argmin(1)):
                HELPER_NEAR[s + k] = int(j)
    return HELPER_NEAR


def covered(clo, keep, base_f, base_v):
    """Vârfurile corpului aflate sigur sub haină (legate de ea, fără marginea de un rând)."""
    nbr, near = body_neighbors(base_f), helper_to_body(base_v)
    seed = set()
    for i in keep:
        for r, w in zip(clo["refs"][i], clo["weights"][i]):
            if abs(w) > .05:
                seed.add(int(r) if r < 13380 else near[int(r)])
    return sorted(v for v in seed if all(n in seed for n in nbr.get(v, ())))


def local_delete(clo, keep, base_f, base_v, rings=1):
    """Doar zona corpului de sub piesa păstrată (un costum ascunde tot corpul; o piesă din el, doar zona ei)."""
    nbr, near = body_neighbors(base_f), helper_to_body(base_v)
    seed = set()
    for i in keep:
        for r, w in zip(clo["refs"][i], clo["weights"][i]):
            if abs(w) > .05:
                seed.add(int(r) if r < 13380 else near[int(r)])
    if not clo["delete_verts"]:                 # haina nu are listă: ascundem corpul de sub ea, fără marginea de un rând
        return [v for v in seed if all(n in seed for n in nbr.get(v, ()))]
    reg = set(seed)
    for _ in range(rings):
        reg |= {n for v in list(reg) for n in nbr.get(v, ())}
    return [v for v in clo["delete_verts"] if v in reg]


def add_proxy(pack, pid, mhclo_path, comps, detail, opts, base_v, arm_w, is_hair=False, base_f=None):
    clo = L.read_mhclo(mhclo_path)
    gv, gvt, gf, _ = L.read_obj(mhclo_path.parent / clo["obj"])
    if len(clo["refs"]) != len(gv):
        print(f"  ! {pid}: {len(clo['refs'])} legături pentru {len(gv)} vârfuri — sar"); return None
    keepv = None
    if comps is not None:
        cs = components(len(gv), gf)
        if comps == "top":
            pos0 = L.fit_proxy(clo, base_v)
            cs = [c for c in cs if pos0[c][:, 1].max() > 3.0 and len(c) > 400][:1]
            keepv = set(cs[0])
        else:
            keepv = set(i for k in comps for i in cs[k])
    if opts.get("no_arms"):                     # vestă: fără mâneci (vârfurile legate de brațe)
        armv = np.maximum(arm_w[0], arm_w[1])
        army = (armv[clo["refs"]] * np.clip(clo["weights"], 0, 1)).sum(1)       # cât e legat vârful de braț
        keepv = set(i for i in (keepv or range(len(gv))) if army[i] < 0.25)
    keep = (lambda vi: all(a in keepv for a in vi)) if keepv is not None else None
    rv, ruv, tris = render_mesh(gf, gvt, keep)
    if not len(tris):
        print(f"  ! {pid}: fără fețe"); return None
    used = np.unique(rv)                                  # doar vârfurile folosite
    remap = -np.ones(len(gv), dtype=np.int64); remap[used] = np.arange(len(used))
    refs, w, off = bind_arrays(clo, used)
    # metri pe unitate UV (pentru desenul materialului la mărimea reală)
    pos = L.fit_proxy(clo, base_v)[rv]
    e3 = np.linalg.norm(pos[tris[:, 1]] - pos[tris[:, 0]], axis=1).sum()
    eu = np.linalg.norm(ruv[tris[:, 1]] - ruv[tris[:, 0]], axis=1).sum()
    muv = float(e3 / max(eu, 1e-9)) * 0.1
    mat = L.read_mhmat(mhclo_path.parent / clo["material"]) if clo["material"] and (mhclo_path.parent / clo["material"]).exists() else {}
    rec = {
        "nv": int(len(used)), "refs": pack.arr(refs, np.uint16), "w": pack.arr(w, np.float32),
        "off": pack.arr(np.round(off * 1e3), np.int16),
        "scale": {k: [int(a), int(b), float(c)] for k, (a, b, c) in clo["scale"].items()},
        "rmap": pack.arr(remap[rv], np.uint16), "uv": pack.arr(ruv, np.float32), "idx": pack.arr(tris, np.uint16 if len(rv) < 65536 else np.uint32),
        "del": pack.arr(sorted(set(v for v in (local_delete(clo, used, base_f, base_v) if keepv is not None or not clo["delete_verts"] else clo["delete_verts"]) if v < 13380)), np.uint16),
        "cov": pack.arr(covered(clo, used, base_f, base_v), np.uint16),
        "z": int(clo["z_depth"]), "muv": round(muv, 5),
    }
    if is_hair:
        dt = load_tex(mhclo_path.parent / mat.get("diffuseTexture", "")) if mat.get("diffuseTexture") else None
        if dt is not None:
            dt = dt.convert("RGBA").resize((1024, 1024), Image.LANCZOS)
            r, g, b, a = dt.split()
            lum = ImageOps.autocontrast(dt.convert("L"), cutoff=1)        # culoarea vine din aplicație: păstrăm doar luminozitatea
            rec["tex"] = pack.raw(png(Image.merge("LA", (lum, a))), "image/png")
    else:
        d = detail_map(mhclo_path.parent, mat, detail) if detail else None
        if d is not None:
            rec["detail"] = pack.raw(jpeg(d, 88), "image/jpeg")
        n = normal_map(mhclo_path.parent, mat)
        if n is not None:
            rec["normal"] = pack.raw(jpeg(n, 90), "image/jpeg")
    return rec


def main():
    pack = Pack()
    base_v, base_vt, base_f, groups = L.read_obj(L.MH / "3dobjs" / "base.obj")
    nv, nb = len(base_v), 13380
    print(f"corp: {nv} vârfuri, {nb} ale corpului")
    sk, weights = L.read_skeleton()

    # greutățile brațelor: tot ce atârnă de upperarm01 (brațul, antebrațul, mâna)
    def subtree(root):
        out, todo = set(), [root]
        while todo:
            b = todo.pop(); out.add(b)
            todo += [k for k, v in sk["bones"].items() if v["parent"] == b]
        return out
    arm_w = []
    for side in ("L", "R"):
        w = np.zeros(nv)
        for b in subtree("upperarm01." + side):
            for i, x in weights.get(b, []):
                w[i] += x
        arm_w.append(np.clip(w, 0, 1))
    lowarm_w = []
    for side in ("L", "R"):
        w = np.zeros(nv)
        for b in subtree("lowerarm01." + side):
            for i, x in weights.get(b, []):
                w[i] += x
        lowarm_w.append(np.clip(w, 0, 1))
    # vârfurile ajutătoare (de care se leagă mânecile) au greutăți incomplete în .mhw (0 pe dreapta, ~0,5 pe stânga):
    # le iau de la cel mai apropiat vârf al corpului, altfel mâneca nu urmează brațul coborât și mâna pare „tăiată”
    near = helper_to_body(base_v)
    hi_, bj = np.array(list(near.keys())), np.array(list(near.values()))
    for w in arm_w + lowarm_w:
        w[hi_] = w[bj]
    head_w = np.zeros(nv)
    for b in subtree("head"):
        for i, x in weights.get(b, []):
            head_w[i] += x
    joints = {k: v for k, v in sk["joints"].items()}
    J = lambda name: joints[name]

    # corpul: fețele grupului „body” + globii oculari (pentru manechin / fața din poză)
    bodyset = groups["body"]; eyes = groups["helper-l-eye"] | groups["helper-r-eye"]
    rv, ruv, tris = render_mesh(base_f, base_vt, lambda vi: all(a in bodyset for a in vi))
    erv, euv, etris = render_mesh(base_f, base_vt, lambda vi: all(a in eyes for a in vi))
    # fața: triunghiurile capului din față (pentru proiecția fotografiei)
    hc = base_v[list(groups["joint-head"])].mean(0)
    P = base_v[rv]
    tri_head = np.array([i for i, t in enumerate(tris) if min(head_w[rv[t]]) > .95 and P[t][:, 2].mean() > hc[2] - .1])
    pack.index["body"] = {
        "nv": nv, "nb": nb, "v": pack.arr(base_v, np.float32),
        "rmap": pack.arr(rv, np.uint16), "uv": pack.arr(ruv, np.float32), "idx": pack.arr(tris, np.uint16),
        "eye": {"rmap": pack.arr(erv, np.uint16), "idx": pack.arr(etris, np.uint16)},
        "faceTris": pack.arr(tri_head, np.uint16),
        "armL": pack.arr(np.round(arm_w[0] * 255), np.uint8), "armR": pack.arr(np.round(arm_w[1] * 255), np.uint8),
        "lowL": pack.arr(np.round(lowarm_w[0] * 255), np.uint8), "lowR": pack.arr(np.round(lowarm_w[1] * 255), np.uint8),
        "joints": {k: J(k) for k in ("upperarm01.L____head", "upperarm01.R____head", "lowerarm01.L____head", "lowerarm01.R____head",
                                     "wrist.L____head", "wrist.R____head", "head____head", "neck01____head", "spine03____head",
                                     "pelvis.L____head", "upperleg01.L____head", "upperleg01.R____head", "foot.L____head", "foot.R____head")},
        "eyeL": sorted(groups["joint-l-eye"]), "eyeR": sorted(groups["joint-r-eye"]),
        "measures": MEASURES,
    }
    print(f"  fețe corp {len(tris)}, ochi {len(etris)}, față {len(tri_head)}")

    # ținte
    tg = {}
    T = L.MH / "targets"
    def put(name, d):
        nz = np.where(np.abs(d).max(1) > 1e-5)[0]
        tg[name] = {"i": pack.arr(nz, np.uint16), "d": pack.arr(np.round(d[nz] * 1e3), np.int16)}
    for g in ("female", "male"):
        for a in ("child", "young"):
            d = sum(L.dense_target(T / "macrodetails" / f"{r}-{g}-{a}.target", nv) for r in RACES) / 3
            put(f"{g}-{a}", d)
            for wt in ("minweight", "maxweight"):
                put(f"{g}-{a}-{wt}", L.dense_target(T / "macrodetails" / f"universal-{g}-{a}-averagemuscle-{wt}.target", nv))
    for m in ("bust", "underbust", "waist", "hips", "thigh"):
        for s in ("incr", "decr"):
            put(f"{m}-{s}", L.dense_target(T / "measure" / f"measure-{m}-circ-{s}.target", nv))
    pack.index["targets"] = tg
    print(f"  ținte: {len(tg)}")

    # haine
    gi = {}
    for gid, (name, comps, det, opts) in GARMENTS.items():
        found = list(PACKS.rglob(name + ".mhclo"))
        if not found:
            print(f"  ! lipsește {name}"); continue
        rec = add_proxy(pack, gid, found[0], comps, det, opts, base_v, arm_w, base_f=base_f)
        if rec:
            gi[gid] = rec; print(f"  haină {gid:14s} {rec['nv']:5d} v  ascunde {rec['del']['n']:5d}  muv={rec['muv']}  {'detaliu ' if 'detail' in rec else ''}{'normale' if 'normal' in rec else ''}")
    pack.index["garments"] = gi
    hi = {}
    for st, name in HAIR.items():
        found = list((PACKS / "system" / "hair").rglob(name + ".mhclo"))
        if found:
            rec = add_proxy(pack, st, found[0], None, None, {}, base_v, arm_w, is_hair=True, base_f=base_f)
            if rec:
                hi[st] = rec; print(f"  păr {st:12s} {rec['nv']:5d} v")
    pack.index["hair"] = hi
    pack.index["license"] = "Corp, ținte, haine și păr: MakeHuman (makehumancommunity.org), licență CC0 1.0."
    pack.save(OUT)
    print(f"{OUT.relative_to(ROOT)}: {OUT.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
