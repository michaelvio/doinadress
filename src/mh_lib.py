"""Cititoare pentru formatele MakeHuman (CC0): base.obj, .target, .mhclo, .mhskel/.mhw.

Folosite de src/mh_build.py ca să producă resursele compacte ale corpului 3D realist.
Fișierele sursă sunt doar text; nimic din ele nu se execută.
"""
import json, pathlib, re
import numpy as np

MH = pathlib.Path(__file__).resolve().parent.parent / "assets_src" / "mh_repo" / "makehuman" / "data"


def read_obj(path, keep_groups=None):
    """OBJ cu fețe quad/tri. Întoarce v (N,3), vt (M,2), fețele [(vidx, vtidx, grup)] și grupurile de vârfuri."""
    v, vt, faces, groups, group = [], [], [], {}, None
    for line in open(path, encoding="utf-8", errors="replace"):
        if line.startswith("v "):
            v.append([float(x) for x in line.split()[1:4]])
        elif line.startswith("vt "):
            vt.append([float(x) for x in line.split()[1:3]])
        elif line.startswith("g ") or line.startswith("o "):
            group = line.split(None, 1)[1].strip()
        elif line.startswith("usemtl"):
            pass
        elif line.startswith("f "):
            vi, ti = [], []
            for tok in line.split()[1:]:
                p = tok.split("/")
                vi.append(int(p[0]) - 1)
                ti.append(int(p[1]) - 1 if len(p) > 1 and p[1] else -1)
            faces.append((vi, ti, group))
            groups.setdefault(group, set()).update(vi)
    return np.array(v, dtype=np.float64), np.array(vt, dtype=np.float64) if vt else np.zeros((0, 2)), faces, groups


def read_target(path, nverts):
    """Țintă .target: 'index dx dy dz' pe rând -> (indici, deplasări)."""
    idx, d = [], []
    for line in open(path, encoding="utf-8", errors="replace"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        p = line.split()
        if len(p) < 4:
            continue
        i = int(p[0])
        if i < nverts:
            idx.append(i); d.append([float(p[1]), float(p[2]), float(p[3])])
    return np.array(idx, dtype=np.int64), np.array(d, dtype=np.float64).reshape(-1, 3)


def dense_target(path, nverts):
    i, d = read_target(path, nverts)
    out = np.zeros((nverts, 3)); out[i] = d
    return out


def read_mhclo(path):
    """Haină / păr MakeHuman: legarea fiecărui vârf al hainei de 3 vârfuri ale corpului.
    Întoarce dict cu: refs (K,3) int, weights (K,3), offsets (K,3), scale refs, obj file, material, z_depth, delete_verts."""
    out = {"refs": [], "weights": [], "offsets": [], "scale": {}, "obj": None, "material": None, "z_depth": 50,
           "delete_verts": [], "name": None, "tags": [], "offset_scale": None}
    mode, seen_verts = None, False      # după „verts” pot apărea și alte chei (ex. material) înaintea vârfurilor
    for raw in open(path, encoding="utf-8", errors="replace"):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        p = line.split()
        key = p[0].lower()
        if mode != "delete" and seen_verts and re.match(r"^-?\d", p[0]) and len(p) in (1, 9):
            if len(p) == 1:
                out["refs"].append([int(p[0])] * 3); out["weights"].append([1, 0, 0]); out["offsets"].append([0, 0, 0])
            else:
                out["refs"].append([int(p[0]), int(p[1]), int(p[2])])
                out["weights"].append([float(p[3]), float(p[4]), float(p[5])])
                out["offsets"].append([float(p[6]), float(p[7]), float(p[8])] if len(p) >= 9 else [0, 0, 0])
            continue
        if mode == "delete" and re.match(r"^\d", p[0]):
            toks = " ".join(p).replace(" - ", "-").split()          # „1355 - 1388 1393” -> intervale
            for tok in toks:
                if "-" in tok:
                    a, b = tok.split("-"); out["delete_verts"].extend(range(int(a), int(b) + 1))
                else:
                    out["delete_verts"].append(int(tok))
            continue
        mode = None
        if key == "verts":
            mode = "verts"; seen_verts = True
        elif key == "delete_verts":
            mode = "delete"
        elif key == "obj_file":
            out["obj"] = p[1]
        elif key == "material":
            out["material"] = p[1]
        elif key == "name":
            out["name"] = p[1]
        elif key == "tag":
            out["tags"].append(" ".join(p[1:]).lower())
        elif key == "z_depth":
            out["z_depth"] = int(p[1])
        elif key in ("x_scale", "y_scale", "z_scale"):
            out["scale"][key[0]] = (int(p[1]), int(p[2]), float(p[3]))
    for k in ("refs", "weights", "offsets"):
        out[k] = np.array(out[k], dtype=np.float64 if k != "refs" else np.int64)
    return out


def read_mhmat(path):
    """Material MakeHuman: texturi (diffuse, normal, transparency) și culori."""
    m = {}
    for line in open(path, encoding="utf-8", errors="replace"):
        p = line.strip().split(None, 1)
        if len(p) == 2 and not p[0].startswith("#"):
            m[p[0]] = p[1].strip()
    return m


def fit_proxy(clo, body_v, base_v=None):
    """Poziția vârfurilor hainei pe corpul dat (ca în MakeHuman: baricentric + offset scalat)."""
    r, w, o = clo["refs"], clo["weights"], clo["offsets"]
    pos = (body_v[r[:, 0]] * w[:, :1] + body_v[r[:, 1]] * w[:, 1:2] + body_v[r[:, 2]] * w[:, 2:3])
    s = np.ones(3)
    for ax, j in (("x", 0), ("y", 1), ("z", 2)):
        if ax in clo["scale"]:
            a, b, ref = clo["scale"][ax]
            s[j] = abs(body_v[a][j] - body_v[b][j]) / ref if ref else 1
    return pos + o * s


def read_skeleton():
    sk = json.load(open(MH / "rigs" / "default.mhskel", encoding="utf-8"))
    wt = json.load(open(MH / "rigs" / "default_weights.mhw", encoding="utf-8"))
    return sk, wt["weights"]
