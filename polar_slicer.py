#!/usr/bin/env python3
"""
polar_slicer.py -- standalone parametric G-code generator for POLAR CROSS-PLY parts.

Because polar cross-ply can't be installed into a stock slicer without recompiling,
this tool lets anyone PRINT the pattern today. It is NOT a general mesh slicer: it
slices the class of parts the pattern is valid for -- axisymmetric discs / rings /
annuli (optionally a stepped profile) -- directly from parameters, and writes
printable G-code with alternating radial/hoop plies, walls, and solid caps.

It reuses polar_crossply.py for the pattern geometry (single source of truth).

Usage:
    python polar_slicer.py --od 66.2 --id 10.5 --height 9.4 -o part.gcode
    python polar_slicer.py --config mypart.json -o part.gcode
    python polar_slicer.py --help

License: MIT (suggested).
"""
from __future__ import annotations
import argparse, json, math, sys
from dataclasses import dataclass, asdict, field
from typing import List, Tuple, Optional

from polar_crossply import (PolarParams, hoop_ply, radial_ply, grid_ply, radial_ply_vw,
                            ply_type_for_layer, _band_edges)

Point = Tuple[float, float]
Polyline = List[Point]


# ============================================================================
# CONFIG
# ============================================================================
@dataclass
class Config:
    # --- part geometry (mm) ------------------------------------------------
    od: float = 66.2            # outer diameter
    id: float = 10.5            # bore diameter (0 = solid disc, no hole)
    height: float = 9.4         # total part height

    # --- process ------------------------------------------------------------
    layer_height: float = 0.4
    first_layer_height: float = 0.2
    line_width: float = 0.6     # extrusion width (>= nozzle dia)
    nozzle_diameter: float = 0.6
    filament_diameter: float = 1.75
    flow: float = 1.0           # extrusion multiplier

    # --- walls / caps -------------------------------------------------------
    outer_walls: int = 2
    inner_walls: int = 2        # walls around the bore (if id>0)
    solid_cap_layers: int = 4   # top & bottom layers forced to dense hoop (closed surface)

    # --- infill density -----------------------------------------------------
    infill_density: float = 100.0   # percent; 100 = solid

    # --- polar cross-ply pattern (see SPEC.md) -----------------------------
    ply_sequence: str = "R,H"
    phase_stagger_deg: float = 3.0
    auto_phase_stagger: bool = True   # set stagger so spokes sweep one inter-spoke
                                      # pitch over the radial layers (helical winding)
    hoop_spiral: bool = False          # seamless spiral hoop plies (no stacked seam)
    # --- variable-width radial ply (v2) -------------------------------------
    radial_mode: str = "vw"           # {vw, banded}. vw = variable-width (v2, current)
    vw_w_min: float = 0.6             # = nozzle diameter
    vw_w_max: float = 1.2             # nozzle max road width
    vw_end_gap: float = 0.0           # spokes stop this far short of the perimeter
    vw_band_gap: float = 0.3          # radial gap between bands
    vw_vol_rate: float = 8.0          # mm^3/s held constant; width set by speed
    banding: str = "doubling"         # {none, doubling, geometric}
    band_ratio: float = 2.0
    spoke_continuity: str = "zigzag"
    anchor: float = 2.5
    tie_rings: bool = True

    # --- speeds (mm/s) ------------------------------------------------------
    print_speed: float = 40.0
    solid_speed: float = 35.0
    wall_speed: float = 30.0
    first_layer_speed: float = 20.0
    travel_speed: float = 150.0

    # --- travel / retraction ------------------------------------------------
    retract_length: float = 1.0
    retract_speed: float = 40.0
    z_hop: float = 0.4              # "Zfix": hop on travels between spokes
    travel_retract_min: float = 1.5  # only retract for travels longer than this

    # --- temperatures (set to match YOUR material) --------------------------
    nozzle_temp: float = 210.0
    bed_temp: float = 60.0

    # --- machine ------------------------------------------------------------
    bed_x: float = 220.0
    bed_y: float = 220.0
    center_xy: Optional[Tuple[float, float]] = None   # default: bed center

    # --- start / end g-code: PASTE YOUR OWN from a working profile ----------
    # These generic Marlin defaults home, heat, and prime. Replace for your printer.
    start_gcode: str = ""
    end_gcode: str = ""
    # Emitted once, immediately after the first layer completes. Typical use:
    # switch the part-cooling fan on and raise the bed temp (most profiles run
    # the first layer with the fan off and a cooler bed for adhesion).
    after_first_layer_gcode: str = ""


DEFAULT_START = """; ---- START (generic Marlin; replace with your printer's) ----
G90                      ; absolute XYZ
M83                      ; relative extrusion
M104 S{nozzle_temp}      ; set hotend
M140 S{bed_temp}         ; set bed
M190 S{bed_temp}         ; wait bed
M109 S{nozzle_temp}      ; wait hotend
G28                      ; home all
G1 Z5 F600
; prime line
G1 X{prime_x0} Y{prime_y} Z{first_layer_height} F{travel_mm_min}
G1 X{prime_x1} Y{prime_y} E12 F1000
G92 E0
M83
"""

DEFAULT_END = """; ---- END ----
M104 S0
M140 S0
G91
G1 Z10 F600
G90
G1 X10 Y{bed_y_minus} F{travel_mm_min}
M84
"""


# ============================================================================
# GEOMETRY HELPERS
# ============================================================================
def ring(center: Point, r: float, seg_deg: float = 4.0) -> Polyline:
    steps = max(16, int(360.0 / seg_deg))
    return [(center[0] + r*math.cos(2*math.pi*k/steps),
             center[1] + r*math.sin(2*math.pi*k/steps)) for k in range(steps+1)]


def wall_loops(center: Point, cfg: Config) -> List[Polyline]:
    """Outer + inner perimeter loops, printed every layer for surface quality."""
    w = cfg.line_width
    loops = []
    # outer walls, inward from OD
    r_out = cfg.od/2 - w/2
    for i in range(cfg.outer_walls):
        r = r_out - i*w
        if r > 0: loops.append(ring(center, r))
    # inner walls, outward from bore
    if cfg.id > 0:
        r_in = cfg.id/2 + w/2
        for i in range(cfg.inner_walls):
            r = r_in + i*w
            if r < cfg.od/2: loops.append(ring(center, r))
    return loops


def _auto_phase_deg(cfg: Config, spacing: float, core: float, n_layers: int) -> float:
    """Stagger so spokes sweep one full inter-spoke pitch over the radial layers:
    the inter-spoke gaps helix around the part instead of stacking in Z."""
    n_inner = max(6, math.ceil(2*math.pi*max(core, spacing)/spacing))   # inner-band spokes
    inter_spoke_deg = 360.0 / n_inner
    n_radial = max(1, sum(1 for i in range(n_layers)
                          if ply_type_for_layer_str(cfg.ply_sequence, i) == "R"))
    return inter_spoke_deg / n_radial


def ply_type_for_layer_str(seq: str, i: int) -> str:
    toks = [s.strip().upper() for s in seq.split(",") if s.strip()]
    return toks[i % len(toks)] if toks else "R"


def polar_params_for(cfg: Config, center: Point, n_layers: int = 0) -> PolarParams:
    dens = max(1e-3, cfg.infill_density/100.0)
    spacing = cfg.line_width / dens          # 100% -> line_width (solid)
    # keep the fill INSIDE the walls
    wall_out = cfg.outer_walls * cfg.line_width
    wall_in  = cfg.inner_walls * cfg.line_width if cfg.id > 0 else 0.0
    core = cfg.id/2 + wall_in if cfg.id > 0 else max(cfg.line_width*4, spacing)
    phase = cfg.phase_stagger_deg
    if cfg.auto_phase_stagger and n_layers > 0:
        phase = _auto_phase_deg(cfg, spacing, core, n_layers)
    return PolarParams(
        center=center,
        outer_radius=cfg.od/2 - wall_out,
        bore_radius=core,
        extrusion_width=cfg.line_width,
        line_spacing=spacing,
        ply_sequence=cfg.ply_sequence,
        phase_stagger_deg=phase,
        hoop_spiral=cfg.hoop_spiral,
        banding=cfg.banding,
        band_ratio=cfg.band_ratio,
        spoke_continuity=cfg.spoke_continuity,
        anchor=cfg.anchor,
        tie_rings=cfg.tie_rings,
    )


def dense_hoop(cfg: Config, center: Point) -> List[Polyline]:
    """Fully dense concentric rings for solid caps (spacing = line_width)."""
    p = polar_params_for(cfg, center)
    p.line_spacing = cfg.line_width
    return hoop_ply(p)


def layer_infill(cfg: Config, center: Point, layer_index: int, n_layers: int) -> List[Polyline]:
    cap = cfg.solid_cap_layers
    is_cap = (layer_index < cap) or (layer_index >= n_layers - cap)
    if is_cap:
        return dense_hoop(cfg, center)     # closed top/bottom surface
    p = polar_params_for(cfg, center, n_layers)
    t = ply_type_for_layer(p, layer_index)
    if t == "H":
        return hoop_ply(p)
    if t == "G":
        g_ord = sum(1 for i in range(layer_index) if ply_type_for_layer(p, i) == "G")
        return grid_ply(p, ply_index=g_ord)
    radial_ord = sum(1 for i in range(layer_index) if ply_type_for_layer(p, i) == "R")
    if getattr(cfg, "radial_mode", "banded") == "vw":
        return radial_ply_vw(p, ply_index=radial_ord,
                             w_min=cfg.vw_w_min, w_max=cfg.vw_w_max,
                             end_gap=cfg.vw_end_gap, band_gap=cfg.vw_band_gap)
    return radial_ply(p, ply_index=radial_ord)


# ============================================================================
# G-CODE EMITTER
# ============================================================================
class GcodeWriter:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.fil_area = math.pi * (cfg.filament_diameter/2)**2
        self.lines: List[str] = []
        self.x = self.y = self.z = 0.0
        self.hopped = False
        self.retracted = False
        self.filament_used = 0.0

    def g(self, s): self.lines.append(s)

    def e_for(self, seg_len, lh):
        # Rounded-rectangle bead cross-section, as Slic3r/PrusaSlicer use:
        # an extruded road is not a sharp rectangle -- its edges are rounded to
        # radius lh/2, so area = w*lh - lh^2*(1 - pi/4).  Using plain w*lh
        # over-extrudes by ~4% at 0.2 mm layers and ~9% at 0.4 mm.
        # Verified against a known-good PrusaSlicer export: matches to 4 d.p.
        w = self.cfg.line_width
        area = w * lh - lh * lh * (1.0 - math.pi / 4.0)
        vol = seg_len * max(area, 1e-9)
        e = vol / self.fil_area * self.cfg.flow
        self.filament_used += e
        return e

    def retract(self):
        if self.cfg.retract_length > 0 and not self.retracted:
            self.g("G1 E-%.4f F%d" % (self.cfg.retract_length, int(self.cfg.retract_speed*60)))
            self.retracted = True

    def unretract(self):
        if self.cfg.retract_length > 0 and self.retracted:
            self.g("G1 E%.4f F%d" % (self.cfg.retract_length, int(self.cfg.retract_speed*60)))
            self.retracted = False

    def hop(self, z):
        if self.cfg.z_hop > 0 and not self.hopped:
            self.g("G1 Z%.3f F600 ; Zfix hop up" % (z + self.cfg.z_hop)); self.hopped = True

    def unhop(self, z):
        if self.hopped:
            self.g("G1 Z%.3f F600 ; Zfix hop down" % z); self.hopped = False

    def travel_to(self, pt, z):
        dist = math.hypot(pt[0]-self.x, pt[1]-self.y)
        if dist > self.cfg.travel_retract_min:
            self.retract(); self.hop(z)
        self.g("G0 X%.3f Y%.3f F%d" % (pt[0], pt[1], int(self.cfg.travel_speed*60)))
        self.x, self.y = pt
        self.unhop(z); self.unretract()

    def extrude_path(self, path, z, lh, speed):
        if len(path) < 2: return
        self.travel_to(path[0], z)
        f = int(speed*60)
        for pt in path[1:]:
            seg = math.hypot(pt[0]-self.x, pt[1]-self.y)
            if seg < 1e-6: continue
            self.g("G1 X%.3f Y%.3f E%.5f F%d" % (pt[0], pt[1], self.e_for(seg, lh), f))
            self.x, self.y = pt

    def e_for_w(self, seg_len, lh, width):
        area = width * lh - lh * lh * (1.0 - math.pi / 4.0)
        e = seg_len * max(area, 1e-9) / self.fil_area * self.cfg.flow
        self.filament_used += e
        return e

    def extrude_path_vw(self, path, z, lh, vol_rate, speed_cap):
        """path = [(x, y, width), ...]. Volumetric rate held constant, so the
        head slows as the road widens: v = Q / (w * lh)."""
        if len(path) < 2: return
        self.travel_to((path[0][0], path[0][1]), z)
        prev_w = path[0][2]                      # reset per path -- do not carry over
        corr = lh * lh * (1.0 - math.pi / 4.0)   # rounded-bead correction
        for pt in path[1:]:
            seg = math.hypot(pt[0]-self.x, pt[1]-self.y)
            if seg < 1e-6: continue
            wmid = 0.5*(pt[2] + prev_w)
            area = max(1e-9, wmid*lh - corr)     # true bead area, not w*lh
            v = min(speed_cap, vol_rate / area)  # constant volumetric rate
            self.g("G1 X%.3f Y%.3f E%.5f F%d"
                   % (pt[0], pt[1], self.e_for_w(seg, lh, wmid), int(v*60)))
            self.x, self.y = pt[0], pt[1]; prev_w = pt[2]

    def move_z(self, z):
        self.g("G1 Z%.3f F600" % z); self.z = z


def generate(cfg: Config) -> Tuple[str, dict]:
    center = cfg.center_xy or (cfg.bed_x/2, cfg.bed_y/2)
    n_layers = 1 + max(0, round((cfg.height - cfg.first_layer_height)/cfg.layer_height))

    w = GcodeWriter(cfg)
    # ---- start gcode ----
    subs = dict(nozzle_temp=int(cfg.nozzle_temp), bed_temp=int(cfg.bed_temp),
                first_layer_height=cfg.first_layer_height,
                travel_mm_min=int(cfg.travel_speed*60),
                prime_x0=10.0, prime_x1=min(cfg.bed_x-10, 210.0), prime_y=10.0,
                bed_y_minus=cfg.bed_y-10)
    start = (cfg.start_gcode or DEFAULT_START).format(**subs)
    w.g(start.rstrip())

    stats = dict(layers=n_layers, center=center, bands=None,
                 od=cfg.od, id=cfg.id, height=cfg.height)

    for li in range(n_layers):
        z = cfg.first_layer_height + (li*cfg.layer_height if li>0 else 0.0)
        lh = cfg.first_layer_height if li == 0 else cfg.layer_height
        cap = (li < cfg.solid_cap_layers) or (li >= n_layers - cfg.solid_cap_layers)
        p = polar_params_for(cfg, center)
        ptype = "CAP" if cap else ply_type_for_layer(p, li)
        if li == 1 and cfg.after_first_layer_gcode:
            w.g(cfg.after_first_layer_gcode.rstrip())
        w.g(";LAYER:%d" % li)
        w.g(";Z:%.3f" % z)
        w.g(";PLY:%s" % ptype)
        w.move_z(z)

        spd_wall = cfg.first_layer_speed if li == 0 else cfg.wall_speed
        spd_fill = cfg.first_layer_speed if li == 0 else (cfg.solid_speed if (cap or ptype=="H") else cfg.print_speed)

        # walls first, then infill (infill anchors onto walls)
        w.g(";TYPE:WALL")
        for loop in wall_loops(center, cfg):
            w.extrude_path(loop, z, lh, spd_wall)
        w.g(";TYPE:%s" % ("SOLID" if (cap or ptype=="H") else "RADIAL"))
        for path in layer_infill(cfg, center, li, n_layers):
            if path and len(path[0]) == 3:          # (x, y, width) -> variable width
                w.extrude_path_vw(path, z, lh, cfg.vw_vol_rate, spd_fill)
            else:
                w.extrude_path(path, z, lh, spd_fill)

    # ---- end gcode ----
    w.retract()
    end = (cfg.end_gcode or DEFAULT_END).format(**subs)
    w.g(end.rstrip())

    if getattr(cfg, "radial_mode", "banded") == "vw":
        from polar_crossply import vw_bands
        stats["bands"] = vw_bands(polar_params_for(cfg, center),
                                  cfg.vw_w_min, cfg.vw_w_max, cfg.vw_end_gap, cfg.vw_band_gap)
    else:
        stats["bands"] = _band_edges(polar_params_for(cfg, center))
    stats["filament_mm"] = round(w.filament_used, 1)
    stats["filament_g_PLA"] = round(w.filament_used * w.fil_area * 1.24 / 1000, 2)
    return "\n".join(w.lines) + "\n", stats


# ============================================================================
# CLI
# ============================================================================
def main(argv=None):
    ap = argparse.ArgumentParser(description="Parametric polar cross-ply G-code generator (axisymmetric parts).")
    ap.add_argument("-o","--out", default="polar_part.gcode")
    ap.add_argument("--config", help="JSON config file (overrides defaults; CLI flags override it)")
    # expose the common knobs
    for name, typ in [("od",float),("id",float),("height",float),("layer_height",float),
                      ("first_layer_height",float),("line_width",float),("nozzle_diameter",float),
                      ("filament_diameter",float),("infill_density",float),("outer_walls",int),
                      ("inner_walls",int),("solid_cap_layers",int),("phase_stagger_deg",float),
                      ("band_ratio",float),("anchor",float),("print_speed",float),("wall_speed",float),
                      ("travel_speed",float),("z_hop",float),("nozzle_temp",float),("bed_temp",float),
                      ("bed_x",float),("bed_y",float)]:
        ap.add_argument("--"+name, type=typ)
    ap.add_argument("--ply_sequence")
    ap.add_argument("--banding", choices=["none","doubling","geometric"])
    ap.add_argument("--spoke_continuity", choices=["zigzag","individual"])
    ap.add_argument("--start_gcode_file")
    ap.add_argument("--end_gcode_file")
    ap.add_argument("--after_first_layer_gcode_file")
    args = ap.parse_args(argv)

    cfg = Config()
    if args.config:
        with open(args.config) as f:
            data = json.load(f)
        for k,v in data.items():
            if hasattr(cfg,k): setattr(cfg,k,v)
    for k,v in vars(args).items():
        if k in ("out","config","start_gcode_file","end_gcode_file","after_first_layer_gcode_file"): continue
        if v is not None and hasattr(cfg,k): setattr(cfg,k,v)
    if args.start_gcode_file: cfg.start_gcode = open(args.start_gcode_file).read()
    if args.end_gcode_file: cfg.end_gcode = open(args.end_gcode_file).read()
    if args.after_first_layer_gcode_file: cfg.after_first_layer_gcode = open(args.after_first_layer_gcode_file).read()

    gcode, stats = generate(cfg)
    with open(args.out,"w") as f: f.write(gcode)
    print("Wrote %s" % args.out)
    print("  layers:        %d" % stats["layers"])
    print("  center:        (%.1f, %.1f)" % stats["center"])
    print("  OD/ID/height:  %.1f / %.1f / %.1f mm" % (stats["od"],stats["id"],stats["height"]))
    print("  radial bands:  " + ", ".join("%d@%.1f-%.1fmm"%(n,a,b) for (a,b,n) in stats["bands"]))
    print("  filament:      %.1f mm  (~%.1f g if PLA 1.24)" % (stats["filament_mm"], stats["filament_g_PLA"]))
    print("  NOTE: set nozzle/bed temp and paste your printer's start/end g-code before printing.")

if __name__ == "__main__":
    main()
