"""
procedural_city.py
==================
Production-ready Maya Python script for procedural city generation.

Generates a heavily detailed, stylized modern city on a 20x20 block grid.
Run this script inside the Maya Script Editor (Python tab).

Requirements:
    Maya 2018+ with standard polygon tools available.
    Sufficient RAM recommended (large scene: ~80 000+ objects).

Usage:
    Copy-paste entire file into Maya Script Editor and execute,
    OR run via: import procedural_city (if placed in PYTHONPATH).

Random seed 42 ensures reproducible results.
"""

import maya.cmds as cmds
import random
import math

# =============================================================================
# SEED & GLOBAL CONFIGURATION
# =============================================================================
random.seed(42)

BLOCK_SIZE  = 50        # Each city block footprint (units)
ROAD_W      = 8         # Road width (units)
SW_W        = 2         # Sidewalk width on each side (units)
STREET_MOD  = ROAD_W + SW_W * 2    # Total street module width  = 12
MODULE      = BLOCK_SIZE + STREET_MOD   # City-cell size  = 62
N           = 20        # Grid dimension  (20x20 blocks)
CITY_SZ     = N * MODULE + STREET_MOD  # Total city footprint  = 1252
OX          = -CITY_SZ / 2.0           # City world X origin  = -626
OZ          = -CITY_SZ / 2.0           # City world Z origin  = -626
MASTER      = "Procedural_City"        # Name of the root group

# =============================================================================
# UNIQUE-NAME COUNTER
# =============================================================================
_cnt = [0]


def uid(prefix):
    """Return a unique object name: prefix_NNNNN."""
    _cnt[0] += 1
    return "{}_{:05d}".format(prefix, _cnt[0])


# =============================================================================
# POSITION HELPERS
# =============================================================================
def blk_ox(i):
    """Left-edge X of block column i."""
    return OX + i * MODULE + STREET_MOD


def blk_oz(j):
    """Front-edge Z of block row j."""
    return OZ + j * MODULE + STREET_MOD


def blk_cx(i):
    """Center X of block column i."""
    return blk_ox(i) + BLOCK_SIZE * 0.5


def blk_cz(j):
    """Center Z of block row j."""
    return blk_oz(j) + BLOCK_SIZE * 0.5


def road_cx(col):
    """Center X of the vertical road at column col  (0 .. N)."""
    return OX + col * MODULE + STREET_MOD * 0.5


def road_cz(row):
    """Center Z of the horizontal road at row  (0 .. N)."""
    return OZ + row * MODULE + STREET_MOD * 0.5


# =============================================================================
# GEOMETRY PRIMITIVES  (all Y coords are *bottom* of the object unless noted)
# =============================================================================
def mkbox(nm, cx, by, cz, w, h, d, ry=0):
    """Create a polyCube.  Bottom at y=by, centre at (cx, -, cz)."""
    o = cmds.polyCube(w=w, h=h, d=d, sx=1, sy=1, sz=1, name=uid(nm))[0]
    cmds.move(cx, by + h * 0.5, cz, o)
    if ry:
        cmds.rotate(0, ry, 0, o, r=True)
    return o


def mkcyl(nm, cx, by, cz, r, h, ry=0, rx_=0, rz_=0):
    """Create a polyCylinder.  Bottom at y=by."""
    o = cmds.polyCylinder(r=r, h=h, sc=0, sx=8, sy=1, name=uid(nm))[0]
    cmds.move(cx, by + h * 0.5, cz, o)
    if rx_:
        cmds.rotate(rx_, 0, 0, o, r=True)
    if ry:
        cmds.rotate(0, ry, 0, o, r=True)
    if rz_:
        cmds.rotate(0, 0, rz_, o, r=True)
    return o


def mksph(nm, cx, cy, cz, r):
    """Create a polySphere centred at (cx, cy, cz)."""
    o = cmds.polySphere(r=r, sx=8, sy=6, name=uid(nm))[0]
    cmds.move(cx, cy, cz, o)
    return o


# =============================================================================
# MATERIAL HELPERS
# =============================================================================
_sg = {}   # shader_name -> shading_group_name


def mkmat(nm, r, g, b, typ="lambert", sp=None):
    """Create (or reuse) a Lambert / Phong shader and its SG."""
    if nm in _sg:
        return
    m = cmds.shadingNode(typ, asShader=True, name=nm)
    cmds.setAttr(m + ".color", r, g, b, type="double3")
    if typ == "phong" and sp:
        cmds.setAttr(m + ".specularColor", sp[0], sp[1], sp[2], type="double3")
        cmds.setAttr(m + ".cosinePower", 25)
    sg = cmds.sets(renderable=True, noSurfaceShader=True,
                   empty=True, name=nm + "_SG")
    cmds.connectAttr(m + ".outColor", sg + ".surfaceShader", force=True)
    _sg[nm] = sg


def asgn(mat, obj):
    """Assign material to a mesh object."""
    sg = _sg.get(mat)
    if sg and cmds.objExists(obj):
        try:
            cmds.sets(obj, edit=True, forceElement=sg)
        except Exception:
            pass


# =============================================================================
# CREATE ALL MATERIALS
# =============================================================================
print("Creating materials...")

# -- Infrastructure --
mkmat("asphalt",   0.15, 0.15, 0.15)
mkmat("concrete",  0.50, 0.50, 0.50)
mkmat("sidewalk",  0.73, 0.71, 0.65)
mkmat("rdline",    0.95, 0.95, 0.85)
mkmat("crsswlk",   0.88, 0.88, 0.78)

# -- Building shells --
mkmat("stone",     0.60, 0.55, 0.50)
mkmat("brick",     0.68, 0.33, 0.20)
mkmat("metal",     0.62, 0.65, 0.70, "phong", (0.30, 0.30, 0.30))
mkmat("glass",     0.42, 0.62, 0.85, "phong", (0.50, 0.50, 0.50))
mkmat("glassd",    0.18, 0.28, 0.42, "phong", (0.40, 0.40, 0.40))
mkmat("wht_mat",   0.90, 0.90, 0.90)
mkmat("drk_mat",   0.12, 0.12, 0.15)

# -- Building body colours --
BLDG_MATS = [
    "bb_beige", "bb_cream", "bb_gray", "bb_bronze",
    "bb_blue",  "bb_terra", "bb_olv", "brick"
]
mkmat("bb_beige",  0.85, 0.80, 0.68)
mkmat("bb_cream",  0.92, 0.90, 0.78)
mkmat("bb_gray",   0.60, 0.63, 0.67)
mkmat("bb_bronze", 0.65, 0.50, 0.30)
mkmat("bb_blue",   0.32, 0.48, 0.68)
mkmat("bb_terra",  0.72, 0.38, 0.26)
mkmat("bb_olv",    0.52, 0.56, 0.38)

# -- Nature --
mkmat("foliage",   0.16, 0.50, 0.16)
mkmat("foliage2",  0.20, 0.58, 0.22)
mkmat("trunk_c",   0.40, 0.27, 0.12)

# -- Cars --
CAR_MATS = ["car_r", "car_b", "car_s", "car_k", "car_w"]
mkmat("car_r",     0.80, 0.10, 0.10)
mkmat("car_b",     0.10, 0.20, 0.72)
mkmat("car_s",     0.76, 0.78, 0.80, "phong", (0.25, 0.25, 0.25))
mkmat("car_k",     0.06, 0.06, 0.07)
mkmat("car_w",     0.93, 0.93, 0.95)
mkmat("car_win",   0.30, 0.48, 0.72, "phong", (0.40, 0.40, 0.40))
mkmat("tire_c",    0.08, 0.08, 0.08)

# -- Traffic lights --
mkmat("lt_red",    1.00, 0.04, 0.04)
mkmat("lt_yel",    1.00, 0.84, 0.04)
mkmat("lt_grn",    0.04, 0.88, 0.04)
mkmat("pole_m",    0.28, 0.30, 0.33)

# -- Street furniture --
mkmat("bench_m",   0.52, 0.38, 0.18)
mkmat("trash_m",   0.20, 0.28, 0.20)
mkmat("lamp_m",    0.24, 0.24, 0.26, "phong", (0.15, 0.15, 0.15))
mkmat("lamp_gl",   1.00, 0.93, 0.72)

# -- Misc scene details --
mkmat("manhole_m", 0.12, 0.12, 0.12)
mkmat("hydrant_m", 0.76, 0.08, 0.08)
mkmat("dumpster_m",0.20, 0.50, 0.20)
mkmat("wood_m",    0.48, 0.33, 0.16)
mkmat("crane_y",   0.95, 0.74, 0.08)
mkmat("crane_k",   0.10, 0.10, 0.12)
mkmat("cable_m",   0.22, 0.22, 0.22)
mkmat("awning_r",  0.80, 0.15, 0.15)
mkmat("awning_b",  0.15, 0.25, 0.70)
mkmat("sign_m",    0.95, 0.85, 0.20)
mkmat("barber_r",  0.85, 0.10, 0.10)
mkmat("barber_w",  0.90, 0.90, 0.90)
mkmat("barber_b",  0.10, 0.20, 0.70)
mkmat("planter_m", 0.30, 0.45, 0.20)
mkmat("rope_m",    0.60, 0.48, 0.22)

# -- Billboards (neon colours) --
BILL_MATS = ["bill_r", "bill_c", "bill_y", "bill_m", "bill_g"]
mkmat("bill_r",    0.95, 0.25, 0.05)
mkmat("bill_c",    0.05, 0.75, 0.95)
mkmat("bill_y",    0.95, 0.85, 0.08)
mkmat("bill_m",    0.90, 0.10, 0.75)
mkmat("bill_g",    0.10, 0.88, 0.30)
mkmat("bill_sp",   0.30, 0.32, 0.35)

print("  {} shading groups created.".format(len(_sg)))


# =============================================================================
# MASTER GROUP & SUB-GROUP HELPERS
# =============================================================================
if cmds.objExists(MASTER):
    cmds.delete(MASTER)
master = cmds.group(em=True, name=MASTER)

_grps = {}


def get_grp(name):
    """Return (creating if needed) a named child group of master."""
    if name not in _grps:
        g = cmds.group(em=True, name=name)
        cmds.parent(g, master)
        _grps[name] = g
    return _grps[name]


def put(objs, gname):
    """Parent a list of objects into a named sub-group."""
    g = get_grp(gname)
    for o in objs:
        if o and cmds.objExists(o):
            try:
                cmds.parent(o, g)
            except Exception:
                pass


def collapse_meshes(objs, prefix):
    """Merge related mesh pieces into one object to reduce scene object count."""
    valid = [o for o in objs if o and cmds.objExists(o)]
    if not valid:
        return []
    if len(valid) == 1:
        return valid
    try:
        merged = cmds.polyUnite(valid, ch=False, mergeUVSets=True, name=uid(prefix))[0]
        return [merged]
    except Exception:
        # If Maya cannot merge a specific object set, keep the original pieces.
        return valid


# =============================================================================
# SECTION 1: GROUND PLANE
# =============================================================================
print("Section 1: Ground plane...")
gnd = mkbox("ground", 0, -0.1, 0, CITY_SZ, 0.1, CITY_SZ)
asgn("asphalt", gnd)
put([gnd], "Grp_Ground")


# =============================================================================
# SECTION 2: ROADS
# =============================================================================
print("Section 2: Roads...")
road_objs = []

# Vertical roads run the full city length along Z, one per column
for col in range(N + 1):
    o = mkbox("road_v", road_cx(col), 0, 0, ROAD_W, 0.05, CITY_SZ)
    asgn("asphalt", o)
    road_objs.append(o)

# Horizontal roads run the full city length along X, one per row
for row in range(N + 1):
    o = mkbox("road_h", 0, 0, road_cz(row), CITY_SZ, 0.05, ROAD_W)
    asgn("asphalt", o)
    road_objs.append(o)

put(road_objs, "Grp_Roads")
print("  Roads placed: {}".format(len(road_objs)))


# =============================================================================
# SECTION 3: SIDEWALKS
# =============================================================================
print("Section 3: Sidewalks...")
sw_objs = []
SWH = 0.15   # sidewalk raise height

for col in range(N + 1):
    cx = road_cx(col)
    for side in (-1, 1):
        sx = cx + side * (ROAD_W * 0.5 + SW_W * 0.5)
        o = mkbox("sw_v", sx, 0, 0, SW_W, SWH, CITY_SZ)
        asgn("sidewalk", o)
        sw_objs.append(o)

for row in range(N + 1):
    cz = road_cz(row)
    for side in (-1, 1):
        sz = cz + side * (ROAD_W * 0.5 + SW_W * 0.5)
        o = mkbox("sw_h", 0, 0, sz, CITY_SZ, SWH, SW_W)
        asgn("sidewalk", o)
        sw_objs.append(o)

put(sw_objs, "Grp_Sidewalks")
print("  Sidewalk strips: {}".format(len(sw_objs)))


# =============================================================================
# SECTION 4: ROAD MARKINGS  (centre dashes, edge lines, crosswalks)
# =============================================================================
print("Section 4: Road markings...")
mrk_objs = []

DASH_W, DASH_L, DASH_GAP, DASH_H = 0.30, 3.5, 2.5, 0.06

# Dashed centre lines on vertical roads
for col in range(N + 1):
    cx = road_cx(col)
    z = OZ
    while z < OZ + CITY_SZ:
        o = mkbox("dash", cx, 0, z + DASH_L * 0.5, DASH_W, DASH_H, DASH_L)
        asgn("rdline", o)
        mrk_objs.append(o)
        z += DASH_L + DASH_GAP

# Dashed centre lines on horizontal roads
for row in range(N + 1):
    cz = road_cz(row)
    x = OX
    while x < OX + CITY_SZ:
        o = mkbox("dash", x + DASH_L * 0.5, 0, cz, DASH_L, DASH_H, DASH_W)
        asgn("rdline", o)
        mrk_objs.append(o)
        x += DASH_L + DASH_GAP

# Solid edge lines along both sides of every road
EW, EH = 0.15, 0.06
for col in range(N + 1):
    cx = road_cx(col)
    for side in (-1, 1):
        ex = cx + side * ROAD_W * 0.42
        o = mkbox("edge", ex, 0, 0, EW, EH, CITY_SZ)
        asgn("rdline", o)
        mrk_objs.append(o)

for row in range(N + 1):
    cz = road_cz(row)
    for side in (-1, 1):
        ez = cz + side * ROAD_W * 0.42
        o = mkbox("edge", 0, 0, ez, CITY_SZ, EH, EW)
        asgn("rdline", o)
        mrk_objs.append(o)

# Crosswalks at every intersection (striped white rectangles)
CW_N    = 5            # stripes per crossing direction
CW_W    = 0.70         # stripe width
CW_H    = 0.07         # stripe height
CW_L    = ROAD_W * 0.85  # stripe length
CW_SP   = 1.10         # stripe spacing

for col in range(N + 1):
    for row in range(N + 1):
        ix, iz = road_cx(col), road_cz(row)
        # Stripes crossing the vertical road (pedestrians walk along X)
        for k in range(CW_N):
            zk = iz - (CW_N - 1) * CW_SP * 0.5 + k * CW_SP
            o = mkbox("cw", ix, 0, zk, CW_L, CW_H, CW_W)
            asgn("crsswlk", o)
            mrk_objs.append(o)
        # Stripes crossing the horizontal road (pedestrians walk along Z)
        for k in range(CW_N):
            xk = ix - (CW_N - 1) * CW_SP * 0.5 + k * CW_SP
            o = mkbox("cw", xk, 0, iz, CW_W, CW_H, CW_L)
            asgn("crsswlk", o)
            mrk_objs.append(o)

put(mrk_objs, "Grp_RoadMarkings")
print("  Road marking pieces: {}".format(len(mrk_objs)))


# =============================================================================
# SECTION 5-6: BUILDINGS
# =============================================================================
print("Section 5-6: Buildings (all blocks)...")

# Entrance registry — used later for storefront decoration
_entrances = []   # each entry: (cx, cz, front_z, bldg_w)


# Window column density: 1 column per this many units of building width
WIN_COL_DIVISOR = 5.0
WINDOW_BASE_Y_OFFSET = 2.5

# -- Window grid helper --
def add_windows(cx, base_y, cz, w, h, d, style):
    """Return window cube objects on the front & back faces."""
    objs  = []
    wmat  = "glass" if style in ("modern_glass", "futuristic") else "glassd"
    WW, WH, WD = 0.75, 1.00, 0.12    # width, height, extrusion depth
    WCX = max(1.8, w / WIN_COL_DIVISOR)   # column spacing
    WRY = 2.2                              # row spacing
    nx  = max(1, min(4, int((w - 0.5) / WCX)))
    nf  = max(1, min(4, int((h - WINDOW_BASE_Y_OFFSET) / WRY)))
    start_y = base_y + WINDOW_BASE_Y_OFFSET
    for row in range(nf):
        wy = start_y + row * WRY + WH * 0.5
        for col in range(nx):
            wx = cx - (nx - 1) * WCX * 0.5 + col * WCX
            # Front window
            o = mkbox("win", wx, wy - WH * 0.5, cz - d * 0.5 - WD * 0.5, WW, WH, WD)
            asgn(wmat, o); objs.append(o)
            # Back window
            o = mkbox("win", wx, wy - WH * 0.5, cz + d * 0.5 + WD * 0.5, WW, WH, WD)
            asgn(wmat, o); objs.append(o)
    return objs


# -- Entrance helper --
def add_entrance(cx, cz, w, d):
    """Return door-frame, glass door and canopy objects."""
    objs = []
    fz   = cz - d * 0.5     # front face Z position
    dw, dh, dd = 1.4, 2.4, 0.15   # door opening size
    # Door-frame stiles and lintel
    for sx in (-dw * 0.5 - 0.12, dw * 0.5 + 0.12):
        o = mkbox("dfrm", cx + sx, 0, fz - dd * 0.5, 0.15, dh + 0.2, dd)
        asgn("metal", o); objs.append(o)
    o = mkbox("dfrm", cx, dh, fz - dd * 0.5, dw + 0.4, 0.15, dd)
    asgn("metal", o); objs.append(o)
    # Door glass
    o = mkbox("dglass", cx, 0, fz - 0.07, dw, dh, 0.06)
    asgn("glass", o); objs.append(o)
    # Canopy / awning
    aw_d = 1.6
    o = mkbox("awn", cx, dh + 0.15, fz - aw_d * 0.5, dw + 2.0, 0.2, aw_d)
    asgn("awning_r", o); objs.append(o)
    # Record entrance for storefront dressing
    _entrances.append((cx, cz, fz, w))
    return objs


# -- Roof helper (style-dependent) --
def add_roof(cx, top_y, cz, w, d, style):
    """Return roof objects appropriate to the architectural style."""
    objs = []
    if style == "art_deco":
        # Three stepped tiers + central finial
        tiers = [(w * 0.80, d * 0.80, 1.5),
                 (w * 0.55, d * 0.55, 1.2),
                 (w * 0.30, d * 0.30, 1.8)]
        y = top_y
        for sw, sd, sh in tiers:
            o = mkbox("rtier", cx, y, cz, sw, sh, sd)
            asgn("stone", o); objs.append(o)
            y += sh
        o = mkcyl("finial", cx, y, cz, 0.28, 3.0)
        asgn("metal", o); objs.append(o)

    elif style == "modern_glass":
        # Flat parapet + slim glass railing
        o = mkbox("par", cx, top_y, cz, w + 0.3, 0.5, d + 0.3)
        asgn("concrete", o); objs.append(o)
        for rcx_, rcz_, rw, rd in [
            (cx,          cz - d * 0.5 - 0.05, w,    0.08),
            (cx,          cz + d * 0.5 + 0.05, w,    0.08),
            (cx - w * 0.5 - 0.05, cz,           0.08, d),
            (cx + w * 0.5 + 0.05, cz,           0.08, d),
        ]:
            o = mkbox("rail", rcx_, top_y + 0.5, rcz_, rw, 0.9, rd)
            asgn("glass", o); objs.append(o)

    elif style == "brick":
        # Projecting cornice (2 layers)
        o = mkbox("crnice", cx, top_y,        cz, w + 0.8, 0.6, d + 0.8)
        asgn("brick", o); objs.append(o)
        o = mkbox("crnice", cx, top_y + 0.6,  cz, w + 0.4, 0.4, d + 0.4)
        asgn("stone", o); objs.append(o)

    elif style == "futuristic":
        # Thin metal cap + vertical fins
        o = mkbox("froof", cx, top_y, cz, w * 0.9, 0.35, d * 0.9)
        asgn("metal", o); objs.append(o)
        n_fins = max(2, int(w / 3.5))
        for k in range(n_fins):
            # Spread fins evenly across 80 % of building width
            if n_fins > 1:
                fx = cx - w * 0.4 + k * (w * 0.8 / (n_fins - 1))
            else:
                fx = cx
            o = mkbox("fin", fx, top_y + 0.35, cz, 0.18,
                      random.uniform(1.2, 3.5), d * 0.5)
            asgn("metal", o); objs.append(o)

    elif style == "neogothic":
        # Corner spires + tall central spire
        for dx, dz in [(w * 0.35,  d * 0.35),
                       (-w * 0.35,  d * 0.35),
                       (w * 0.35, -d * 0.35),
                       (-w * 0.35, -d * 0.35)]:
            o = mkcyl("gspire", cx + dx, top_y, cz + dz,
                      0.22, random.uniform(2.0, 4.5))
            asgn("stone", o); objs.append(o)
        o = mkcyl("gcspire", cx, top_y, cz, 0.38, random.uniform(3.5, 7.0))
        asgn("stone", o); objs.append(o)

    else:
        # Default flat parapet
        o = mkbox("par", cx, top_y, cz, w + 0.2, 0.4, d + 0.2)
        asgn("concrete", o); objs.append(o)

    return objs


# -- Roof-detail helper --
def add_roof_details(cx, top_y, cz, w, d):
    """AC units, vents, or satellite dish on rooftop."""
    objs = []
    choice = random.choice(["ac", "vent", "dish", "vent2"])
    ox_ = cx + random.uniform(-w * 0.28, w * 0.28)
    oz_ = cz + random.uniform(-d * 0.28, d * 0.28)
    if choice == "ac":
        o = mkbox("ac", ox_, top_y, oz_, 1.5, 0.8, 1.0)
        asgn("metal", o); objs.append(o)
        o = mkcyl("acex", ox_ + 0.3, top_y + 0.8, oz_, 0.18, 0.5)
        asgn("drk_mat", o); objs.append(o)
    elif choice == "vent":
        o = mkcyl("vent", ox_, top_y, oz_, 0.28, 1.2)
        asgn("drk_mat", o); objs.append(o)
    elif choice == "dish":
        o = mkcyl("dishp", ox_, top_y, oz_, 0.07, 1.0)
        asgn("metal", o); objs.append(o)
        o = mkbox("dishb", ox_, top_y + 1.0, oz_, 0.8, 0.07, 0.8)
        asgn("metal", o); objs.append(o)
    elif choice == "vent2":
        for _ in range(2):
            vx = cx + random.uniform(-w * 0.32, w * 0.32)
            vz = cz + random.uniform(-d * 0.32, d * 0.32)
            o = mkcyl("vent", vx, top_y, vz, 0.22, 1.0)
            asgn("drk_mat", o); objs.append(o)
    return objs


# -- Single building constructor --
def build_regular(cx, cz, w, d, h, style, bmat):
    """Construct one building; return all mesh objects."""
    objs = []
    # Stone/metal base (slightly wider than body)
    o = mkbox("bbase", cx, 0, cz, w + 0.6, 1.0, d + 0.6)
    asgn("stone", o); objs.append(o)
    # Main body
    o = mkbox("bbody", cx, 1.0, cz, w, h - 1.0, d)
    asgn(bmat, o); objs.append(o)
    # Windows
    objs.extend(add_windows(cx, 1.0, cz, w, h - 1.0, d, style))
    # Entrance
    objs.extend(add_entrance(cx, cz, w, d))
    # Roof
    objs.extend(add_roof(cx, h, cz, w, d, style))
    # Rooftop details (AC / vent / dish)
    if random.random() < 0.65:
        objs.extend(add_roof_details(cx, h, cz, w, d))
    return collapse_meshes(objs, "bldg")


# -- Landmark corner building constructor --
def build_landmark(cx, cz, w, d, h):
    """Tall, ornate landmark building for block corners."""
    objs = []
    style = random.choice(["art_deco", "neogothic"])
    bmat  = random.choice(["stone", "bb_cream", "bb_gray"])

    # Wide decorative base (2 units tall)
    o = mkbox("lmbase", cx, 0, cz, w + 1.0, 2.0, d + 1.0)
    asgn("stone", o); objs.append(o)
    # Mid-floor band
    o = mkbox("lmband", cx, h * 0.45, cz, w + 0.5, 0.6, d + 0.5)
    asgn("stone", o); objs.append(o)
    # Main body
    o = mkbox("lmbody", cx, 2.0, cz, w, h - 2.0, d)
    asgn(bmat, o); objs.append(o)
    # Windows (more floors since taller)
    objs.extend(add_windows(cx, 2.0, cz, w, h - 2.0, d, style))
    # Entrance
    objs.extend(add_entrance(cx, cz, w, d))
    # Landmark roof
    objs.extend(add_roof(cx, h, cz, w, d, style))
    # Corner turrets (cylindrical)
    for dx, dz in [(w * 0.5, d * 0.5), (-w * 0.5, d * 0.5),
                   (w * 0.5, -d * 0.5), (-w * 0.5, -d * 0.5)]:
        o = mkcyl("turret", cx + dx, 0, cz + dz, 0.7, h * 0.85)
        asgn("stone", o); objs.append(o)
        # Turret cap
        o = mkcyl("tcap", cx + dx, h * 0.85, cz + dz, 0.75, 0.4)
        asgn("concrete", o); objs.append(o)
    objs.extend(add_roof_details(cx, h, cz, w, d))
    return collapse_meshes(objs, "lm_bldg")


# -- Place buildings across all 20x20 blocks --
STYLES   = ["art_deco", "modern_glass", "brick", "futuristic", "neogothic"]
CELL_SZ  = BLOCK_SIZE / 5.0    # 10 units – 5×5 sub-grid inside each block
bldg_objs = []
# Keep track of used building colours per block row to avoid identical adj. heights
_last_h  = {}   # (bi, bj) -> last height  (simple adjacency guard)

for bi in range(N):
    for bj in range(N):
        ox = blk_ox(bi)
        oz = blk_oz(bj)

        # Corner cells always get landmark buildings
        corner_cells = {(0, 0), (0, 4), (4, 0), (4, 4)}
        # Choose 2–6 additional interior cells for regular buildings
        interior = [(r, c) for r in range(5) for c in range(5)
                    if (r, c) not in corner_cells]
        random.shuffle(interior)
        n_regular = random.randint(2, 6)
        regular_cells = interior[:n_regular]

        # -- Landmark buildings at corner cells --
        prev_h = _last_h.get((bi, bj), 0)
        for cr, cc in corner_cells:
            cx = ox + (cc + 0.5) * CELL_SZ
            cz = oz + (cr + 0.5) * CELL_SZ
            lh = random.uniform(30, 45)
            # Ensure height differs from previous neighbour (max 20 retries)
            for _ in range(20):
                if abs(lh - prev_h) >= 3:
                    break
                lh = random.uniform(30, 45)
            prev_h = lh
            lw = random.uniform(6, 9)
            ld = random.uniform(6, 9)
            bldg_objs.extend(build_landmark(cx, cz, lw, ld, lh))

        # -- Regular buildings at interior cells --
        prev_mat = None
        for cr, cc in regular_cells:
            cx = ox + (cc + 0.5) * CELL_SZ
            cz = oz + (cr + 0.5) * CELL_SZ
            h  = random.uniform(8, 30)
            # Ensure height differs from previous neighbour (max 20 retries)
            for _ in range(20):
                if abs(h - prev_h) >= 2:
                    break
                h = random.uniform(8, 30)
            prev_h = h
            w  = random.uniform(5, CELL_SZ * 0.82)
            d  = random.uniform(5, CELL_SZ * 0.82)
            style = random.choice(STYLES)
            bmat  = random.choice(BLDG_MATS)
            # Ensure material differs from previous building (max 10 retries)
            for _ in range(10):
                if bmat != prev_mat:
                    break
                bmat = random.choice(BLDG_MATS)
            prev_mat = bmat
            bldg_objs.extend(build_regular(cx, cz, w, d, h, style, bmat))

        _last_h[(bi, bj)] = prev_h

put(bldg_objs, "Grp_Buildings")
print("  Building objects: {}".format(len(bldg_objs)))
print("  Entrance records: {}".format(len(_entrances)))


# =============================================================================
# SECTION 7: TRAFFIC LIGHTS  (4 poles per intersection)
# =============================================================================
print("Section 7: Traffic lights...")
tl_objs = []


def make_traffic_light(px, pz, facing_x):
    """One traffic light pole with 3 signal lights."""
    objs = []
    # Pole
    o = mkcyl("tlpole", px, 0, pz, 0.12, 5.5)
    asgn("pole_m", o); objs.append(o)
    # Horizontal arm
    arm_len = 1.2
    ax = px + (arm_len * 0.5 if facing_x else 0)
    az = pz + (0 if facing_x else arm_len * 0.5)
    o = mkbox("tlarm", ax, 5.5, az,
              arm_len if facing_x else 0.12,
              0.12,
              0.12 if facing_x else arm_len)
    asgn("pole_m", o); objs.append(o)
    # Housing box
    hx = px + (arm_len if facing_x else 0)
    hz = pz + (0 if facing_x else arm_len)
    o = mkbox("tlbox", hx, 4.4, hz, 0.35, 1.2, 0.35)
    asgn("drk_mat", o); objs.append(o)
    # Three signal lights (red / yellow / green top to bottom)
    for k, (lmat, ly_off) in enumerate([("lt_red",  5.7),
                                         ("lt_yel",  5.3),
                                         ("lt_grn",  4.9)]):
        o = mkcyl("ltlight", hx, ly_off, hz, 0.12, 0.12)
        asgn(lmat, o); objs.append(o)
    return collapse_meshes(objs, "tl_asset")


for col in range(N + 1):
    for row in range(N + 1):
        ix, iz = road_cx(col), road_cz(row)
        offset = ROAD_W * 0.5 + SW_W * 0.5
        # Four poles, one at each quadrant of the intersection
        corners = [
            (ix - offset, iz - offset, True),
            (ix + offset, iz - offset, True),
            (ix - offset, iz + offset, False),
            (ix + offset, iz + offset, False),
        ]
        for px, pz, fx in corners:
            tl_objs.extend(make_traffic_light(px, pz, fx))

put(tl_objs, "Grp_TrafficLights")
print("  Traffic light objects: {}".format(len(tl_objs)))


# =============================================================================
# SECTION 8: BILLBOARDS  (30 along major roads)
# =============================================================================
print("Section 8: Billboards...")
bb_objs = []


def make_billboard(cx, by, cz, ry=0):
    """Double-sided billboard with two metal support legs."""
    objs = []
    bh, bw, bd = 4.0, 8.0, 0.3
    leg_h = by + 1.0
    # Left leg
    o = mkcyl("bleg", cx - bw * 0.35, 0, cz, 0.18, leg_h + bh * 0.5)
    asgn("bill_sp", o); objs.append(o)
    # Right leg
    o = mkcyl("bleg", cx + bw * 0.35, 0, cz, 0.18, leg_h + bh * 0.5)
    asgn("bill_sp", o); objs.append(o)
    # Face (front)
    mat = random.choice(BILL_MATS)
    o = mkbox("bface", cx, leg_h, cz - bd * 0.5, bw, bh, bd * 0.5, ry=ry)
    asgn(mat, o); objs.append(o)
    # Face (back, different colour)
    mat2 = random.choice(BILL_MATS)
    o = mkbox("bface", cx, leg_h, cz + bd * 0.5, bw, bh, bd * 0.5, ry=ry)
    asgn(mat2, o); objs.append(o)
    return collapse_meshes(objs, "billboard")


# Scatter 30 billboards along roads (sidewalk edge)
for _ in range(30):
    col  = random.randint(0, N)
    side = random.choice([-1, 1])
    cx_r = road_cx(col) + side * (ROAD_W * 0.5 + SW_W + 0.5)
    z_r  = OZ + random.uniform(0.05, 0.95) * CITY_SZ
    bb_objs.extend(make_billboard(cx_r, SWH, z_r, ry=0))

put(bb_objs, "Grp_Billboards")
print("  Billboard objects: {}".format(len(bb_objs)))


# =============================================================================
# SECTION 9: TREES  (15–20 per block along sidewalks)
# =============================================================================
print("Section 9: Trees...")
tree_objs = []


def make_tree(cx, cz):
    """Simple stylized tree: brown trunk + 2-3 green foliage spheres."""
    objs = []
    th = random.uniform(2.5, 4.5)
    tr = random.uniform(0.18, 0.30)
    # Trunk
    o = mkcyl("trunk", cx, SWH, cz, tr, th)
    asgn("trunk_c", o); objs.append(o)
    # Foliage (2–3 spheres stacked/offset)
    n_sph = random.randint(2, 3)
    for k in range(n_sph):
        fr = random.uniform(0.9, 1.6)
        fy = SWH + th + k * fr * 0.55
        fx = cx + random.uniform(-0.3, 0.3)
        fz = cz + random.uniform(-0.3, 0.3)
        fmat = "foliage" if k % 2 == 0 else "foliage2"
        o = mksph("foliage", fx, fy, fz, fr)
        asgn(fmat, o); objs.append(o)
    return collapse_meshes(objs, "tree")


for bi in range(N):
    for bj in range(N):
        n_trees = random.randint(15, 20)
        ox = blk_ox(bi)
        oz = blk_oz(bj)

        for _ in range(n_trees):
            edge = random.randint(0, 3)
            if edge == 0:   # South side
                tx = ox + random.uniform(2, BLOCK_SIZE - 2)
                tz = oz - SW_W * 0.5
            elif edge == 1: # North side
                tx = ox + random.uniform(2, BLOCK_SIZE - 2)
                tz = oz + BLOCK_SIZE + SW_W * 0.5
            elif edge == 2: # West side
                tx = ox - SW_W * 0.5
                tz = oz + random.uniform(2, BLOCK_SIZE - 2)
            else:           # East side
                tx = ox + BLOCK_SIZE + SW_W * 0.5
                tz = oz + random.uniform(2, BLOCK_SIZE - 2)
            tree_objs.extend(make_tree(tx, tz))

put(tree_objs, "Grp_Trees")
print("  Tree objects: {}".format(len(tree_objs)))


# =============================================================================
# SECTION 10: STREET FURNITURE  (benches, trash cans, lamp posts)
# =============================================================================
print("Section 10: Street furniture...")
furn_objs = []


def make_bench(cx, cz, ry=0):
    """Simple park bench: seat + back + two legs."""
    objs = []
    LEG_H = 0.35   # legs lift seat above sidewalk surface
    # Legs (rest on sidewalk surface)
    for lx in (-0.8, 0.8):
        o = mkbox("bleg", cx + lx, SWH, cz, 0.1, LEG_H, 0.55, ry=ry)
        asgn("metal", o); objs.append(o)
    # Seat (on top of legs)
    o = mkbox("bseat", cx, SWH + LEG_H, cz, 2.0, 0.12, 0.6, ry=ry)
    asgn("bench_m", o); objs.append(o)
    # Back rest
    o = mkbox("bback", cx, SWH + LEG_H + 0.17, cz + 0.24, 2.0, 0.45, 0.08, ry=ry)
    asgn("bench_m", o); objs.append(o)
    return collapse_meshes(objs, "bench")


def make_trash_can(cx, cz):
    """Cylindrical trash can."""
    objs = []
    o = mkcyl("trash", cx, SWH, cz, 0.25, 0.9)
    asgn("trash_m", o); objs.append(o)
    # Lid ring
    o = mkcyl("lid", cx, SWH + 0.9, cz, 0.27, 0.06)
    asgn("drk_mat", o); objs.append(o)
    return collapse_meshes(objs, "trashcan")


def make_lamp_post(cx, cz):
    """Street lamp: pole + glowing spherical cap."""
    objs = []
    # Pole
    o = mkcyl("lamppole", cx, SWH, cz, 0.08, 6.5)
    asgn("lamp_m", o); objs.append(o)
    # Horizontal arm
    o = mkbox("lamparm", cx + 0.4, SWH + 6.5, cz, 0.8, 0.08, 0.08)
    asgn("lamp_m", o); objs.append(o)
    # Glowing cap (sphere)
    o = mksph("lampgl", cx + 0.8, SWH + 6.5, cz, 0.25)
    asgn("lamp_gl", o); objs.append(o)
    return collapse_meshes(objs, "lamppost")


# Place furniture at regular intervals along sidewalks
FURN_SPACING = 12.0
for col in range(N + 1):
    cx = road_cx(col)
    for side in (-1, 1):
        sx = cx + side * (ROAD_W * 0.5 + SW_W * 0.5)
        z  = OZ + 5.0
        idx = 0
        while z < OZ + CITY_SZ - 5.0:
            if idx % 3 == 0:
                furn_objs.extend(make_lamp_post(sx, z))
            elif idx % 3 == 1:
                furn_objs.extend(make_bench(sx, z, ry=90))
            else:
                furn_objs.extend(make_trash_can(sx, z))
            idx += 1
            z += FURN_SPACING

for row in range(N + 1):
    cz = road_cz(row)
    for side in (-1, 1):
        sz = cz + side * (ROAD_W * 0.5 + SW_W * 0.5)
        x  = OX + 5.0
        idx = 0
        while x < OX + CITY_SZ - 5.0:
            if idx % 3 == 0:
                furn_objs.extend(make_lamp_post(x, sz))
            elif idx % 3 == 1:
                furn_objs.extend(make_bench(x, sz))
            else:
                furn_objs.extend(make_trash_can(x, sz))
            idx += 1
            x += FURN_SPACING

put(furn_objs, "Grp_StreetFurniture")
print("  Furniture objects: {}".format(len(furn_objs)))


# =============================================================================
# SECTION 11: CARS  (150–200 parked & driving)
# =============================================================================
print("Section 11: Cars...")
car_objs = []


def make_car(cx, cz, ry=0, paint=None):
    """Box-body car with rounded top, 4 wheels and window panels."""
    objs = []
    if paint is None:
        paint = random.choice(CAR_MATS)
    # Body
    o = mkbox("carbody", cx, SWH, cz, 3.8, 1.0, 1.8, ry=ry)
    asgn(paint, o); objs.append(o)
    # Roof (slightly narrower/shorter, centred higher)
    o = mkbox("carroof", cx, SWH + 1.0, cz, 2.2, 0.75, 1.6, ry=ry)
    asgn(paint, o); objs.append(o)
    # Front & rear windshields (thin blue panels)
    for wz_off in (-1.4, 1.4):
        o = mkbox("carwin", cx, SWH + 1.25, cz + wz_off, 1.8, 0.6, 0.08, ry=ry)
        asgn("car_win", o); objs.append(o)
    # Four wheels (cylinders lying on their side; rz_=90 makes disk face outward).
    # We need the wheel centre to sit at y = WHEEL_R above the ground so the
    # bottom of the tire (y=0) just touches the road surface.
    # mkcyl places the object centre at  by + h/2,  so:
    #   wheel_centre_y = wheel_by + WHEEL_T / 2  = WHEEL_R
    #   => wheel_by = WHEEL_R - WHEEL_T / 2
    WHEEL_R, WHEEL_T = 0.28, 0.22
    wheel_by = WHEEL_R - WHEEL_T * 0.5   # = 0.17 (bottom of lying cylinder)
    for wx_off in (-1.3, 1.3):
        for wz_off2 in (-0.75, 0.75):
            o = mkcyl("wheel",
                      cx + wx_off, wheel_by, cz + wz_off2,
                      WHEEL_R, WHEEL_T, rz_=90)
            asgn("tire_c", o); objs.append(o)
    return collapse_meshes(objs, "car")


# Scatter cars: parked along road edges and a few "driving" mid-lane
n_cars = random.randint(150, 200)
for _ in range(n_cars):
    lane = random.choice(["parked_v", "parked_h", "driving_v", "driving_h"])
    if lane == "parked_v":
        col   = random.randint(0, N)
        cx    = road_cx(col) + random.choice([-1, 1]) * ROAD_W * 0.32
        cz    = OZ + random.uniform(0.02, 0.98) * CITY_SZ
        ry    = 0
    elif lane == "parked_h":
        row   = random.randint(0, N)
        cz    = road_cz(row) + random.choice([-1, 1]) * ROAD_W * 0.32
        cx    = OX + random.uniform(0.02, 0.98) * CITY_SZ
        ry    = 90
    elif lane == "driving_v":
        col   = random.randint(0, N)
        cx    = road_cx(col)
        cz    = OZ + random.uniform(0.02, 0.98) * CITY_SZ
        ry    = 0
    else:
        row   = random.randint(0, N)
        cz    = road_cz(row)
        cx    = OX + random.uniform(0.02, 0.98) * CITY_SZ
        ry    = 90
    car_objs.extend(make_car(cx, cz, ry=ry))

put(car_objs, "Grp_Cars")
print("  Car objects: {}".format(len(car_objs)))


# =============================================================================
# SECTION 12: COMMERCIAL STOREFRONTS  (30 % of buildings)
# =============================================================================
print("Section 12: Commercial storefronts...")
store_objs = []

# Pick 30 % of recorded entrances
random.shuffle(_entrances)
n_stores = max(1, int(len(_entrances) * 0.30))
store_sample = _entrances[:n_stores]

store_types = ["coffee", "restaurant", "barbershop", "club"]


def make_coffee_shop(cx, fz, w):
    """Outdoor table + 2 chairs + sign."""
    objs = []
    # Table
    o = mkbox("ctable", cx, SWH, fz - 2.0, 1.0, 0.7, 1.0)
    asgn("bench_m", o); objs.append(o)
    # Two chairs
    for lx in (-0.6, 0.6):
        o = mkbox("cchair", cx + lx, SWH, fz - 2.0, 0.5, 0.5, 0.5)
        asgn("bench_m", o); objs.append(o)
    # Coffee sign panel
    o = mkbox("csign", cx, 2.6, fz - 0.15, min(w * 0.6, 3.0), 0.6, 0.1)
    asgn("sign_m", o); objs.append(o)
    return collapse_meshes(objs, "shop_coffee")


def make_restaurant(cx, fz, w):
    """Red awning, menu board, outdoor planter."""
    objs = []
    # Red awning
    o = mkbox("rawn", cx, 2.5, fz - 1.2, min(w * 0.8, 5.0), 0.25, 2.4)
    asgn("awning_r", o); objs.append(o)
    # Menu board (thin flat rectangle)
    o = mkbox("menu", cx - w * 0.3, SWH, fz - 2.0, 0.08, 1.4, 0.9)
    asgn("drk_mat", o); objs.append(o)
    # Planter (green box)
    o = mkbox("plntr", cx + w * 0.25, SWH, fz - 2.0, 0.8, 0.5, 0.8)
    asgn("planter_m", o); objs.append(o)
    return collapse_meshes(objs, "shop_rest")


def make_barbershop(cx, fz, w):
    """Barber pole (striped cylinder) + small sign."""
    objs = []
    # Barber pole — single cylinder; colour it red/white alternating
    # (3-colour stripe represented via 3 stacked short cylinders)
    pole_r = 0.1
    for k, bmat in enumerate(["barber_r", "barber_w", "barber_b",
                               "barber_r", "barber_w"]):
        o = mkcyl("bpole", cx - w * 0.4, SWH + k * 0.5, fz - 0.25, pole_r, 0.5)
        asgn(bmat, o); objs.append(o)
    # Sign
    o = mkbox("bsign", cx, 2.6, fz - 0.15, min(w * 0.55, 2.5), 0.55, 0.1)
    asgn("sign_m", o); objs.append(o)
    return collapse_meshes(objs, "shop_barber")


def make_club(cx, fz, w):
    """LED stripe bands on facade + queue barrier (2 posts + rope)."""
    objs = []
    # LED bands — three thin horizontal bars on facade
    for ky in (0.8, 1.6, 2.4):
        o = mkbox("led", cx, ky, fz - 0.05, min(w * 0.9, 6.0), 0.12, 0.06)
        asgn("bill_m", o); objs.append(o)
    # Queue barrier posts
    for lx in (-1.5, 1.5):
        o = mkcyl("qpost", cx + lx, SWH, fz - 2.5, 0.07, 1.0)
        asgn("metal", o); objs.append(o)
    # Rope between posts
    o = mkbox("rope", cx, SWH + 1.0, fz - 2.5, 3.0, 0.06, 0.06)
    asgn("rope_m", o); objs.append(o)
    return collapse_meshes(objs, "shop_club")


STORE_FN = {
    "coffee":      make_coffee_shop,
    "restaurant":  make_restaurant,
    "barbershop":  make_barbershop,
    "club":        make_club,
}

for (cx, cz, fz, bw) in store_sample:
    stype = random.choice(store_types)
    store_objs.extend(STORE_FN[stype](cx, fz, bw))

put(store_objs, "Grp_Storefronts")
print("  Storefront objects: {}".format(len(store_objs)))


# =============================================================================
# SECTION 13: CRANES  (8 construction cranes)
# =============================================================================
print("Section 13: Cranes...")
crane_objs = []


def make_crane(cx, cz, h=40.0, jib_len=18.0):
    """Tower crane: lattice tower, horizontal jib, cab, and hook cable."""
    objs = []
    # Tower (main vertical column, hollow lattice simulated by 4 corner rods)
    col_r = 0.25
    col_sp = 1.0
    for dx, dz in [(-col_sp, -col_sp), (col_sp, -col_sp),
                   (-col_sp,  col_sp), (col_sp,  col_sp)]:
        o = mkcyl("ctwr", cx + dx, 0, cz + dz, col_r, h)
        asgn("crane_y", o); objs.append(o)
    # Cross-braces every 4 units up the tower
    for ky in range(0, int(h), 4):
        o = mkbox("cbrace", cx, ky + 2, cz, col_sp * 2 + 0.5, 0.15, 0.15)
        asgn("crane_y", o); objs.append(o)
        o = mkbox("cbrace", cx, ky + 2, cz, 0.15, 0.15, col_sp * 2 + 0.5)
        asgn("crane_y", o); objs.append(o)
    # Cab (operator's cabin on top of tower)
    o = mkbox("ccab", cx, h, cz, 2.5, 2.2, 2.5)
    asgn("crane_k", o); objs.append(o)
    # Cab window
    o = mkbox("ccabwin", cx, h + 1.0, cz - 1.3, 1.8, 1.0, 0.1)
    asgn("glass", o); objs.append(o)
    # Horizontal jib (main boom)
    jib_cx = cx + jib_len * 0.5
    o = mkbox("cjib", jib_cx, h + 2.2, cz, jib_len, 0.5, 0.5)
    asgn("crane_y", o); objs.append(o)
    # Counter-jib (shorter, opposite side)
    cj_len = jib_len * 0.38
    cj_cx  = cx - cj_len * 0.5
    o = mkbox("ccjib", cj_cx, h + 2.2, cz, cj_len, 0.4, 0.4)
    asgn("crane_y", o); objs.append(o)
    # Counterweight
    o = mkbox("ccwt", cx - cj_len, h + 2.2, cz, 2.0, 1.2, 1.5)
    asgn("concrete", o); objs.append(o)
    # Trolley on jib
    tr_x = cx + jib_len * 0.65
    o = mkbox("ctrlly", tr_x, h + 2.2, cz, 0.8, 0.5, 0.8)
    asgn("crane_k", o); objs.append(o)
    # Hook cable
    o = mkcyl("ccable", tr_x, SWH, cz, 0.04, h + 2.2 - SWH)
    asgn("cable_m", o); objs.append(o)
    # Hook
    o = mkbox("chook", tr_x, SWH, cz, 0.3, 0.5, 0.3)
    asgn("metal", o); objs.append(o)
    return collapse_meshes(objs, "crane")


# Place 8 cranes at scattered block positions
crane_positions = random.sample(
    [(bi, bj) for bi in range(1, N - 1) for bj in range(1, N - 1)], 8
)
for bi, bj in crane_positions:
    cx = blk_cx(bi) + random.uniform(-8, 8)
    cz = blk_cz(bj) + random.uniform(-8, 8)
    crane_h   = random.uniform(35, 55)
    crane_jib = random.uniform(15, 22)
    crane_objs.extend(make_crane(cx, cz, crane_h, crane_jib))

put(crane_objs, "Grp_Cranes")
print("  Crane objects: {}".format(len(crane_objs)))


# =============================================================================
# SECTION 14: MISC DETAILS
#   Manhole covers, fire hydrants, dumpsters, power/telephone poles
# =============================================================================
print("Section 14: Misc details...")
misc_objs = []


def make_manhole(cx, cz):
    """Flat black circle (manhole cover) on sidewalk."""
    o = mkcyl("mhole", cx, SWH - 0.01, cz, 0.45, 0.04)
    asgn("manhole_m", o)
    return [o]


def make_hydrant(cx, cz):
    """Red fire hydrant: body + two side nubs."""
    objs = []
    o = mkcyl("hyd_b", cx, SWH, cz, 0.18, 0.7)
    asgn("hydrant_m", o); objs.append(o)
    # Cap dome
    o = mksph("hyd_cap", cx, SWH + 0.7, cz, 0.20)
    asgn("hydrant_m", o); objs.append(o)
    # Side nubs
    for side in (-1, 1):
        o = mkcyl("hyd_n", cx + side * 0.22, SWH + 0.3, cz, 0.07, 0.2, rz_=90)
        asgn("hydrant_m", o); objs.append(o)
    return collapse_meshes(objs, "hydrant")


def make_dumpster(cx, cz, ry=0):
    """Green open-top dumpster box."""
    objs = []
    # Body
    o = mkbox("dump", cx, SWH, cz, 2.5, 1.2, 1.2, ry=ry)
    asgn("dumpster_m", o); objs.append(o)
    # Open interior (just show rim — thin top frame)
    o = mkbox("dumplid", cx, SWH + 1.2, cz, 2.6, 0.1, 1.3, ry=ry)
    asgn("drk_mat", o); objs.append(o)
    return collapse_meshes(objs, "dumpster")


def make_power_pole(cx, cz):
    """Wooden power/telephone pole with crossbar and wires."""
    objs = []
    # Post
    o = mkcyl("ppole", cx, 0, cz, 0.12, 9.0)
    asgn("wood_m", o); objs.append(o)
    # Crossbar
    o = mkbox("pbar", cx, 8.8, cz, 3.5, 0.15, 0.15)
    asgn("wood_m", o); objs.append(o)
    # Insulators (small cylinders on bar ends)
    for lx in (-1.6, 1.6):
        o = mkcyl("pins", cx + lx, 8.95, cz, 0.06, 0.2)
        asgn("wht_mat", o); objs.append(o)
    return collapse_meshes(objs, "powerpole")


# Scatter misc details across sidewalks
for bi in range(N):
    for bj in range(N):
        ox = blk_ox(bi)
        oz = blk_oz(bj)
        # Manhole covers on sidewalks (1–2 per block)
        for _ in range(random.randint(1, 2)):
            tx = ox + random.uniform(0, BLOCK_SIZE)
            tz = oz - SW_W * 0.3
            misc_objs.extend(make_manhole(tx, tz))
        # Fire hydrants (1 per block)
        hx = ox + random.uniform(2, BLOCK_SIZE - 2)
        hz = oz - SW_W * 0.5
        misc_objs.extend(make_hydrant(hx, hz))
        # Dumpster in back alley (every 4th block)
        if (bi + bj) % 4 == 0:
            dx = ox + random.uniform(4, BLOCK_SIZE - 4)
            dz = oz + BLOCK_SIZE * 0.85
            misc_objs.extend(make_dumpster(dx, dz, ry=random.choice([0, 90])))

# Power poles along sidewalks (every 20 units along vertical roads)
PP_SPACING = 20.0
for col in range(N + 1):
    cx = road_cx(col) + ROAD_W * 0.5 + SW_W
    z  = OZ + 5.0
    while z < OZ + CITY_SZ - 5.0:
        misc_objs.extend(make_power_pole(cx, z))
        z += PP_SPACING

put(misc_objs, "Grp_MiscDetails")
print("  Misc-detail objects: {}".format(len(misc_objs)))


# =============================================================================
# DONE — report totals
# =============================================================================
total_grp_children = 0
for gn, g in _grps.items():
    kids = cmds.listRelatives(g, children=True) or []
    total_grp_children += len(kids)

print("\n=== Procedural City Generation Complete ===")
print("Master group : {}".format(MASTER))
print("Sub-groups   : {}".format(len(_grps)))
print("Total objects in sub-groups: {}".format(total_grp_children))
print("Random seed  : 42")
print("Grid         : {}x{} blocks ({} units wide)".format(N, N, CITY_SZ))
print("===========================================\n")
