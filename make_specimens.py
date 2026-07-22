#!/usr/bin/env python3
"""
make_specimens.py -- generate the ring-test specimen matrix for comparing
polar cross-ply against baseline layups, at MATCHED MASS.

Test method: ASTM D2290 split-disk METHOD, applied by analogy to printed rings.
NOTE the specimen is NON-STANDARD (see RING_TEST_PLAN.md). Absolute "apparent
hoop strength" is biased low by the fixture bending moment; because every layup
here uses IDENTICAL geometry and fixture, that bias is common-mode and the
LAYUP-TO-LAYUP RATIOS are what this program measures.

Layups generated:
  crossply   R,H   polar cross-ply (the pattern under test)
  hoop       H     all concentric/spiral hoop  (hoop-optimal reference)
  radial     R     all radial spokes           (radial-optimal reference)
  grid       G     +-45 rectilinear            (the STOCK slicer baseline)
  solid      H     dense hoop, spacing=line_width (upper-bound reference)

Usage:
  python make_specimens.py                       # defaults, 5 replicates
  python make_specimens.py --replicates 5 --od 80 --id 50 --width 10
  python make_specimens.py --no-match-mass       # skip mass equalisation

License: MIT
"""
from __future__ import annotations
import argparse, copy, math, os

from polar_slicer import Config, generate

LAYUPS = {
    "crossply": dict(ply_sequence="R,H", note="polar cross-ply (under test)"),
    "hoop":     dict(ply_sequence="H",   note="all hoop (hoop-optimal ref)"),
    "radial":   dict(ply_sequence="R",   note="all radial (radial-optimal ref)"),
    "grid":     dict(ply_sequence="G",   note="+-45 rectilinear (STOCK baseline)"),
    "solid":    dict(ply_sequence="H",   note="dense hoop (upper-bound ref)"),
}


def build_cfg(args, layup: str) -> Config:
    cfg = Config()
    cfg.od = args.od
    cfg.id = args.id
    cfg.height = args.width          # ring axial width = print height
    cfg.line_width = args.line_width
    cfg.nozzle_diameter = args.nozzle
    cfg.layer_height = args.layer_height
    cfg.first_layer_height = args.first_layer_height
    cfg.nozzle_temp = args.nozzle_temp
    cfg.bed_temp = args.bed_temp
    cfg.bed_x, cfg.bed_y = args.bed_x, args.bed_y
    # Specimens: no solid caps -- caps would add hoop-oriented skins to EVERY
    # layup and mask the difference we are trying to measure.
    cfg.solid_cap_layers = 0
    # Minimal walls, identical for all layups (they are common-mode).
    cfg.outer_walls = args.walls
    cfg.inner_walls = args.walls
    cfg.ply_sequence = LAYUPS[layup]["ply_sequence"]
    cfg.infill_density = 100.0
    if layup == "solid":
        cfg.infill_density = 100.0
    return cfg


def mass_of(cfg: Config) -> float:
    _, stats = generate(cfg)
    return stats["filament_mm"]


def match_mass(cfg: Config, target_mm: float, tol=0.01, iters=24) -> Config:
    """Bisect infill_density so total filament ~= target."""
    lo, hi = 40.0, 160.0
    best = copy.deepcopy(cfg)
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        c = copy.deepcopy(cfg); c.infill_density = mid
        m = mass_of(c)
        best = c
        if abs(m - target_mm) / target_mm < tol:
            return c
        if m > target_mm:
            hi = mid      # too much material -> reduce density
        else:
            lo = mid      # too little  -> increase density
    return best


def main():
    ap = argparse.ArgumentParser(description="Generate ring-test specimen matrix (D2290 method, non-standard specimen).")
    ap.add_argument("--outdir", default="specimens")
    ap.add_argument("--replicates", type=int, default=5)
    ap.add_argument("--od", type=float, default=80.0, help="ring outer diameter mm")
    ap.add_argument("--id", type=float, default=50.0, help="ring inner diameter mm")
    ap.add_argument("--width", type=float, default=10.0, help="ring axial width mm (= print height)")
    ap.add_argument("--line_width", type=float, default=0.6)
    ap.add_argument("--nozzle", type=float, default=0.4)
    ap.add_argument("--layer_height", type=float, default=0.2)
    ap.add_argument("--first_layer_height", type=float, default=0.2)
    ap.add_argument("--walls", type=int, default=2)
    ap.add_argument("--nozzle_temp", type=float, default=210)
    ap.add_argument("--bed_temp", type=float, default=60)
    ap.add_argument("--bed_x", type=float, default=220)
    ap.add_argument("--bed_y", type=float, default=220)
    ap.add_argument("--no-match-mass", dest="match", action="store_false")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    wall = (args.od - args.id) / 2.0
    print("Ring specimen: OD %.1f  ID %.1f  wall %.1f mm  width %.1f mm"
          % (args.od, args.id, wall, args.width))
    print("Nominal wall cross-section per side: %.1f mm^2  (A used in sigma = P / 2A)"
          % (wall * args.width))
    print()

    # natural masses
    natural = {}
    for name in LAYUPS:
        cfg = build_cfg(args, name)
        natural[name] = mass_of(cfg)
    target = max(natural.values())
    print("Natural filament use (mm):")
    for k, v in natural.items():
        print("  %-9s %8.0f   %s" % (k, v, LAYUPS[k]["note"]))
    if args.match:
        print("\nMatching all layups to %.0f mm (the densest) by tuning infill density...\n" % target)

    rows = []
    for name in LAYUPS:
        cfg = build_cfg(args, name)
        if args.match and name != "solid":
            cfg = match_mass(cfg, target)
        gcode, stats = generate(cfg)
        for r in range(1, args.replicates + 1):
            path = os.path.join(args.outdir, "ring_%s_%02d.gcode" % (name, r))
            with open(path, "w") as f:
                f.write(gcode)
        rows.append((name, cfg.infill_density, stats["filament_mm"], stats["layers"]))

    print("%-9s %8s %10s %7s  %s" % ("layup", "density", "filament", "layers", "note"))
    for (name, dens, fil, lay) in rows:
        print("%-9s %7.1f%% %9.0fmm %7d  %s" % (name, dens, fil, lay, LAYUPS[name]["note"]))
    dev = [abs(r[2] - target) / target * 100 for r in rows]
    print("\nMax mass deviation from target: %.1f%%" % max(dev))
    print("Wrote %d files to %s/ (%d layups x %d replicates)"
          % (len(LAYUPS) * args.replicates, args.outdir, len(LAYUPS), args.replicates))
    print("\nREMINDER: add reduced sections (notches) before testing -- see RING_TEST_PLAN.md.")
    print("Set your printer's start/end g-code and temps before printing.")


if __name__ == "__main__":
    main()
