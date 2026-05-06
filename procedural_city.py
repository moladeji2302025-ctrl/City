"""
procedural_city.py
==================
Optimized Maya procedural city generator.

Performance optimizations implemented:
- Reduced master city size presets via CITY_SIZE ("small"/"tiny"/"test")
- 5x5 default grid (down from the larger 12x12 variant)
- Asset instancing for repeated objects (windows, trees, cars, traffic lights,
  and street furniture)
- Lower-poly repeated assets (trees, cars, roof details, crane)
- Road-marking batching (combined per-road/per-intersection meshes)
- Viewport suspension during generation via cmds.refresh(suspend=True)
- Progress prints every 20%
- Material reuse cache (no duplicate shaders)
- QUALITY slider ("medium" / "low")
- Periodic cmds.cleanupScene() calls

Run in Maya Script Editor (Python tab).

WARNING:
This script starts by running cmds.file(newFile=True, force=True), which
clears the current Maya scene without prompting to save.
"""

import random
import maya.cmds as cmds


# -----------------------------------------------------------------------------
# GLOBAL SETTINGS
# -----------------------------------------------------------------------------
random.seed(42)
QUALITY = "medium"  # "medium" or "low"
CITY_SIZE = "small"  # "small"=5x5, "tiny"=3x3, "test"=2x2

BLOCK_SIZE = 50
ROAD_W = 8
SW_W = 2
STREET_MOD = ROAD_W + SW_W * 2
MODULE = BLOCK_SIZE + STREET_MOD

# Changed from the previous larger-grid version:
# use a master size preset so city footprint and dependent counts scale together.
_CITY_SIZE_PRESETS = {"small": 5, "tiny": 3, "test": 2}
N = _CITY_SIZE_PRESETS.get(CITY_SIZE.lower(), _CITY_SIZE_PRESETS["small"])
CITY_SZ = N * MODULE + STREET_MOD
OX = -CITY_SZ / 2.0
OZ = -CITY_SZ / 2.0
MASTER = "Procedural_City"

# Changed from the larger version:
# lower in-block density while preserving style/entrance/window/roof systems.
SUBDIV = 6
CELL_SZ = BLOCK_SIZE / float(SUBDIV)
BUILDINGS_PER_BLOCK_MIN = 6
BUILDINGS_PER_BLOCK_MAX = 10
TREES_PER_BLOCK_MIN = 8
TREES_PER_BLOCK_MAX = 12

# Related counts scale with CITY_SIZE footprint (5x5 baseline == 1.0).
# For CITY_SIZE="small" this yields:
# - billboards: 10-15 (was 30 in the larger 12x12 version)
# - cars: 50-75 (was 150-200)
# - cranes: 3-4 (was 8)
_CITY_SCALE = float(N * N) / 25.0  # 25.0 = 5x5 baseline grid area
BILLBOARD_COUNT_MIN = max(2, int(round(10 * _CITY_SCALE)))
BILLBOARD_COUNT_MAX = max(BILLBOARD_COUNT_MIN, int(round(15 * _CITY_SCALE)))
CAR_COUNT_MIN = max(8, int(round(50 * _CITY_SCALE)))
CAR_COUNT_MAX = max(CAR_COUNT_MIN, int(round(75 * _CITY_SCALE)))
CRANE_COUNT_MIN = max(1, int(round(3 * _CITY_SCALE)))
CRANE_COUNT_MAX = max(CRANE_COUNT_MIN, int(round(4 * _CITY_SCALE)))

# Window/roof complexity switches for QUALITY
LOW_QUALITY = QUALITY.lower() == "low"
WINDOW_DEPTH = 0.01 if LOW_QUALITY else 0.08
ENABLE_ROOF_DETAILS = not LOW_QUALITY


# -----------------------------------------------------------------------------
# HELPERS
# -----------------------------------------------------------------------------
_cnt = [0]
_mats = {}
_groups = {}
_prototypes = {}
_entrances = []


def uid(prefix):
    _cnt[0] += 1
    return "{}_{:05d}".format(prefix, _cnt[0])


def blk_ox(i):
    return OX + i * MODULE + STREET_MOD


def blk_oz(j):
    return OZ + j * MODULE + STREET_MOD


def blk_cx(i):
    return blk_ox(i) + BLOCK_SIZE * 0.5


def blk_cz(j):
    return blk_oz(j) + BLOCK_SIZE * 0.5


def road_cx(col):
    return OX + col * MODULE + STREET_MOD * 0.5


def road_cz(row):
    return OZ + row * MODULE + STREET_MOD * 0.5


def mkbox(prefix, cx, by, cz, w, h, d, ry=0):
    o = cmds.polyCube(w=w, h=h, d=d, sx=1, sy=1, sz=1, name=uid(prefix))[0]
    cmds.move(cx, by + h * 0.5, cz, o)
    if ry:
        cmds.rotate(0, ry, 0, o, r=True)
    return o


def mkcyl(prefix, cx, by, cz, r, h, ry=0, rz=0, sx=6):
    # Low segment count for repeated geometry
    o = cmds.polyCylinder(r=r, h=h, sx=sx, sy=1, sz=1, name=uid(prefix))[0]
    cmds.move(cx, by + h * 0.5, cz, o)
    if ry:
        cmds.rotate(0, ry, 0, o, r=True)
    if rz:
        cmds.rotate(0, 0, rz, o, r=True)
    return o


def mksph(prefix, cx, cy, cz, r, sx=6, sy=4):
    o = cmds.polySphere(r=r, sx=sx, sy=sy, name=uid(prefix))[0]
    cmds.move(cx, cy, cz, o)
    return o


def combine(objs, prefix):
    valid = [o for o in objs if o and cmds.objExists(o)]
    if not valid:
        return None
    if len(valid) == 1:
        return valid[0]
    return cmds.polyUnite(valid, ch=False, mergeUVSets=True, name=uid(prefix))[0]


def ensure_material(name, color, typ="lambert", spec=None):
    if name in _mats:
        return _mats[name]
    mat = cmds.shadingNode(typ, asShader=True, name=name)
    cmds.setAttr(mat + ".color", color[0], color[1], color[2], type="double3")
    if typ == "phong" and spec:
        cmds.setAttr(mat + ".specularColor", spec[0], spec[1], spec[2], type="double3")
        cmds.setAttr(mat + ".cosinePower", 20)
    sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=name + "_SG")
    cmds.connectAttr(mat + ".outColor", sg + ".surfaceShader", force=True)
    _mats[name] = sg
    return sg


def assign(mat, obj):
    sg = _mats.get(mat)
    if sg and obj and cmds.objExists(obj):
        cmds.sets(obj, edit=True, forceElement=sg)


def get_group(name):
    if name not in _groups:
        g = cmds.group(em=True, name=name)
        cmds.parent(g, MASTER)
        _groups[name] = g
    return _groups[name]


def put(objs, group_name):
    if not objs:
        return
    g = get_group(group_name)
    for o in objs:
        if o and cmds.objExists(o):
            cmds.parent(o, g)


def periodic_cleanup(label):
    try:
        cmds.cleanupScene()
        print("  cleanupScene() called after {}".format(label))
    except Exception:
        pass


def progress(pct, label):
    print("[Progress] {}% - {}".format(pct, label))


def register_prototype(name, obj):
    _prototypes[name] = obj
    cmds.parent(obj, get_group("Grp_Prototypes"))
    cmds.setAttr(obj + ".visibility", 0)


def instance_proto(name, cx, by, cz, ry=0, scale=(1, 1, 1), parent_group=None):
    inst = cmds.instance(_prototypes[name], name=uid(name + "_i"))[0]
    cmds.move(cx, by, cz, inst, absolute=True)
    if ry:
        cmds.rotate(0, ry, 0, inst, r=True)
    if scale != (1, 1, 1):
        cmds.scale(scale[0], scale[1], scale[2], inst, absolute=True)
    if parent_group:
        cmds.parent(inst, get_group(parent_group))
    return inst


# -----------------------------------------------------------------------------
# MATERIALS (reused)
# -----------------------------------------------------------------------------
def create_materials():
    ensure_material("asphalt", (0.15, 0.15, 0.15))
    ensure_material("concrete", (0.50, 0.50, 0.50))
    ensure_material("sidewalk", (0.73, 0.71, 0.65))
    ensure_material("rdline", (0.95, 0.95, 0.85))
    ensure_material("crsswlk", (0.88, 0.88, 0.78))

    ensure_material("stone", (0.60, 0.55, 0.50))
    ensure_material("brick", (0.68, 0.33, 0.20))
    ensure_material("metal", (0.62, 0.65, 0.70), "phong", (0.28, 0.28, 0.28))
    ensure_material("glass", (0.42, 0.62, 0.85), "phong", (0.50, 0.50, 0.50))
    ensure_material("glassd", (0.20, 0.30, 0.45), "phong", (0.35, 0.35, 0.35))
    ensure_material("dark", (0.10, 0.10, 0.12))
    ensure_material("white", (0.90, 0.90, 0.90))

    for n, c in {
        "bb_beige": (0.85, 0.80, 0.68),
        "bb_cream": (0.92, 0.90, 0.78),
        "bb_gray": (0.60, 0.63, 0.67),
        "bb_bronze": (0.65, 0.50, 0.30),
        "bb_blue": (0.32, 0.48, 0.68),
        "bb_terra": (0.72, 0.38, 0.26),
        "bb_olive": (0.52, 0.56, 0.38),
        "bb_charcoal": (0.26, 0.28, 0.30),
    }.items():
        ensure_material(n, c)

    ensure_material("foliage", (0.18, 0.52, 0.18))
    ensure_material("foliage2", (0.22, 0.58, 0.24))
    ensure_material("trunk", (0.40, 0.27, 0.12))

    ensure_material("car_r", (0.80, 0.10, 0.10))
    ensure_material("car_b", (0.10, 0.20, 0.72))
    ensure_material("car_s", (0.76, 0.78, 0.80), "phong", (0.24, 0.24, 0.24))
    ensure_material("car_k", (0.06, 0.06, 0.07))
    ensure_material("car_w", (0.93, 0.93, 0.95))
    ensure_material("car_win", (0.30, 0.48, 0.72), "phong", (0.40, 0.40, 0.40))

    ensure_material("lt_red", (1.00, 0.04, 0.04))
    ensure_material("lt_yel", (1.00, 0.84, 0.04))
    ensure_material("lt_grn", (0.04, 0.88, 0.04))
    ensure_material("pole", (0.28, 0.30, 0.33))

    ensure_material("bench", (0.52, 0.38, 0.18))
    ensure_material("trash", (0.20, 0.28, 0.20))
    ensure_material("lamp", (0.24, 0.24, 0.26), "phong", (0.15, 0.15, 0.15))
    ensure_material("lamp_gl", (1.00, 0.93, 0.72))

    ensure_material("manhole", (0.12, 0.12, 0.12))
    ensure_material("hydrant", (0.76, 0.08, 0.08))
    ensure_material("dumpster", (0.20, 0.50, 0.20))
    ensure_material("wood", (0.48, 0.33, 0.16))

    ensure_material("crane_y", (0.95, 0.74, 0.08))
    ensure_material("crane_dark", (0.10, 0.10, 0.12))
    ensure_material("cable", (0.22, 0.22, 0.22))

    ensure_material("awning_r", (0.80, 0.15, 0.15))
    ensure_material("awning_b", (0.15, 0.25, 0.70))
    ensure_material("sign", (0.95, 0.85, 0.20))
    ensure_material("barber_r", (0.85, 0.10, 0.10))
    ensure_material("barber_w", (0.90, 0.90, 0.90))
    ensure_material("barber_b", (0.10, 0.20, 0.70))
    ensure_material("planter", (0.30, 0.45, 0.20))
    ensure_material("rope", (0.60, 0.48, 0.22))

    ensure_material("bill_r", (0.95, 0.25, 0.05))
    ensure_material("bill_c", (0.05, 0.75, 0.95))
    ensure_material("bill_y", (0.95, 0.85, 0.08))
    ensure_material("bill_m", (0.90, 0.10, 0.75))
    ensure_material("bill_g", (0.10, 0.88, 0.30))
    ensure_material("bill_sp", (0.30, 0.32, 0.35))


# -----------------------------------------------------------------------------
# PROTOTYPES (instancing targets)
# -----------------------------------------------------------------------------
def create_prototypes():
    # Window
    w = mkbox("proto_window", 0, 0, 0, 0.8, 1.0, WINDOW_DEPTH)
    assign("glassd" if LOW_QUALITY else "glass", w)
    register_prototype("window", w)

    # Tree (low-poly)
    tree_parts = []
    trunk = mkcyl("proto_tree_trunk", 0, 0, 0, 0.22, 3.0, sx=6)
    assign("trunk", trunk)
    tree_parts.append(trunk)
    if LOW_QUALITY:
        cap = mkcyl("proto_tree_cap", 0, 2.8, 0, 1.2, 1.8, sx=6)
        assign("foliage", cap)
        tree_parts.append(cap)
    else:
        cap1 = mksph("proto_tree_cap", 0, 3.6, 0, 1.2, sx=6, sy=4)
        cap2 = mksph("proto_tree_cap", 0.3, 4.2, 0.2, 0.9, sx=6, sy=4)
        assign("foliage", cap1)
        assign("foliage2", cap2)
        tree_parts.extend([cap1, cap2])
    tree = combine(tree_parts, "proto_tree")
    register_prototype("tree", tree)

    # Traffic light
    tl_parts = []
    pole = mkcyl("proto_tl_pole", 0, 0, 0, 0.12, 5.5, sx=6)
    assign("pole", pole)
    tl_parts.append(pole)
    arm = mkbox("proto_tl_arm", 0.6, 5.5, 0, 1.2, 0.12, 0.12)
    assign("pole", arm)
    tl_parts.append(arm)
    box = mkbox("proto_tl_box", 1.2, 4.4, 0, 0.34, 1.15, 0.34)
    assign("dark", box)
    tl_parts.append(box)
    for y, mat in ((5.7, "lt_red"), (5.3, "lt_yel"), (4.9, "lt_grn")):
        l = mkcyl("proto_tl_light", 1.2, y, 0, 0.11, 0.10, sx=6)
        assign(mat, l)
        tl_parts.append(l)
    tl = combine(tl_parts, "proto_tlight")
    register_prototype("traffic_light", tl)

    # Bench
    bench_parts = []
    for lx in (-0.8, 0.8):
        o = mkbox("proto_bench_leg", lx, 0, 0, 0.10, 0.35, 0.55)
        assign("metal", o)
        bench_parts.append(o)
    seat = mkbox("proto_bench_seat", 0, 0.35, 0, 2.0, 0.12, 0.60)
    back = mkbox("proto_bench_back", 0, 0.52, 0.24, 2.0, 0.42, 0.08)
    assign("bench", seat)
    assign("bench", back)
    bench_parts.extend([seat, back])
    bench = combine(bench_parts, "proto_bench")
    register_prototype("bench", bench)

    # Trash can
    trash_parts = []
    tc = mkcyl("proto_trash", 0, 0, 0, 0.25, 0.9, sx=6)
    lid = mkcyl("proto_trash_lid", 0, 0.9, 0, 0.27, 0.06, sx=6)
    assign("trash", tc)
    assign("dark", lid)
    trash_parts.extend([tc, lid])
    register_prototype("trash", combine(trash_parts, "proto_trashcan"))

    # Lamp post
    lamp_parts = []
    lp = mkcyl("proto_lamp_pole", 0, 0, 0, 0.08, 6.5, sx=6)
    la = mkbox("proto_lamp_arm", 0.4, 6.5, 0, 0.8, 0.08, 0.08)
    lg = mksph("proto_lamp_gl", 0.8, 6.5, 0, 0.22, sx=6, sy=4)
    assign("lamp", lp)
    assign("lamp", la)
    assign("lamp_gl", lg)
    lamp_parts.extend([lp, la, lg])
    register_prototype("lamp", combine(lamp_parts, "proto_lamp"))

    # Simplified car prototypes (no wheel cylinders; wheel arches instead)
    car_colors = ["car_r", "car_b", "car_s", "car_k", "car_w"]
    for color in car_colors:
        cparts = []
        body = mkbox("proto_car_body", 0, 0, 0, 3.8, 1.0, 1.8)
        roof = mkbox("proto_car_roof", 0, 1.0, 0, 2.2, 0.65, 1.45)
        fw = mkbox("proto_car_fw", 0, 1.2, -0.72, 1.8, 0.45, 0.08)
        rw = mkbox("proto_car_rw", 0, 1.2, 0.72, 1.8, 0.45, 0.08)
        assign(color, body)
        assign(color, roof)
        assign("car_win", fw)
        assign("car_win", rw)
        cparts.extend([body, roof, fw, rw])
        # dark wheel-arch strips on both sides (visual wheel simplification)
        for zoff in (-0.96, 0.96):
            ws = mkbox("proto_car_wstrip", 0, 0.05, zoff, 2.8, 0.32, 0.10)
            assign("dark", ws)
            cparts.append(ws)
        car = combine(cparts, "proto_car_" + color)
        register_prototype(color, car)


# -----------------------------------------------------------------------------
# CITY SECTIONS
# -----------------------------------------------------------------------------
def build_ground_roads_sidewalks_markings():
    # Ground
    g = mkbox("ground", 0, -0.1, 0, CITY_SZ, 0.1, CITY_SZ)
    assign("asphalt", g)
    put([g], "Grp_Ground")

    # Roads
    roads = []
    for col in range(N + 1):
        rv = mkbox("road_v", road_cx(col), 0, 0, ROAD_W, 0.05, CITY_SZ)
        assign("asphalt", rv)
        roads.append(rv)
    for row in range(N + 1):
        rh = mkbox("road_h", 0, 0, road_cz(row), CITY_SZ, 0.05, ROAD_W)
        assign("asphalt", rh)
        roads.append(rh)
    put(roads, "Grp_Roads")

    # Sidewalks
    sidewalks = []
    swh = 0.15
    for col in range(N + 1):
        cx = road_cx(col)
        for side in (-1, 1):
            sx = cx + side * (ROAD_W * 0.5 + SW_W * 0.5)
            sv = mkbox("sw_v", sx, 0, 0, SW_W, swh, CITY_SZ)
            assign("sidewalk", sv)
            sidewalks.append(sv)
    for row in range(N + 1):
        cz = road_cz(row)
        for side in (-1, 1):
            sz = cz + side * (ROAD_W * 0.5 + SW_W * 0.5)
            sh = mkbox("sw_h", 0, 0, sz, CITY_SZ, swh, SW_W)
            assign("sidewalk", sh)
            sidewalks.append(sh)
    put(sidewalks, "Grp_Sidewalks")

    # Road markings: combine per-road/per-intersection to reduce tiny mesh count
    d_w, d_l, d_gap, d_h = 0.30, 3.5, 2.5, 0.06
    marking_objs = []

    for col in range(N + 1):
        pieces = []
        cx = road_cx(col)
        z = OZ
        while z < OZ + CITY_SZ:
            d = mkbox("dash", cx, 0, z + d_l * 0.5, d_w, d_h, d_l)
            assign("rdline", d)
            pieces.append(d)
            z += d_l + d_gap
        for side in (-1, 1):
            ex = cx + side * ROAD_W * 0.42
            e = mkbox("edge", ex, 0, 0, 0.15, d_h, CITY_SZ)
            assign("rdline", e)
            pieces.append(e)
        merged = combine(pieces, "mark_v")
        if merged:
            marking_objs.append(merged)

    for row in range(N + 1):
        pieces = []
        cz = road_cz(row)
        x = OX
        while x < OX + CITY_SZ:
            d = mkbox("dash", x + d_l * 0.5, 0, cz, d_l, d_h, d_w)
            assign("rdline", d)
            pieces.append(d)
            x += d_l + d_gap
        for side in (-1, 1):
            ez = cz + side * ROAD_W * 0.42
            e = mkbox("edge", 0, 0, ez, CITY_SZ, d_h, 0.15)
            assign("rdline", e)
            pieces.append(e)
        merged = combine(pieces, "mark_h")
        if merged:
            marking_objs.append(merged)

    cw_n, cw_w, cw_h, cw_l, cw_sp = 5, 0.70, 0.07, ROAD_W * 0.85, 1.10
    for col in range(N + 1):
        for row in range(N + 1):
            pieces = []
            ix, iz = road_cx(col), road_cz(row)
            for k in range(cw_n):
                zk = iz - (cw_n - 1) * cw_sp * 0.5 + k * cw_sp
                c1 = mkbox("cw", ix, 0, zk, cw_l, cw_h, cw_w)
                assign("crsswlk", c1)
                pieces.append(c1)
            for k in range(cw_n):
                xk = ix - (cw_n - 1) * cw_sp * 0.5 + k * cw_sp
                c2 = mkbox("cw", xk, 0, iz, cw_w, cw_h, cw_l)
                assign("crsswlk", c2)
                pieces.append(c2)
            merged = combine(pieces, "mark_x")
            if merged:
                marking_objs.append(merged)

    put(marking_objs, "Grp_RoadMarkings")
    return swh


def add_building_windows(cx, base_y, cz, w, h, d, landmark=False):
    # Instanced thin windows (no full cubes)
    # Non-landmarks use every-other (even-indexed) back rows to preserve visual density while
    # reducing far-side instance counts for performance.
    nx = 4 if landmark else 3
    ny = 5 if landmark else 3
    nx = max(2, min(nx, int(max(2.0, w) / 2.0)))
    ny = max(2, min(ny, int(max(6.0, h) / 5.0)))
    sx = (w * 0.70) / max(1, nx - 1)
    sy = (h * 0.65) / max(1, ny)
    start_x = cx - (nx - 1) * sx * 0.5
    start_y = base_y + 2.2
    zf = cz - d * 0.5 - WINDOW_DEPTH * 0.5
    zb = cz + d * 0.5 + WINDOW_DEPTH * 0.5
    for iy in range(ny):
        wy = start_y + iy * sy
        for ix in range(nx):
            wx = start_x + ix * sx
            instance_proto("window", wx, wy + 0.5, zf, parent_group="Grp_Windows")
            if landmark or (iy % 2 == 0):
                instance_proto("window", wx, wy + 0.5, zb, ry=180, parent_group="Grp_Windows")


def add_building_entrance(cx, cz, w, d):
    objs = []
    fz = cz - d * 0.5
    dw, dh = 1.4, 2.4
    for sx in (-dw * 0.5 - 0.12, dw * 0.5 + 0.12):
        p = mkbox("dfrm", cx + sx, 0, fz - 0.08, 0.15, dh + 0.2, 0.15)
        assign("metal", p)
        objs.append(p)
    top = mkbox("dfrm", cx, dh, fz - 0.08, dw + 0.4, 0.15, 0.15)
    door = mkbox("door", cx, 0, fz - 0.04, dw, dh, 0.05)
    canopy = mkbox("canopy", cx, dh + 0.15, fz - 0.8, dw + 1.8, 0.2, 1.6)
    assign("metal", top)
    assign("glass", door)
    assign("awning_r", canopy)
    objs.extend([top, door, canopy])
    _entrances.append((cx, cz, fz, w))
    return objs


def add_roof(cx, top_y, cz, w, d, style):
    objs = []
    # 8 style families
    if style == "art_deco":
        for i, scale in enumerate((0.84, 0.62, 0.40)):
            o = mkbox("rtier", cx, top_y + i * 0.8, cz, w * scale, 0.8, d * scale)
            assign("stone", o)
            objs.append(o)
    elif style == "modern_glass":
        p = mkbox("rpar", cx, top_y, cz, w + 0.3, 0.45, d + 0.3)
        assign("concrete", p)
        objs.append(p)
    elif style == "brick":
        c1 = mkbox("cornice", cx, top_y, cz, w + 0.7, 0.55, d + 0.7)
        c2 = mkbox("cornice", cx, top_y + 0.55, cz, w + 0.35, 0.35, d + 0.35)
        assign("brick", c1)
        assign("stone", c2)
        objs.extend([c1, c2])
    elif style == "futuristic":
        m = mkbox("rfut", cx, top_y, cz, w * 0.9, 0.3, d * 0.9)
        assign("metal", m)
        objs.append(m)
    elif style == "neogothic":
        for dx, dz in ((w * 0.35, d * 0.35), (-w * 0.35, d * 0.35), (w * 0.35, -d * 0.35), (-w * 0.35, -d * 0.35)):
            s = mkcyl("spire", cx + dx, top_y, cz + dz, 0.18, 2.5, sx=6)
            assign("stone", s)
            objs.append(s)
    elif style == "minimalist":
        p = mkbox("rmini", cx, top_y, cz, w + 0.2, 0.25, d + 0.2)
        assign("bb_gray", p)
        objs.append(p)
    elif style == "industrial":
        p = mkbox("rind", cx, top_y, cz, w + 0.2, 0.4, d + 0.2)
        assign("bb_charcoal", p)
        objs.append(p)
    elif style == "postmodern":
        p1 = mkbox("rpm", cx, top_y, cz, w * 0.95, 0.35, d * 0.95)
        p2 = mkbox("rpm", cx + w * 0.12, top_y + 0.35, cz - d * 0.12, w * 0.48, 0.35, d * 0.48)
        assign("bb_blue", p1)
        assign("bb_beige", p2)
        objs.extend([p1, p2])

    if ENABLE_ROOF_DETAILS:
        # very low-poly roof details
        if style in ("industrial", "modern_glass", "minimalist"):
            ac = mkbox("ac", cx, top_y + 0.45, cz, 1.2, 0.6, 0.9)
            vent = mkcyl("vent", cx + 0.5, top_y + 1.0, cz + 0.3, 0.12, 0.5, sx=6)
            assign("metal", ac)
            assign("dark", vent)
            objs.extend([ac, vent])
        elif style in ("art_deco", "neogothic"):
            fin = mkcyl("fin", cx, top_y + 0.5, cz, 0.22, 1.8, sx=6)
            assign("metal", fin)
            objs.append(fin)
    return objs


def build_buildings():
    styles = [
        "art_deco", "modern_glass", "brick", "futuristic",
        "neogothic", "minimalist", "industrial", "postmodern",
    ]
    mats = ["bb_beige", "bb_cream", "bb_gray", "bb_bronze", "bb_blue", "bb_terra", "bb_olive", "brick"]

    bldg_objs = []
    block_index = 0

    min_per_block = max(4, min(BUILDINGS_PER_BLOCK_MIN, SUBDIV * SUBDIV))
    max_per_block = max(min_per_block, min(BUILDINGS_PER_BLOCK_MAX, SUBDIV * SUBDIV))
    generated_count = 0

    for bi in range(N):
        for bj in range(N):
            ox = blk_ox(bi)
            oz = blk_oz(bj)

            cells = [(r, c) for r in range(SUBDIV) for c in range(SUBDIV)]
            corner_cells = [(0, 0), (0, SUBDIV - 1), (SUBDIV - 1, 0), (SUBDIV - 1, SUBDIV - 1)]
            interior = [p for p in cells if p not in corner_cells]
            random.shuffle(interior)
            target_per_block = random.randint(min_per_block, max_per_block)
            regular_target = max(0, target_per_block - len(corner_cells))
            chosen = corner_cells + interior[:regular_target]
            generated_count += len(chosen)

            prev_h = -999
            prev_m = None

            for cr, cc in chosen:
                cx = ox + (cc + 0.5) * CELL_SZ
                cz = oz + (cr + 0.5) * CELL_SZ
                landmark = (cr, cc) in corner_cells

                if landmark:
                    h = random.uniform(30, 42)
                    w = random.uniform(6.0, 8.0)
                    d = random.uniform(6.0, 8.0)
                    style = random.choice(["art_deco", "neogothic", "postmodern"])
                    mat = random.choice(["stone", "bb_cream", "bb_gray"])
                    base_h = 2.0
                else:
                    h = random.uniform(8, 28)
                    if abs(h - prev_h) < 2.0:
                        h += 2.5
                    w = random.uniform(4.4, 7.6)
                    d = random.uniform(4.4, 7.6)
                    style = random.choice(styles)
                    mat = random.choice(mats)
                    if mat == prev_m:
                        alternatives = [m for m in mats if m != prev_m]
                        if alternatives:
                            mat = random.choice(alternatives)
                    base_h = 1.0

                prev_h = h
                prev_m = mat

                base = mkbox("bbase", cx, 0, cz, w + 0.5, base_h, d + 0.5)
                body = mkbox("bbody", cx, base_h, cz, w, h - base_h, d)
                assign("stone" if landmark else "concrete", base)
                assign(mat, body)
                bldg_objs.extend([base, body])

                add_building_windows(cx, base_h, cz, w, h - base_h, d, landmark=landmark)
                bldg_objs.extend(add_building_entrance(cx, cz, w, d))
                bldg_objs.extend(add_roof(cx, h, cz, w, d, style))

            block_index += 1
            # periodic scene cleanup while building the city core
            if block_index % 24 == 0:
                periodic_cleanup("{} blocks".format(block_index))

    put(bldg_objs, "Grp_Buildings")
    print("  Buildings generated: {}".format(generated_count))
    print("  Entrance records: {}".format(len(_entrances)))


def place_traffic_lights():
    offset = ROAD_W * 0.5 + SW_W * 0.5
    for col in range(N + 1):
        for row in range(N + 1):
            ix, iz = road_cx(col), road_cz(row)
            corners = [
                (ix - offset, iz - offset, 0),
                (ix + offset, iz - offset, 180),
                (ix - offset, iz + offset, 90),
                (ix + offset, iz + offset, -90),
            ]
            for px, pz, ry in corners:
                instance_proto("traffic_light", px, 0, pz, ry=ry, parent_group="Grp_TrafficLights")


def place_billboards():
    bcols = ["bill_r", "bill_c", "bill_y", "bill_m", "bill_g"]
    objs = []
    for _ in range(random.randint(BILLBOARD_COUNT_MIN, BILLBOARD_COUNT_MAX)):
        col = random.randint(0, N)
        side = random.choice([-1, 1])
        cx = road_cx(col) + side * (ROAD_W * 0.5 + SW_W + 0.5)
        cz = OZ + random.uniform(0.05, 0.95) * CITY_SZ
        by = 0.15
        left = mkcyl("bleg", cx - 2.8, 0, cz, 0.16, by + 3.8, sx=6)
        right = mkcyl("bleg", cx + 2.8, 0, cz, 0.16, by + 3.8, sx=6)
        f = mkbox("bface", cx, by + 1.0, cz - 0.08, 8.0, 4.0, 0.12)
        b = mkbox("bface", cx, by + 1.0, cz + 0.08, 8.0, 4.0, 0.12)
        assign("bill_sp", left)
        assign("bill_sp", right)
        assign(random.choice(bcols), f)
        assign(random.choice(bcols), b)
        objs.extend([left, right, f, b])
    put(objs, "Grp_Billboards")


def place_trees(sidewalk_h):
    for bi in range(N):
        for bj in range(N):
            n_trees = random.randint(TREES_PER_BLOCK_MIN, TREES_PER_BLOCK_MAX)
            ox = blk_ox(bi)
            oz = blk_oz(bj)
            for _ in range(n_trees):
                edge = random.randint(0, 3)
                if edge == 0:
                    tx = ox + random.uniform(2, BLOCK_SIZE - 2)
                    tz = oz - SW_W * 0.5
                elif edge == 1:
                    tx = ox + random.uniform(2, BLOCK_SIZE - 2)
                    tz = oz + BLOCK_SIZE + SW_W * 0.5
                elif edge == 2:
                    tx = ox - SW_W * 0.5
                    tz = oz + random.uniform(2, BLOCK_SIZE - 2)
                else:
                    tx = ox + BLOCK_SIZE + SW_W * 0.5
                    tz = oz + random.uniform(2, BLOCK_SIZE - 2)
                # Slight random scaling; entrance zones are sparse enough for flythroughs
                scl = random.uniform(0.85, 1.15)
                instance_proto("tree", tx, sidewalk_h, tz, scale=(scl, scl, scl), parent_group="Grp_Trees")


def place_street_furniture(sidewalk_h):
    # Reduced density vs. larger-grid version; keep all categories (lamp/bench/trash).
    spacing = 20.0  # Increased from 14.0 to lower sidewalk prop density.
    for col in range(N + 1):
        cx = road_cx(col)
        for side in (-1, 1):
            sx = cx + side * (ROAD_W * 0.5 + SW_W * 0.5)
            z = OZ + 5.0
            idx = 0
            while z < OZ + CITY_SZ - 5.0:
                asset = "lamp" if idx % 3 == 0 else ("bench" if idx % 3 == 1 else "trash")
                ry = 90 if asset == "bench" else 0
                instance_proto(asset, sx, sidewalk_h, z, ry=ry, parent_group="Grp_StreetFurniture")
                idx += 1
                z += spacing
    for row in range(N + 1):
        cz = road_cz(row)
        for side in (-1, 1):
            sz = cz + side * (ROAD_W * 0.5 + SW_W * 0.5)
            x = OX + 5.0
            idx = 0
            while x < OX + CITY_SZ - 5.0:
                asset = "lamp" if idx % 3 == 0 else ("bench" if idx % 3 == 1 else "trash")
                ry = 0
                instance_proto(asset, x, sidewalk_h, sz, ry=ry, parent_group="Grp_StreetFurniture")
                idx += 1
                x += spacing


def place_cars(sidewalk_h):
    n_cars = random.randint(CAR_COUNT_MIN, CAR_COUNT_MAX)
    car_assets = ["car_r", "car_b", "car_s", "car_k", "car_w"]
    for _ in range(n_cars):
        lane = random.choice(["parked_v", "parked_h", "driving_v", "driving_h"])
        if lane == "parked_v":
            col = random.randint(0, N)
            cx = road_cx(col) + random.choice([-1, 1]) * ROAD_W * 0.32
            cz = OZ + random.uniform(0.02, 0.98) * CITY_SZ
            ry = 0
        elif lane == "parked_h":
            row = random.randint(0, N)
            cz = road_cz(row) + random.choice([-1, 1]) * ROAD_W * 0.32
            cx = OX + random.uniform(0.02, 0.98) * CITY_SZ
            ry = 90
        elif lane == "driving_v":
            col = random.randint(0, N)
            cx = road_cx(col)
            cz = OZ + random.uniform(0.02, 0.98) * CITY_SZ
            ry = 0
        else:
            row = random.randint(0, N)
            cz = road_cz(row)
            cx = OX + random.uniform(0.02, 0.98) * CITY_SZ
            ry = 90
        instance_proto(random.choice(car_assets), cx, sidewalk_h, cz, ry=ry, parent_group="Grp_Cars")


def make_storefronts(sidewalk_h):
    objs = []
    sample = list(_entrances)
    random.shuffle(sample)
    sample = sample[:max(1, int(len(sample) * 0.30))]

    for cx, _cz, fz, bw in sample:
        st = random.choice(["coffee", "restaurant", "barbershop", "club"])
        if st == "coffee":
            t = mkbox("ctable", cx, sidewalk_h, fz - 2.0, 1.0, 0.7, 1.0)
            c1 = mkbox("cchair", cx - 0.6, sidewalk_h, fz - 2.0, 0.45, 0.5, 0.45)
            c2 = mkbox("cchair", cx + 0.6, sidewalk_h, fz - 2.0, 0.45, 0.5, 0.45)
            s = mkbox("csign", cx, 2.6, fz - 0.15, min(bw * 0.6, 3.0), 0.6, 0.1)
            assign("bench", t)
            assign("bench", c1)
            assign("bench", c2)
            assign("sign", s)
            objs.extend([t, c1, c2, s])
        elif st == "restaurant":
            a = mkbox("rawn", cx, 2.5, fz - 1.2, min(bw * 0.8, 5.0), 0.25, 2.2)
            m = mkbox("menu", cx - bw * 0.3, sidewalk_h, fz - 2.0, 0.08, 1.4, 0.9)
            p = mkbox("planter", cx + bw * 0.25, sidewalk_h, fz - 2.0, 0.8, 0.5, 0.8)
            assign("awning_r", a)
            assign("dark", m)
            assign("planter", p)
            objs.extend([a, m, p])
        elif st == "barbershop":
            for k, bmat in enumerate(["barber_r", "barber_w", "barber_b", "barber_r", "barber_w"]):
                pole = mkcyl("bpole", cx - bw * 0.4, sidewalk_h + k * 0.5, fz - 0.25, 0.1, 0.5, sx=6)
                assign(bmat, pole)
                objs.append(pole)
            s = mkbox("bsign", cx, 2.6, fz - 0.15, min(bw * 0.55, 2.5), 0.55, 0.1)
            assign("sign", s)
            objs.append(s)
        else:
            for ky in (0.8, 1.6, 2.4):
                led = mkbox("led", cx, ky, fz - 0.05, min(bw * 0.9, 6.0), 0.12, 0.06)
                assign("bill_m", led)
                objs.append(led)
            p1 = mkcyl("qpost", cx - 1.5, sidewalk_h, fz - 2.5, 0.07, 1.0, sx=6)
            p2 = mkcyl("qpost", cx + 1.5, sidewalk_h, fz - 2.5, 0.07, 1.0, sx=6)
            r = mkbox("rope", cx, sidewalk_h + 1.0, fz - 2.5, 3.0, 0.06, 0.06)
            assign("metal", p1)
            assign("metal", p2)
            assign("rope", r)
            objs.extend([p1, p2, r])

    put(objs, "Grp_Storefronts")


def place_cranes(sidewalk_h):
    # Simplified cranes: exactly 3 cylinders + 2 boxes
    objs = []
    interior_positions = [(bi, bj) for bi in range(1, N - 1) for bj in range(1, N - 1)]
    # tiny/test grids may have no interior cells; allow edge blocks in that case.
    if not interior_positions:
        interior_positions = [(bi, bj) for bi in range(N) for bj in range(N)]
    crane_count = min(len(interior_positions), random.randint(CRANE_COUNT_MIN, CRANE_COUNT_MAX))
    positions = random.sample(interior_positions, crane_count)
    for bi, bj in positions:
        cx = blk_cx(bi) + random.uniform(-8, 8)
        cz = blk_cz(bj) + random.uniform(-8, 8)
        h = random.uniform(32, 48)
        jib = random.uniform(14, 20)

        tower = mkcyl("cr_tower", cx, 0, cz, 0.30, h, sx=6)
        cable = mkcyl("cr_cable", cx + jib * 0.62, sidewalk_h, cz, 0.05, h + 1.8 - sidewalk_h, sx=6)
        hook = mkcyl("cr_hook", cx + jib * 0.62, sidewalk_h, cz, 0.12, 0.5, sx=6)
        boom = mkbox("cr_boom", cx + jib * 0.5, h + 1.8, cz, jib, 0.45, 0.45)
        cab = mkbox("cr_cab", cx, h, cz, 2.2, 1.8, 1.8)

        assign("crane_y", tower)
        assign("cable", cable)
        assign("crane_dark", hook)
        assign("crane_y", boom)
        assign("crane_dark", cab)
        objs.extend([tower, cable, hook, boom, cab])

    put(objs, "Grp_Cranes")


def place_misc(sidewalk_h):
    objs = []

    # Manholes / hydrants / dumpsters
    for bi in range(N):
        for bj in range(N):
            ox = blk_ox(bi)
            oz = blk_oz(bj)
            for _ in range(random.randint(1, 2)):
                mh = mkcyl("mhole", ox + random.uniform(0, BLOCK_SIZE), sidewalk_h - 0.01, oz - SW_W * 0.3, 0.45, 0.04, sx=6)
                assign("manhole", mh)
                objs.append(mh)
            hx = ox + random.uniform(2, BLOCK_SIZE - 2)
            hz = oz - SW_W * 0.5
            hb = mkcyl("hydr", hx, sidewalk_h, hz, 0.18, 0.7, sx=6)
            hc = mksph("hydr_cap", hx, sidewalk_h + 0.7, hz, 0.2, sx=6, sy=4)
            assign("hydrant", hb)
            assign("hydrant", hc)
            objs.extend([hb, hc])
            if (bi + bj) % 4 == 0:
                dx = ox + random.uniform(4, BLOCK_SIZE - 4)
                dz = oz + BLOCK_SIZE * 0.85
                dp = mkbox("dump", dx, sidewalk_h, dz, 2.4, 1.1, 1.1, ry=random.choice([0, 90]))
                rim = mkbox("dump_rim", dx, sidewalk_h + 1.1, dz, 2.5, 0.08, 1.2)
                assign("dumpster", dp)
                assign("dark", rim)
                objs.extend([dp, rim])

    # Power poles
    for col in range(N + 1):
        cx = road_cx(col) + ROAD_W * 0.5 + SW_W
        z = OZ + 5.0
        while z < OZ + CITY_SZ - 5.0:
            p = mkcyl("ppole", cx, 0, z, 0.12, 8.8, sx=6)
            b = mkbox("pbar", cx, 8.6, z, 3.2, 0.14, 0.14)
            assign("wood", p)
            assign("wood", b)
            objs.extend([p, b])
            z += 22.0

    put(objs, "Grp_MiscDetails")


# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------
def generate_city():
    print("Starting optimized procedural city generation...")
    print("  QUALITY: {}".format(QUALITY))
    print("  CITY_SIZE: {} | Grid: {}x{} | Buildings per block: {}-{}".format(
        CITY_SIZE, N, N, BUILDINGS_PER_BLOCK_MIN, BUILDINGS_PER_BLOCK_MAX
    ))

    # Force clean scene and suspend viewport updates for performance.
    # NOTE: This intentionally clears any unsaved scene content.
    cmds.file(newFile=True, force=True)
    cmds.refresh(suspend=True)

    completed = False
    try:
        cmds.group(em=True, name=MASTER)
        create_materials()
        create_prototypes()

        sidewalk_h = build_ground_roads_sidewalks_markings()
        periodic_cleanup("roads/markings")
        progress(20, "roads, sidewalks, and road markings complete")

        build_buildings()
        periodic_cleanup("buildings")
        progress(40, "buildings complete")

        place_traffic_lights()
        place_billboards()
        place_trees(sidewalk_h)
        periodic_cleanup("traffic lights/billboards/trees")
        progress(60, "traffic lights, billboards, and trees complete")

        place_street_furniture(sidewalk_h)
        place_cars(sidewalk_h)
        make_storefronts(sidewalk_h)
        periodic_cleanup("furniture/cars/storefronts")
        progress(80, "street furniture, cars, and storefronts complete")

        place_cranes(sidewalk_h)
        place_misc(sidewalk_h)
        periodic_cleanup("cranes/misc details")
        progress(100, "city generation complete")

        total_children = 0
        for g in _groups.values():
            total_children += len(cmds.listRelatives(g, children=True) or [])

        print("\n=== Procedural City Generation Complete ===")
        print("Master group : {}".format(MASTER))
        print("Sub-groups   : {}".format(len(_groups)))
        print("Scene children under sub-groups: {}".format(total_children))
        print("Buildings    : target {}-{} per block".format(BUILDINGS_PER_BLOCK_MIN, BUILDINGS_PER_BLOCK_MAX))
        print("Random seed  : 42")
        print("===========================================\n")
        completed = True

    finally:
        cmds.refresh(suspend=False)
        cmds.refresh(force=True)
        if not completed:
            print("City generation was interrupted; viewport refresh has been restored.")


generate_city()
