"""
polar_crossply.py  -- reference generator for POLAR CROSS-PLY infill.

Slicer-agnostic core. Given a region described as an (outer_radius, bore_radius)
annulus about a polar center, plus the parameter set below, it produces the
extrusion polylines for a single layer of either ply type, and can walk a whole
part by alternating plies according to a ply sequence.

This is the reference/spec implementation: it is deliberately geometry-simple
(true circles/annulus) so the ALGORITHM is legible. Integration into a real
slicer replaces the "clip to circle" steps with "clip to the region ExPolygon"
(see SPEC.md, Integration). Everything else ports directly.

Author: reference implementation for open-source contribution.
License: MIT (suggested).
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

Point = Tuple[float, float]
Polyline = List[Point]


# ----------------------------------------------------------------------------
# PARAMETER SET  (these map 1:1 to the documented slicer options in SPEC.md)
# ----------------------------------------------------------------------------
@dataclass
class PolarParams:
    # --- geometry / axis ---------------------------------------------------
    center: Point = (0.0, 0.0)          # polar_center_xy (resolved by center_mode upstream)
    outer_radius: float = 33.0          # clipped from region bbox upstream
    bore_radius: float = 5.0            # polar_core_radius; inside this -> core fill

    # --- deposition ---------------------------------------------------------
    extrusion_width: float = 1.0        # road width
    infill_overlap: float = 0.15        # fraction; overlap of adjacent roads / into perims

    # --- density (polar-native mapping of "infill %") ----------------------
    # target center-to-center spacing between adjacent roads (mm).
    # For 100% solid this equals extrusion_width; for sparse, larger.
    line_spacing: float = 1.0

    # --- ply scheme ---------------------------------------------------------
    ply_sequence: str = "R,H"           # repeating; R=radial, H=hoop. e.g. "H,H,R" biases hoop
    phase_stagger_deg: float = 0.0      # rotate spokes each successive radial ply

    # --- radial banding (density control for spokes) -----------------------
    banding: str = "doubling"           # {none, doubling, geometric}
    band_ratio: float = 2.0             # split a band when arc-pitch > band_ratio * line_spacing
    spoke_continuity: str = "zigzag"    # {zigzag, individual}

    # --- connectivity / strength -------------------------------------------
    anchor: float = 2.5                 # mm spokes overlap into rim/bore/tie rings
    tie_rings: bool = True              # lay concentric tie rings at band edges + bore + rim
    core_fill: str = "concentric"       # {solid, concentric, none} inside bore_radius..(n/a here)


# ----------------------------------------------------------------------------
# HOOP PLY  = concentric rings about the polar center
# ----------------------------------------------------------------------------
def hoop_ply(p: PolarParams, seg_deg: float = 4.0) -> List[Polyline]:
    rings = []
    pitch = p.line_spacing
    r = p.bore_radius + p.extrusion_width / 2.0
    r_max = p.outer_radius - p.extrusion_width / 2.0
    n = max(1, int(math.floor((r_max - r) / pitch)) + 1)
    for _ in range(n):
        if r > r_max + 1e-6:
            break
        steps = max(8, int(360.0 / seg_deg))
        ring = [(p.center[0] + r * math.cos(2*math.pi*k/steps),
                 p.center[1] + r * math.sin(2*math.pi*k/steps)) for k in range(steps + 1)]
        rings.append(ring)
        r += pitch
    return rings


# ----------------------------------------------------------------------------
# RADIAL PLY  = spokes in radius bands (density kept ~constant), optional ties
# ----------------------------------------------------------------------------
def _band_edges(p: PolarParams) -> List[Tuple[float, float, int]]:
    """Return list of (r_inner, r_outer, spoke_count) bands from bore to rim."""
    r_in = p.bore_radius
    r_out = p.outer_radius
    target = p.line_spacing
    # spoke count so arc-pitch at the band's INNER radius ~= target
    def count_for(r):
        return max(6, int(math.ceil(2 * math.pi * max(r, target) / target)))
    bands = []
    if p.banding == "none":
        return [(r_in, r_out, count_for(r_in))]
    r0 = r_in
    n = count_for(r_in)
    while r0 < r_out - 1e-6:
        # grow r until arc-pitch exceeds band_ratio*target, then split
        # arc-pitch = 2*pi*r/n ; solve 2*pi*r/n = band_ratio*target
        r_split = p.band_ratio * target * n / (2 * math.pi)
        r1 = min(r_split, r_out)
        bands.append((r0, r1, n))
        r0 = r1
        if p.banding == "doubling":
            n *= 2
        else:  # geometric: recompute to restore ~target pitch at new inner r
            n = count_for(r0)
    return bands


def radial_ply(p: PolarParams, ply_index: int = 0) -> List[Polyline]:
    paths: List[Polyline] = []
    phase = math.radians(p.phase_stagger_deg * ply_index)
    bands = _band_edges(p)
    for (r0, r1, n) in bands:
        a = p.anchor
        ri = max(p.bore_radius, r0 - a)         # anchor inward
        ro = min(p.outer_radius, r1 + a)        # anchor outward
        angs = [phase + 2*math.pi*k/n for k in range(n)]
        if p.spoke_continuity == "zigzag":
            path = []
            for k, ang in enumerate(angs):
                inner = (p.center[0] + ri*math.cos(ang), p.center[1] + ri*math.sin(ang))
                outer = (p.center[0] + ro*math.cos(ang), p.center[1] + ro*math.sin(ang))
                if k % 2 == 0:
                    path += [inner, outer]
                else:
                    path += [outer, inner]
            paths.append(path)
        else:
            for ang in angs:
                inner = (p.center[0] + ri*math.cos(ang), p.center[1] + ri*math.sin(ang))
                outer = (p.center[0] + ro*math.cos(ang), p.center[1] + ro*math.sin(ang))
                paths.append([inner, outer])
    if p.tie_rings:
        tie_radii = {p.bore_radius + p.extrusion_width/2,
                     p.outer_radius - p.extrusion_width/2}
        for (r0, r1, _n) in bands:
            tie_radii.add(r1)
        for r in sorted(tie_radii):
            if p.bore_radius <= r <= p.outer_radius:
                steps = max(8, int(360/4))
                paths.append([(p.center[0]+r*math.cos(2*math.pi*k/steps),
                               p.center[1]+r*math.sin(2*math.pi*k/steps)) for k in range(steps+1)])
    return paths


# ----------------------------------------------------------------------------
# LAYER DISPATCH + PART WALK
# ----------------------------------------------------------------------------
def ply_type_for_layer(p: PolarParams, layer_index: int) -> str:
    seq = [s.strip().upper() for s in p.ply_sequence.split(",") if s.strip()]
    return seq[layer_index % len(seq)]


def layer_paths(p: PolarParams, layer_index: int) -> Tuple[str, List[Polyline]]:
    t = ply_type_for_layer(p, layer_index)
    if t == "H":
        return "H", hoop_ply(p)
    else:
        radial_ord = sum(1 for i in range(layer_index) if ply_type_for_layer(p, i) == "R")
        return "R", radial_ply(p, ply_index=radial_ord)


def road_length(paths: List[Polyline]) -> float:
    tot = 0.0
    for pl in paths:
        for i in range(1, len(pl)):
            tot += math.dist(pl[i-1], pl[i])
    return tot


def coverage(p: PolarParams, paths: List[Polyline]) -> float:
    area = math.pi * (p.outer_radius**2 - p.bore_radius**2)
    return road_length(paths) * p.extrusion_width / area
