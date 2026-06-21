#!/usr/bin/env python3
"""Generate a new Pixel Agents office layout (default-layout-1.json).

Builds a clean open-plan office: a row of agent workstations up top, a cozy
lounge with sofas + coffee table, a meeting nook, and decor around the walls.
Validates every placement against the game's footprint/collision rules so the
output is guaranteed loadable.
"""
import json, os, time, random

random.seed(7)

# ---- tile types ----------------------------------------------------------
WALL, VOID = 0, 255
F_BLUE, F_WARM, F_GREY = 1, 7, 9  # floor patterns reused from the bundled default

COLORS = {
    WALL:   {"h": 214, "s": 30, "b": -100, "c": -55},
    F_BLUE: {"h": 209, "s": 39, "b": -25,  "c": -80},
    F_WARM: {"h": 25,  "s": 48, "b": -43,  "c": -88},
    F_GREY: {"h": 209, "s": 0,  "b": -16,  "c": -8},
}

# ---- asset footprints / flags (from furniture manifests) -----------------
# type: (w, h, backgroundTiles, canPlaceOnWalls, canPlaceOnSurfaces)
FP = {
    "DESK_FRONT": (3, 2, 1, False, False),
    "PC_FRONT_OFF": (1, 2, 1, False, True),
    "WOODEN_CHAIR_BACK": (1, 2, 1, False, False),
    "CUSHIONED_CHAIR_BACK": (1, 1, 0, False, False),
    "TABLE_FRONT": (3, 4, 1, False, False),
    "WOODEN_CHAIR_SIDE": (1, 2, 1, False, False),
    "PC_SIDE": (1, 2, 1, False, True),
    "COFFEE_TABLE": (2, 2, 0, False, False),
    "SOFA_FRONT": (2, 1, 0, False, False),
    "SOFA_BACK": (2, 1, 0, False, False),
    "SOFA_SIDE": (1, 2, 0, False, False),
    "COFFEE": (1, 1, 0, False, True),
    "SMALL_TABLE_FRONT": (2, 2, 1, False, False),
    "CUSHIONED_BENCH": (1, 1, 0, False, False),
    "LARGE_PLANT": (2, 3, 2, False, False),
    "PLANT": (1, 2, 1, False, False),
    "PLANT_2": (1, 2, 1, False, False),
    "CACTUS": (1, 2, 1, False, False),
    "POT": (1, 1, 0, False, False),
    "BIN": (1, 1, 0, False, False),
    # wall items (bottom row must land on a WALL tile)
    "LARGE_PAINTING": (2, 2, 0, True, False),
    "SMALL_PAINTING": (1, 2, 0, True, False),
    "SMALL_PAINTING_2": (1, 2, 0, True, False),
    "WHITEBOARD": (2, 2, 0, True, False),
    "CLOCK": (1, 2, 0, True, False),
    "BOOKSHELF": (2, 1, 0, True, False),
    "DOUBLE_BOOKSHELF": (2, 2, 0, True, False),
    "HANGING_PLANT": (1, 2, 0, True, True),
}

COLS, ROWS = 24, 19
TOP_WALL = 9          # top wall row; rows 0..8 are VOID buffer above
BOT_WALL = ROWS - 1   # bottom wall row (18)

tiles = [VOID] * (COLS * ROWS)
def idx(c, r): return r * COLS + c
def get(c, r): return tiles[idx(c, r)]
def setile(c, r, v): tiles[idx(c, r)] = v

# ---- carve the room ------------------------------------------------------
# top + bottom walls
for c in range(COLS):
    setile(c, TOP_WALL, WALL)
    setile(c, BOT_WALL, WALL)
# side walls + floor interior
for r in range(TOP_WALL + 1, BOT_WALL):
    setile(0, r, WALL)
    setile(COLS - 1, r, WALL)
    for c in range(1, COLS - 1):
        setile(c, r, F_BLUE)

# lounge zone (warm floor): right third, lower half
for r in range(13, BOT_WALL):
    for c in range(15, COLS - 1):
        setile(c, r, F_WARM)
# entrance runner (grey) down the middle-bottom
for r in range(13, BOT_WALL):
    for c in (11, 12):
        setile(c, r, F_GREY)

# ---- placement + validation ---------------------------------------------
furniture = []
# occupancy of "solid" tiles (blocks walking + placement), excludes bg/surface rows
solid = set()
desk_tiles = set()  # tiles belonging to desks/tables (surface items may overlap)

def footprint(c, r, w, h):
    return [(cc, rr) for rr in range(r, r + h) for cc in range(c, c + w)]

def place(type_, c, r, color=None, mirror=False):
    w, h, bg, wall, surf = FP[type_]
    cells = footprint(c, r, w, h)
    if wall:
        # bottom row must be on WALL tiles; upper rows may be VOID/offmap
        for (cc, rr) in cells:
            if rr == r + h - 1:
                if not (0 <= cc < COLS and 0 <= rr < ROWS and get(cc, rr) == WALL):
                    raise ValueError(f"{type_} bottom not on wall at {cc},{rr}")
            # don't block walking for wall items
    else:
        for (cc, rr) in cells:
            if not (0 <= cc < COLS and 0 <= rr < ROWS):
                raise ValueError(f"{type_} offmap at {cc},{rr}")
            t = get(cc, rr)
            if t in (WALL, VOID):
                raise ValueError(f"{type_} on wall/void at {cc},{rr}")
        # collision: solid rows of this item vs existing solids (skip own bg rows)
        for i, (cc, rr) in enumerate(cells):
            row_in_fp = rr - r
            is_bg = row_in_fp < bg
            if is_bg:
                continue
            if surf and (cc, rr) in desk_tiles:
                continue  # surface item allowed over a desk tile
            if (cc, rr) in solid:
                raise ValueError(f"{type_} collides at {cc},{rr}")
        # commit solids (non-bg, non-surface-over-desk)
        for (cc, rr) in cells:
            if (rr - r) < bg:
                continue
            if surf and (cc, rr) in desk_tiles:
                continue
            solid.add((cc, rr))
        if type_ in ("DESK_FRONT", "TABLE_FRONT", "SMALL_TABLE_FRONT", "COFFEE_TABLE"):
            for (cc, rr) in cells:
                desk_tiles.add((cc, rr))
    uid = f"f-{int(time.time()*1000)}-{random.randint(1000,9999)}-{len(furniture)}"
    item = {"uid": uid, "type": (type_ + ":left") if mirror else type_, "col": c, "row": r}
    if color:
        item["color"] = color
    furniture.append(item)

# === workstations (top): desk above, chair below -> agents face UP =========
# three pods along the top floor band
for base in (2, 9, 16):
    place("DESK_FRONT", base, 10)
    place("PC_FRONT_OFF", base + 1, 10)            # sits on the desk surface
    place("WOODEN_CHAIR_BACK", base + 1, 12)        # back -> faces up toward desk

# === big collaborative table (left-lower) =================================
place("TABLE_FRONT", 2, 14, color={"h": 25, "s": 30, "b": -30, "c": -60})
place("PC_SIDE", 2, 14)                 # left side of table, on surface
place("PC_SIDE", 4, 14, mirror=True)    # right side
place("WOODEN_CHAIR_SIDE", 1, 15)               # left chair faces right
place("WOODEN_CHAIR_SIDE", 5, 15, mirror=True)  # right chair faces left

# === lounge (warm zone, right) ============================================
place("COFFEE_TABLE", 18, 15)
place("COFFEE", 18, 15)
place("SOFA_FRONT", 18, 14)             # above table, faces down
place("SOFA_SIDE", 17, 15)              # left of table, faces right
place("SOFA_SIDE", 20, 15, mirror=True) # right of table, faces left

# === meeting nook chairs ===================================================
place("SMALL_TABLE_FRONT", 14, 10)
place("CUSHIONED_CHAIR_BACK", 14, 12)
place("CUSHIONED_CHAIR_BACK", 15, 12)

# === decor: plants / bins on the floor ====================================
place("LARGE_PLANT", 21, 10)
place("PLANT", 8, 16)
place("CACTUS", 22, 12)
place("BIN", 1, 17)
place("POT", 13, 11)

# === wall decor (bottom row of footprint lands on TOP_WALL=9) =============
def wall_row(type_):  # so bottom row sits on the wall
    return TOP_WALL - (FP[type_][1] - 1)
place("DOUBLE_BOOKSHELF", 1, wall_row("DOUBLE_BOOKSHELF"))
place("LARGE_PAINTING", 4, wall_row("LARGE_PAINTING"))
place("CLOCK", 7, wall_row("CLOCK"))
place("WHITEBOARD", 10, wall_row("WHITEBOARD"))
place("SMALL_PAINTING", 13, wall_row("SMALL_PAINTING"))
place("HANGING_PLANT", 17, wall_row("HANGING_PLANT"))
place("SMALL_PAINTING_2", 19, wall_row("SMALL_PAINTING_2"))
place("BOOKSHELF", 21, wall_row("BOOKSHELF"))

# ---- tileColors parallel array ------------------------------------------
tileColors = []
for r in range(ROWS):
    for c in range(COLS):
        t = get(c, r)
        tileColors.append(COLORS.get(t) if t != VOID else None)

layout = {
    "version": 1,
    "cols": COLS,
    "rows": ROWS,
    "layoutRevision": 2,
    "tiles": tiles,
    "tileColors": tileColors,
    "furniture": furniture,
}

out = os.path.join(os.path.dirname(__file__), "..", "webview-ui", "public", "assets", "default-layout-1.json")
out = os.path.abspath(out)
with open(out, "w") as f:
    json.dump(layout, f, indent=2)

# ---- preview -------------------------------------------------------------
sym = {WALL: "#", VOID: ".", F_BLUE: "1", F_WARM: "7", F_GREY: "9"}
print("\n".join("".join(sym.get(get(c, r), "?") for c in range(COLS)) for r in range(ROWS)))
print(f"\n{len(furniture)} furniture items placed -> {out}")
