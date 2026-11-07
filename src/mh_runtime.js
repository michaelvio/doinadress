// ------------------------------------------------------------------ corp 3D realist: MakeHuman (CC0), deformat după măsuri, cu haine reale
// Pachetul (build_cache/mh.pack, construit de src/mh_build.py) conține corpul, țintele de deformare, hainele și părul.
// Totul se calculează în decimetri (unitatea MakeHuman), apoi se trece în metri (× 0.1).
const MH = { ok: false, off: /*MHOFF*/false, err: null, T: {}, G: {}, H: {}, tex: new Map() };
async function loadMH() {
  try {
    if (MH.off) throw new Error('varianta simplă (fără corpul MakeHuman)');
    const src = /*MHPACK*/null;
    if (!src && location.protocol === 'file:') throw new Error('pachetul 3D lipsește');
    const ab = await (await fetch(src ? 'data:application/octet-stream;base64,' + src : 'mh.pack')).arrayBuffer();
    const dv = new DataView(ab);
    if (dv.getUint32(0, true) !== 0x4b50484d) throw new Error('pachet 3D invalid');
    const jl = dv.getUint32(4, true), J = JSON.parse(new TextDecoder().decode(new Uint8Array(ab, 8, jl)));
    const base = 8 + jl + ((4 - (8 + jl) % 4) % 4);
    const TY = { float32: Float32Array, uint16: Uint16Array, int16: Int16Array, uint8: Uint8Array, uint32: Uint32Array };
    const A = d => new TY[d.t](ab, base + d.o, d.n);
    const blob = d => new Blob([new Uint8Array(ab, base + d.o, d.n)], { type: d.mime });
    const b = J.body;
    Object.assign(MH, { nv: b.nv, nb: b.nb, base: A(b.v), rmap: A(b.rmap), uv: A(b.uv), idx: A(b.idx), eyeRmap: A(b.eye.rmap), eyeIdx: A(b.eye.idx),
      faceTris: A(b.faceTris), armL: A(b.armL), armR: A(b.armR), lowL: A(b.lowL), lowR: A(b.lowR), joints: b.joints, eyeL: b.eyeL, eyeR: b.eyeR, measures: b.measures });
    for (const [k, t] of Object.entries(J.targets)) {          // ținte rare -> dense (Float32, dm)
      const i = A(t.i), d = A(t.d), D = new Float32Array(MH.nv * 3);
      for (let n = 0; n < i.length; n++) { const o = i[n] * 3; D[o] = d[n * 3] * 1e-3; D[o + 1] = d[n * 3 + 1] * 1e-3; D[o + 2] = d[n * 3 + 2] * 1e-3; }
      MH.T[k] = D;
    }
    const proxy = r => ({ nv: r.nv, refs: A(r.refs), w: A(r.w), off: A(r.off), scale: r.scale, rmap: A(r.rmap), uv: A(r.uv), idx: A(r.idx),
      del: A(r.del), cov: A(r.cov), z: r.z, muv: r.muv, detail: r.detail && blob(r.detail), normal: r.normal && blob(r.normal), tex: r.tex && blob(r.tex) });
    for (const [k, r] of Object.entries(J.garments)) MH.G[k] = proxy(r);
    for (const [k, r] of Object.entries(J.hair)) MH.H[k] = proxy(r);
    // texturile se decodează dinainte, ca primele imagini (și miniaturile din catalog) să fie complete
    const all = [...Object.values(MH.G), ...Object.values(MH.H)].flatMap(P => [P.detail, P.normal, P.tex]).filter(Boolean);
    await Promise.all(all.map(b => mhTex(b, false).userData.ready));
    MH.ok = true;
  } catch (e) { MH.err = e.message; if (!MH.off) console.warn('corp 3D realist indisponibil:', e); }
}
// texturile din pachet (decodate o singură dată)
function mhTex(blob, srgb = false, key) {
  if (!blob) return null;
  if (!MH.tex.has(blob)) {
    const tex = new THREE.Texture(); tex.flipY = false;
    tex.wrapS = tex.wrapT = THREE.RepeatWrapping; tex.anisotropy = MAX_ANISO;
    if (srgb) tex.colorSpace = THREE.SRGBColorSpace;
    tex.userData.ready = createImageBitmap(blob, { imageOrientation: 'flipY' }).then(bm => { tex.image = bm; tex.needsUpdate = true; invalidate(); }).catch(() => {});
    MH.tex.set(blob, tex);
  }
  return MH.tex.get(blob);
}

const MH_GARMENT = {
  top: { tricou: g => g === 'f' ? 'tricou_f' : 'tricou_m', bluza: 'camasa', camasa: 'camasa', polo: 'polo', helanca: 'pulover', pulover: 'pulover' },
  bottom: { pantaloni: 'pantaloni', blugi: 'blugi', scurti: 'scurti', fusta: 'fusta', fusta_lunga: 'fusta_lunga' },
  dress: { rochie: 'rochie', rochie_scurta: 'rochie_scurta', rochie_lunga: 'rochie_lunga', sarafan: 'sarafan' },
  outer: { geaca: 'geaca', hanorac: 'geaca', vesta: 'vesta', sacou: g => g === 'f' ? 'sacou_f' : 'sacou_m', palton: g => g === 'f' ? 'palton_f' : 'palton_m' },
  shoes: { pantofi: g => g === 'f' ? 'pantofi_f' : 'pantofi_m', adidasi: 'adidasi', cizme: g => g === 'f' ? 'cizme_f' : 'cizme_m', balerini: 'balerini', toc: 'toc', sandale: 'sandale' },
};
const MH_LAYER = { bottom: .02, top: .05, dress: .07, outer: .14, shoes: 0 };     // dm: straturile exterioare puțin mai departe de corp
const MH_ORDER = { bottom: 0, top: 1, dress: 1.5, outer: 2, shoes: 0 };          // ordinea straturilor (cine acoperă pe cine)
const mhGarmentId = (slot, it, a) => { const m = MH_GARMENT[slot]?.[it.type]; return typeof m === 'function' ? m(a.gen) : m; };

// --- măsurarea unei bucle MakeHuman (perimetru, dm)
function mhMeasure(V, name, add, w) {
  const L = MH.measures[name]; let s = 0;
  const P = i => add ? [V[i * 3] + add[i * 3] * w, V[i * 3 + 1] + add[i * 3 + 1] * w, V[i * 3 + 2] + add[i * 3 + 2] * w] : [V[i * 3], V[i * 3 + 1], V[i * 3 + 2]];
  let p = P(L[0]);
  for (let k = 1; k < L.length; k++) { const q = P(L[k]); s += Math.hypot(q[0] - p[0], q[1] - p[1], q[2] - p[2]); p = q; }
  return s;
}
const addT = (V, T, w) => { if (!T || !w) return; for (let i = 0; i < V.length; i++) V[i] += T[i] * w; };
function mhHeight(V) { let lo = 1e9, hi = -1e9; for (let i = 0; i < MH.nb; i++) { const y = V[i * 3 + 1]; if (y < lo) lo = y; if (y > hi) hi = y; } return [lo, hi]; }
function jointPos(V, name) {
  const L = MH.joints[name], p = [0, 0, 0];
  for (const i of L) { p[0] += V[i * 3]; p[1] += V[i * 3 + 1]; p[2] += V[i * 3 + 2]; }
  return p.map(x => x / L.length);
}

// --- corpul: gen + vârstă, greutate, măsuri (bust/talie/șold), înălțime, brațele coborâte
function mhBodyShape(a) {
  const g = a.gen === 'f' ? 'female' : 'male', V = Float32Array.from(MH.base), b = a.body;
  const ages = a.varsta === 'copil' ? { child: 1 } : a.varsta === 'adolescent' ? { child: .45, young: .55 } : { young: 1 };
  for (const [ag, w] of Object.entries(ages)) addT(V, MH.T[`${g}-${ag}`], w);
  const T = (n, ag) => MH.T[`${g}-${ag}-${n}`];
  const [lo0, hi0] = mhHeight(V);
  let s = (b.height / 10) / (hi0 - lo0);                     // dm țintă / dm actual
  const want = { bust: b.chest / 10 / s, waist: b.waist / 10 / s, hips: b.hips / 10 / s };
  // 1) greutatea generală (după talie), 2) bust / talie / șold, de două ori pentru interacțiuni
  const solve = (name, inc, dec, lim = 1.6) => {
    const c0 = mhMeasure(V, name), d = want[name] - c0;
    const T1 = d >= 0 ? inc : dec; if (!T1) return 0;
    const dc = mhMeasure(V, name, T1, 1) - c0; if (Math.abs(dc) < 1e-4) return 0;
    const w = clamp(d / dc, 0, lim); addT(V, T1, w); return w;
  };
  for (const [ag, aw] of Object.entries(ages)) {
    const c0 = mhMeasure(V, 'waist'), d = want.waist - c0, Tw = d >= 0 ? T('maxweight', ag) : T('minweight', ag);
    const dc = mhMeasure(V, 'waist', Tw, 1) - c0; if (Math.abs(dc) > 1e-4) addT(V, Tw, clamp(d / dc, 0, 1) * aw * .7);
  }
  for (let it = 0; it < 2; it++) {
    solve('bust', MH.T['bust-incr'], MH.T['bust-decr']);
    solve('hips', MH.T['hips-incr'], MH.T['hips-decr']);
    solve('waist', MH.T['waist-incr'], MH.T['waist-decr']);
  }
  const [lo, hi] = mhHeight(V); s = (b.height / 10) / (hi - lo);
  for (let i = 0; i < V.length; i += 3) { V[i] *= s; V[i + 1] = (V[i + 1] - lo) * s; V[i + 2] *= s; }
  // brațele: din poziția „A” (~45°) aproape lipite de corp (~11°), rotind în jurul umărului cu unghi ponderat
  // (1) tot brațul în jurul umărului, (2) antebrațul în jurul cotului, ca brațul să atârne aproape drept
  const rot = (W, piv, phi) => {
    for (let i = 0; i < MH.nv; i++) {
      const w = W[i] / 255; if (!w) continue;
      const an = phi * w, c = Math.cos(an), sn = Math.sin(an), o = i * 3;
      const x = V[o] - piv[0], y = V[o + 1] - piv[1];
      V[o] = piv[0] + x * c - y * sn; V[o + 1] = piv[1] + x * sn + y * c;
    }
  };
  const ang = (p, q, sx) => Math.atan2(sx * (q[0] - p[0]), p[1] - q[1]);       // unghiul față de verticală, spre exterior
  for (const [side, W, Wl, sx] of [['L', MH.armL, MH.lowL, 1], ['R', MH.armR, MH.lowR, -1]]) {
    const sh = jointPos(V, `upperarm01.${side}____head`), el = jointPos(V, `lowerarm01.${side}____head`);
    rot(W, sh, -(ang(sh, el, sx) - .1) * sx);                                   // brațul: ~6° față de corp
    const el2 = jointPos(V, `lowerarm01.${side}____head`), wr = jointPos(V, `wrist.${side}____head`);
    rot(Wl, el2, -(ang(el2, wr, sx) - .16) * sx);                              // antebrațul: ~9°, ușor depărtat de șold
  }
  return V;
}
// --- poziția unei haine / a părului pe corp (legare baricentrică MakeHuman + offset scalat)
function mhFitProxy(P, V, inflate = 0) {
  const out = new Float32Array(P.nv * 3), sc = [1, 1, 1];
  for (const [ax, j] of [['x', 0], ['y', 1], ['z', 2]]) {
    const s = P.scale[ax]; if (s) sc[j] = Math.abs(V[s[0] * 3 + j] - V[s[1] * 3 + j]) / s[2];
  }
  for (let i = 0; i < P.nv; i++) {
    const r0 = P.refs[i * 3] * 3, r1 = P.refs[i * 3 + 1] * 3, r2 = P.refs[i * 3 + 2] * 3;
    const w0 = P.w[i * 3], w1 = P.w[i * 3 + 1], w2 = P.w[i * 3 + 2];
    for (let j = 0; j < 3; j++) out[i * 3 + j] = V[r0 + j] * w0 + V[r1 + j] * w1 + V[r2 + j] * w2 + P.off[i * 3 + j] * 1e-3 * sc[j];
  }
  if (inflate) {                                   // haina mai largă / mai strâmtă: deplasare pe normală
    const n = vertexNormals(out, P.idx, P.rmap, P.nv);
    for (let i = 0; i < out.length; i++) out[i] += n[i] * inflate;
  }
  return out;
}
// normale netede pe vârfurile reale (nu pe cele dublate la cusăturile UV), ca să nu apară dungi de lumină
function vertexNormals(Vu, idx, rmap, nu) {
  const N = new Float32Array(nu * 3);
  for (let t = 0; t < idx.length; t += 3) {
    const a = rmap[idx[t]] * 3, b = rmap[idx[t + 1]] * 3, c = rmap[idx[t + 2]] * 3;
    const ux = Vu[b] - Vu[a], uy = Vu[b + 1] - Vu[a + 1], uz = Vu[b + 2] - Vu[a + 2];
    const vx = Vu[c] - Vu[a], vy = Vu[c + 1] - Vu[a + 1], vz = Vu[c + 2] - Vu[a + 2];
    const nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
    for (const k of [a, b, c]) { N[k] += nx; N[k + 1] += ny; N[k + 2] += nz; }
  }
  for (let i = 0; i < N.length; i += 3) { const l = Math.hypot(N[i], N[i + 1], N[i + 2]) || 1; N[i] /= l; N[i + 1] /= l; N[i + 2] /= l; }
  return N;
}
// geometrie three.js din vârfurile reale + harta de randare (vârfuri dublate la cusăturile UV), în metri
function mhGeometry(Vu, rmap, uv, idx, nu, keepTri) {
  const n = rmap.length, pos = new Float32Array(n * 3), nor = new Float32Array(n * 3), N = vertexNormals(Vu, idx, rmap, nu);
  for (let i = 0; i < n; i++) { const o = rmap[i] * 3; for (let j = 0; j < 3; j++) { pos[i * 3 + j] = Vu[o + j] * .1; nor[i * 3 + j] = N[o + j]; } }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  g.setAttribute('normal', new THREE.BufferAttribute(nor, 3));
  if (uv) g.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
  let I = idx;
  if (keepTri) { const k = []; for (let t = 0; t < idx.length; t += 3) if (keepTri(t)) k.push(idx[t], idx[t + 1], idx[t + 2]); I = k; }
  g.setIndex(Array.isArray(I) ? I : Array.from(I));
  return g;
}
// materialul unei haine reale: culoarea / desenul produsului + relieful hainei (cute, cusături) + normalele ei
const scaledTexCache = new Map();
function scaledTex(tex, k) {
  if (!tex || k === 1) return tex;
  const key = tex.uuid + '|' + k;
  if (!scaledTexCache.has(key)) { const t = tex.clone(); t.repeat.set(tex.repeat.x * k, tex.repeat.y * k); t.needsUpdate = true; scaledTexCache.set(key, t); }
  return scaledTexCache.get(key);
}
function mhClothMat(it, P) {
  const m = itemMat(it);
  if (m.map) m.map = scaledTex(m.map, P.muv);
  const own = mhTex(P.normal);
  if (own) { m.normalMap = own; m.normalScale = new THREE.Vector2(.9, .9); }
  else if (m.normalMap) m.normalMap = scaledTex(m.normalMap, P.muv);
  const det = mhTex(P.detail);
  if (det) {                     // relieful hainei înmulțit peste culoarea produsului (aoMap e doar purtătorul texturii)
    m.aoMap = det; m.aoMapIntensity = 0;
    m.onBeforeCompile = sh => { sh.fragmentShader = sh.fragmentShader.replace('#include <map_fragment>',
      '#include <map_fragment>\n  diffuseColor.rgb *= clamp( texture2D( aoMap, vAoMapUv ).r * 2.0, 0.25, 1.35 );'); };
    m.customProgramCacheKey = () => 'mhdetail';
  }
  m.side = THREE.DoubleSide;
  return m;
}

function buildAvatarMH(a) {
  const root = new THREE.Group();
  const add = m => { m.castShadow = m.receiveShadow = true; root.add(m); return m; };
  const V = mhBodyShape(a), o = a.outfit;
  const fits = {}; SLOTS.forEach(s => fits[s] = fitOf(s, o[s], a));
  // hainele purtate (cu rochia completă nu există bluză / pantaloni — vezi putItem)
  const worn = [];
  for (const s of ['bottom', 'top', 'dress', 'outer', 'shoes']) {
    const it = o[s]; if (!it) continue;
    const id = mhGarmentId(s, it, a), P = id && MH.G[id]; if (!P) continue;
    const f = fits[s], ease = s === 'shoes' ? 0 : clamp((f.d ?? 0) / TAU, -.4, 2.4) / 10;    // cm de circumferință -> dm pe rază
    worn.push({ s, it, P, inflate: MH_LAYER[s] + Math.max(ease, -.02) });
  }
  // corpul fără zonele acoperite complet de haine (nu „străpunge” materialul)
  const hidden = new Uint8Array(MH.nv);
  for (const w of worn) for (const v of w.P.del) hidden[v] = 1;
  const skinMat = new THREE.MeshStandardMaterial({ color: new THREE.Color(a.skin).multiplyScalar(a.faceAdj.bright), roughness: .5 });
  // scalpul de sub păr se colorează ca părul (printre șuvițe nu se vede pielea)
  const HPs = MH.H[a.hair.style], scalp = new Uint8Array(MH.nv);
  if (HPs) for (const v of HPs.cov) scalp[v] = 1;
  const isScalp = t => scalp[MH.rmap[MH.idx[t]]] && scalp[MH.rmap[MH.idx[t + 1]]] && scalp[MH.rmap[MH.idx[t + 2]]];
  const vis = t => !(hidden[MH.rmap[MH.idx[t]]] || hidden[MH.rmap[MH.idx[t + 1]]] || hidden[MH.rmap[MH.idx[t + 2]]]);
  add(new THREE.Mesh(mhGeometry(V, MH.rmap, MH.uv, MH.idx, MH.nv, t => vis(t) && !isScalp(t)), skinMat));
  if (HPs) add(new THREE.Mesh(mhGeometry(V, MH.rmap, MH.uv, MH.idx, MH.nv, t => vis(t) && isScalp(t)),
    new THREE.MeshStandardMaterial({ color: new THREE.Color(a.hair.color).multiplyScalar(.8), roughness: .8 })));
  add(new THREE.Mesh(mhGeometry(V, MH.eyeRmap, null, MH.eyeIdx, MH.nv), a.face ? skinMat : new THREE.MeshStandardMaterial({ color: '#f2efe9', roughness: .3 })));
  // fața din fotografie, proiectată din față pe cap (aliniată după centrele ochilor)
  const tex = faceTex(a);
  if (tex) {
    const eL = MH.eyeL.reduce((p, i) => [p[0] + V[i * 3], p[1] + V[i * 3 + 1], p[2] + V[i * 3 + 2]], [0, 0, 0]).map(x => x / MH.eyeL.length);
    const eR = MH.eyeR.reduce((p, i) => [p[0] + V[i * 3], p[1] + V[i * 3 + 1], p[2] + V[i * 3 + 2]], [0, 0, 0]).map(x => x / MH.eyeR.length);
    const De = Math.hypot(eL[0] - eR[0], eL[1] - eR[1]) * (a.faceAdj.scale || 1), cx = (eL[0] + eR[0]) / 2, cy = (eL[1] + eR[1]) / 2 + (a.faceAdj.dy || 0) * .1;
    const fr = [...MH.faceTris];
    const tris = []; fr.forEach(t => tris.push(MH.idx[t * 3], MH.idx[t * 3 + 1], MH.idx[t * 3 + 2]));
    const used = [...new Set(tris)], loc = new Map(used.map((r, k) => [r, k]));
    const n = used.length, pos = new Float32Array(n * 3), uvA = new Float32Array(n * 2);
    for (let k = 0; k < n; k++) {
      const vi = MH.rmap[used[k]] * 3, x = V[vi], y = V[vi + 1], z = V[vi + 2];
      pos[k * 3] = x * .1; pos[k * 3 + 1] = y * .1; pos[k * 3 + 2] = z * .1;
      uvA[k * 2] = .5 + (x - cx) / (2.6 * De);
      uvA[k * 2 + 1] = (1 - EYE_Y) + (y - cy) / (2.6 * De * FH / FW);
    }
    // ochii: aceeași proiecție, ca privirea din poză să stea pe globii oculari
    const eT = []; const eLoc = new Map(); let ne = n;
    const extra = [];
    for (let t = 0; t < MH.eyeIdx.length; t++) { const r = MH.eyeRmap[MH.eyeIdx[t]]; if (!eLoc.has(r)) { eLoc.set(r, ne++); extra.push(r); } eT.push(eLoc.get(r)); }
    const pos2 = new Float32Array(ne * 3), uv2 = new Float32Array(ne * 2); pos2.set(pos); uv2.set(uvA);
    const col = new Float32Array(ne * 4).fill(1);
    const fade = (k, x, y) => {                   // linia părului (~0.9 × distanța dintre ochi peste ochi) și lateral spre urechi
      const up = smooth(.62 * De, .95 * De, y - cy), side = smooth(1.05 * De, 1.4 * De, Math.abs(x - cx));
      col[k * 4 + 3] = (1 - up) * (1 - side);
    };
    for (let k = 0; k < n; k++) { const vi = MH.rmap[used[k]] * 3; fade(k, V[vi], V[vi + 1]); }
    extra.forEach((r, k) => { const vi = r * 3, x = V[vi], y = V[vi + 1], z = V[vi + 2], q = n + k;
      pos2[q * 3] = x * .1; pos2[q * 3 + 1] = y * .1; pos2[q * 3 + 2] = z * .1;
      uv2[q * 2] = .5 + (x - cx) / (2.6 * De); uv2[q * 2 + 1] = (1 - EYE_Y) + (y - cy) / (2.6 * De * FH / FW); });
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(pos2, 3)); g.setAttribute('uv', new THREE.BufferAttribute(uv2, 2));
    g.setAttribute('color', new THREE.BufferAttribute(col, 4));
    g.setIndex([...tris.map(r => loc.get(r)), ...eT]); g.computeVertexNormals();
    const fm = new THREE.MeshStandardMaterial({ map: tex, transparent: true, vertexColors: true, roughness: .55, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 });
    const fmesh = new THREE.Mesh(g, fm); fmesh.renderOrder = 2; root.add(fmesh);
  }
  // haine: părțile unei haine acoperite complet de un strat exterior nu se desenează (altfel ar „străpunge” materialul)
  for (const w of worn) {
    const cov = new Uint8Array(MH.nv);
    for (const o2 of worn) if (MH_ORDER[o2.s] > MH_ORDER[w.s] && o2.s !== 'shoes') for (const v of o2.P.cov) cov[v] = 1;
    const P = w.P, vc = new Uint8Array(P.nv);
    for (let i = 0; i < P.nv; i++) {
      let all = true;
      for (let k = 0; k < 3; k++) { const r = P.refs[i * 3 + k]; if (Math.abs(P.w[i * 3 + k]) > .05 && !cov[r]) { all = false; break; } }
      vc[i] = all ? 1 : 0;
    }
    const keep = t => !(vc[P.rmap[P.idx[t]]] && vc[P.rmap[P.idx[t + 1]]] && vc[P.rmap[P.idx[t + 2]]]);
    const pos = mhFitProxy(P, V, w.inflate);
    const mesh = add(new THREE.Mesh(mhGeometry(pos, P.rmap, P.uv, P.idx, P.nv, keep), w.s === 'shoes' ? mhShoeMat(w.it, P) : mhClothMat(w.it, P)));
    mesh.renderOrder = 1;
  }
  // păr
  const hs = a.hair.style, HP = MH.H[hs];
  if (HP) {
    const pos = mhFitProxy(HP, V, .02), ht = mhTex(HP.tex);
    const hm = new THREE.MeshStandardMaterial({ color: new THREE.Color(a.hair.color).multiplyScalar(1.35), map: ht, alphaTest: .5, roughness: .6,
      side: THREE.DoubleSide, envMapIntensity: .35 });
    add(new THREE.Mesh(mhGeometry(pos, HP.rmap, HP.uv, HP.idx, HP.nv), hm));
  }
  // accesorii și geantă: aceleași piese ca la corpul simplu, mutate pe capul / umerii corpului realist
  const acc = buildAvatar(a, { accOnly: true });
  if (acc) {
    const D = dims(a), eyeY = (MH.eyeL.reduce((p, i) => p + V[i * 3 + 1], 0) / MH.eyeL.length) * .1;
    for (const ch of [...acc.children]) {
      if (ch.userData.head) ch.position.y += eyeY - (D.yHeadC + D.hh * .02) * S;
      root.add(ch);
    }
  }
  // tălpile pe podea (pantofi cu toc sau fără)
  const bb = new THREE.Box3().setFromObject(root);
  root.userData.lift = -bb.min.y / S;
  return root;
}
function mhShoeMat(it, P) {
  const m = new THREE.MeshStandardMaterial({ color: it.color, roughness: .42, metalness: .05, side: THREE.DoubleSide });
  const own = mhTex(P.normal); if (own) m.normalMap = own;
  const det = mhTex(P.detail);
  if (det) {
    m.aoMap = det; m.aoMapIntensity = 0;
    m.onBeforeCompile = sh => { sh.fragmentShader = sh.fragmentShader.replace('#include <map_fragment>',
      '#include <map_fragment>\n  diffuseColor.rgb *= clamp( texture2D( aoMap, vAoMapUv ).r * 2.0, 0.25, 1.35 );'); };
    m.customProgramCacheKey = () => 'mhdetail';
  }
  return m;
}
