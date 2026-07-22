#!/usr/bin/env python3
"""
mass_audit.py -- reproducible check of the coverage and mass assumptions used in
layups.py, measured directly from the pattern generator.

Why this exists: the first pass of the layup study used areal COVERAGE as the
mass fraction. Coverage is capped at 1.0, so it discards over-deposition, and it
ignores the anchor overlap between bands and the tie rings. The result understated
radial-ply mass by ~1.56x, which INFLATED per-mass performance of the very pattern
being studied. This script measures both quantities so the correction is
verifiable rather than asserted.

Run:  python mass_audit.py
Needs: numpy, and polar_crossply.py from the repo root on the path.
"""
import math, os, sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from polar_crossply import PolarParams, radial_ply, hoop_ply, grid_ply

# Reference rotor geometry (matches SPEC.md / the printed part)
A, B, W = 5.25, 33.10, 1.0          # bore r, outer r, road width (mm)

P = PolarParams(center=(0, 0), outer_radius=B, bore_radius=A,
                extrusion_width=W, line_spacing=W, banding="doubling",
                band_ratio=2.0, anchor=2.5, tie_rings=True,
                spoke_continuity="zigzag", hoop_spiral=True)

ANNULUS = math.pi * (B * B - A * A)


def road_length(paths):
    return sum(math.dist(p[i - 1], p[i]) for p in paths for i in range(1, len(p)))


def deposited_fraction(paths):
    """Commanded material / material a perfectly-packed solid layer needs."""
    return road_length(paths) * W / ANNULUS


def areal_coverage(paths, n=1400):
    """Fraction of the annulus actually covered; overlaps NOT double-counted."""
    g = np.linspace(-B, B, n)
    X, Y = np.meshgrid(g, g, indexing="ij")
    ann = (np.hypot(X, Y) >= A) & (np.hypot(X, Y) <= B)
    cov = np.zeros_like(X, dtype=bool)
    hw = W / 2
    for pl in paths:
        for i in range(1, len(pl)):
            x0, y0 = pl[i - 1]
            x1, y1 = pl[i]
            dx, dy = x1 - x0, y1 - y0
            l2 = dx * dx + dy * dy
            if l2 < 1e-12:
                continue
            m = ((X >= min(x0, x1) - hw) & (X <= max(x0, x1) + hw) &
                 (Y >= min(y0, y1) - hw) & (Y <= max(y0, y1) + hw) & (~cov))
            if not m.any():
                continue
            px, py = X[m] - x0, Y[m] - y0
            t = np.clip((px * dx + py * dy) / l2, 0, 1)
            sub = cov[m]
            sub |= np.hypot(px - t * dx, py - t * dy) <= hw
            cov[m] = sub
    return (cov & ann).sum() / ann.sum()


def main():
    rad = radial_ply(P, 0)
    hoop = hoop_ply(P)
    g0, g1 = grid_ply(P, 0), grid_ply(P, 1)

    dep = {"RAD": deposited_fraction(rad),
           "HOOP": deposited_fraction(hoop),
           "G45": (deposited_fraction(g0) + deposited_fraction(g1)) / 2}
    dep["XPLY"] = (dep["RAD"] + dep["HOOP"]) / 2
    dep["ISO"] = 1.000

    cov = {"RAD": areal_coverage(rad), "HOOP": areal_coverage(hoop)}
    cov["XPLY"] = (cov["RAD"] + cov["HOOP"]) / 2

    print("Reference annulus: r %.2f..%.2f mm, road width %.2f mm, area %.0f mm^2\n"
          % (A, B, W, ANNULUS))
    print("%-6s %12s %12s %10s" % ("layup", "coverage", "deposited", "delta"))
    for k in ("RAD", "HOOP", "XPLY"):
        print("%-6s %12.3f %12.3f %9.2fx" % (k, cov[k], dep[k], dep[k] / cov[k]))
    print("%-6s %12s %12.3f" % ("G45", "~1.0", dep["G45"]))

    old = {"ISO": 1.000, "XPLY": 0.883, "HOOP": 0.970, "RAD": 0.796, "G45": 1.000}
    print("\nMASSFRAC correction (deposition is the mass proxy, not coverage):")
    print("%-6s %10s %10s %14s" % ("layup", "old", "corrected", "per-mass infl."))
    for k in ("ISO", "XPLY", "HOOP", "RAD", "G45"):
        infl = dep[k] / old[k]
        print("%-6s %10.3f %10.3f %13.2fx" % (k, old[k], dep[k], infl))

    print("\nMASSFRAC = {" + ", ".join("'%s': %.3f" % (k, dep[k])
          for k in ("ISO", "XPLY", "HOOP", "RAD", "G45")) + "}")
    print("\nNOTE: the radial ply deposits %.0f%% of a solid layer's material yet"
          % (100 * dep["RAD"]))
    print("      covers only %.0f%% of the area -- over-extrusion in the anchor"
          % (100 * cov["RAD"]))
    print("      overlaps coexisting with voids at band outer edges.")
    print("      Mass should ultimately be MEASURED by weighing specimens.")


if __name__ == "__main__":
    main()
