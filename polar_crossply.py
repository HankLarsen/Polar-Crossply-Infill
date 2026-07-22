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
    # HELICAL STAGGER: rotate the spoke set by this angle on each successive
    # radial ply so the inter-spoke gaps never stack into a vertical weak
    # channel -- they helix instead (the "filament-winding" advance). Set it so
    # the spokes sweep one inter-spoke pitch over the radial layers in the part.
    phase_stagger_deg: float = 3.0

    # --- hoop ply form ------------------------------------------------------
    # False (DEFAULT) -> discrete concentric rings. Proven: 99.9% coverage,
    #          +1% material. This is what stock concentric does and what the
    #          reference part was printed with.
    # True  -> EXPERIMENTAL continuous seamless path. Two test prints failed:
    #          v1 (plain Archimedean spiral) left a crescent VOID up to a full
    #          road width at both bore and perimeter; v2 (closed rings joined
    #          by short ramps) fixed the void but deposits +13% material
    #          because each ramp lays an extra road in a band the adjacent
    #          rings already cover. Do not enable for real parts until the
    #          ramp is made to REPLACE ring sweep rather than add to it.
    # In a real slicer the hoop ply is just stock CONCENTRIC infill (offset
    # inward from the perimeter) with spiralize/connect enabled -- which makes
    # it squares-on-squares, ovals-on-ovals, etc. automatically. The reference
    # below demonstrates the seamless spiral on the circular/annular case.
    hoop_spiral: bool = False

    # --- radial banding (density control for spokes) -----------------------
    banding: str = "doubling"           # {none, doubling, geometric}
    band_ratio: float = 2.0             # split a band when arc-pitch > band_ratio * line_spacing
    spoke_continuity: str = "zigzag"    # {zigzag, individual}

    # --- connectivity / strength -------------------------------------------
    anchor: float = 2.5                 # mm spokes overlap into rim/bore/tie rings
    tie_rings: bool = True              # lay concentric tie rings at band edges + bore + rim
    core_fill: str = "concentric"       # {solid, concentric, none} inside bore_radius..(n/a here)


# ----------------------------------------------------------------------------
# HOOP PLY  = concentric rings (or one seamless spiral) about the polar center
# ----------------------------------------------------------------------------
def _hoop_spiral(p: PolarParams, seg_deg: float = 3.0,
                 connector_deg: float = 5.0) -> Polyline:
    """One continuous seamless path covering the annulus — v3.

    Each ring is a FULL 2*pi closed circle, so every radius gets complete
    circumferential coverage. Rings are joined by a SHORT connector that steps
    one pitch outward while advancing `connector_deg` in angle. Extrusion never
    stops, so there is no per-ring start/stop seam.

    History (both failures found by test print, not by rendering):
      v1  plain Archimedean spiral -- perfect tiling in the bulk (adjacent
          turns sit exactly one pitch apart) but the first and last turns never
          close, leaving a crescent VOID growing to a full road width at both
          the bore and the perimeter.
      v2  closed rings joined by a 45 deg arc ramp -- closed the voids but the
          ramp is ~16 mm of extra road per ring at r=20, i.e. +13% material
          over the whole layer. The ramp was ADDED to the rings rather than
          replacing part of them.
      v3  (this) same closed rings, but the connector is a short jog rather
          than a long arc: +1.7% at connector_deg=0, +2.5% at 5 deg, versus
          +0.9% for discrete seamed rings. So continuity costs ~1-2% material.

    `connector_deg` trades three things:
      0 deg  cheapest (+1.7%) and 100% coverage, but every connector sits at
             the same angle, stacking into a raised radial line, and the two
             90 deg corners can blob at speed.
      5 deg  connectors precess around the part and become smooth diagonals
             that the motion system handles better. Costs +0.8% more.
    """
    pitch = p.line_spacing
    r0 = p.bore_radius + p.extrusion_width / 2.0
    r_max = p.outer_radius - p.extrusion_width / 2.0
    if r_max <= r0:
        return []

    n = int(math.ceil((r_max - r0) / pitch)) + 1
    radii = sorted(set(min(r0 + k * pitch, r_max) for k in range(n)))
    adv = math.radians(max(0.0, min(90.0, connector_deg)))
    cx, cy = p.center
    path: Polyline = []

    def sweep(r_a, r_b, th_a, th_b):
        span = abs(th_b - th_a)
        steps = max(2, int(span / math.radians(seg_deg))) if span > 1e-9 else 1
        start = 1 if path else 0          # don't duplicate the joint point
        for i in range(start, steps + 1):
            f = i / steps
            th = th_a + f * (th_b - th_a)
            r = r_a + f * (r_b - r_a)
            path.append((cx + r * math.cos(th), cy + r * math.sin(th)))

    th = 0.0
    for k, r in enumerate(radii):
        sweep(r, r, th, th + 2 * math.pi)          # closed ring
        th += 2 * math.pi
        if k + 1 < len(radii):
            if adv > 1e-9:
                sweep(r, radii[k + 1], th, th + adv)   # short diagonal
                th += adv
            else:
                path.append((cx + radii[k + 1] * math.cos(th),
                             cy + radii[k + 1] * math.sin(th)))  # radial jog
    return path


def hoop_ply(p: PolarParams, seg_deg: float = 4.0) -> List[Polyline]:
    # Seamless spiral form (default): single continuous road, no stacked seam.
    if getattr(p, "hoop_spiral", True):
        sp = _hoop_spiral(p, seg_deg)
        return [sp] if len(sp) >= 2 else []
    # Discrete concentric rings (each a closed loop with its own seam).
    rings = []
    pitch = p.line_spacing
    r0 = p.bore_radius + p.extrusion_width / 2.0
    r_max = p.outer_radius - p.extrusion_width / 2.0
    if r_max <= r0:
        return []
    # ceil (not floor) so the outermost ring reaches r_max instead of leaving
    # a bare band up to one pitch wide at the perimeter.
    n = int(math.ceil((r_max - r0) / pitch)) + 1
    for r in sorted(set(min(r0 + k * pitch, r_max) for k in range(n))):
        steps = max(8, int(360.0 / seg_deg))
        ring = [(p.center[0] + r * math.cos(2*math.pi*k/steps),
                 p.center[1] + r * math.sin(2*math.pi*k/steps)) for k in range(steps + 1)]
        rings.append(ring)
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
# GRID PLY = rectilinear raster clipped to the annulus (the STOCK baseline).
# Alternates +45/-45 per grid ply, like a conventional slicer's default.
# ----------------------------------------------------------------------------
def grid_ply(p: PolarParams, ply_index: int = 0, angle_deg: Optional[float] = None) -> List[Polyline]:
    th = math.radians(angle_deg if angle_deg is not None else (45.0 + 90.0 * (ply_index % 2)))
    ct, st = math.cos(th), math.sin(th)
    R, Ri = p.outer_radius, p.bore_radius
    pitch = p.line_spacing
    paths: List[Polyline] = []
    d = -R + pitch / 2.0
    while d < R:
        if abs(d) < R:
            t_out = math.sqrt(max(0.0, R*R - d*d))
            spans = []
            if Ri > 0 and abs(d) < Ri:                 # line crosses the bore
                t_in = math.sqrt(max(0.0, Ri*Ri - d*d))
                spans = [(-t_out, -t_in), (t_in, t_out)]
            else:
                spans = [(-t_out, t_out)]
            for (t0, t1) in spans:
                if t1 - t0 < 0.5:
                    continue
                a = (p.center[0] + d*(-st) + t0*ct, p.center[1] + d*ct + t0*st)
                b = (p.center[0] + d*(-st) + t1*ct, p.center[1] + d*ct + t1*st)
                paths.append([a, b])
        d += pitch
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
    elif t == "G":
        g_ord = sum(1 for i in range(layer_index) if ply_type_for_layer(p, i) == "G")
        return "G", grid_ply(p, ply_index=g_ord)
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


# ----------------------------------------------------------------------------
# VARIABLE-WIDTH RADIAL PLY  (v2 strategy)
# ----------------------------------------------------------------------------
# Road width grows in proportion to radius. Because
#     coverage = n * w(r) / (2*pi*r)
# holding w proportional to r makes coverage EXACTLY constant, so one band
# spans a radius ratio of w_max/w_min with no divergence at all. Width is
# achieved by holding volumetric rate constant and SLOWING the head:
#     v(r) = Q / (w(r) * layer_height)
#
# No tie rings, no band-crossing anchors, no circumferential step-overs. Every
# road is purely radial at a distinct angle, so roads cannot cross. Spokes are
# emitted in serpentine order so the hop between them is one arc-pitch long
# (shorter than travel_retract_min), avoiding a retract per spoke.
#
# Returns: list of polylines, each [(x, y, width), ...]
# ----------------------------------------------------------------------------
def vw_bands(p: PolarParams, w_min: float, w_max: float,
             end_gap: float, band_gap: float,
             min_band: float = 2.0) -> List[Tuple[float, float, int]]:
    """Bands sized by the width ratio. If the remainder after a band is
    shorter than `min_band` it is ABSORBED into that band rather than starting
    a stub band: width simply caps at w_max and coverage dips a little toward
    the rim (~0.95 at full extension), which is far better than leaving a bare
    ring between the last spoke tips and the perimeter wall."""
    ratio = max(1.05, w_max / w_min)
    out: List[Tuple[float, float, int]] = []
    r = p.bore_radius
    r_end = p.outer_radius - end_gap
    guard = 0
    while r < r_end - 1e-6 and guard < 64:
        guard += 1
        r_top = min(r * ratio, r_end)
        if r_end - r_top < min_band:
            r_top = r_end                      # absorb the remainder
        n = max(3, int(round(2 * math.pi * r / w_min)))
        out.append((r, r_top, n))
        if r_top >= r_end - 1e-6:
            break
        r = r_top + band_gap
    return out


def radial_ply_vw(p: PolarParams, ply_index: int = 0,
                  w_min: float = 0.6, w_max: float = 1.2,
                  end_gap: float = 1.2, band_gap: float = 0.3,
                  samples: int = 6) -> List[List[Tuple[float, float, float]]]:
    cx, cy = p.center
    phase = math.radians(p.phase_stagger_deg) * ply_index
    paths: List[List[Tuple[float, float, float]]] = []
    for (r_in, r_out, n) in vw_bands(p, w_min, w_max, end_gap, band_gap):
        for i in range(n):
            a = phase + 2 * math.pi * i / n
            ca, sa = math.cos(a), math.sin(a)
            outward = (i % 2 == 0)              # serpentine ordering
            pts: List[Tuple[float, float, float]] = []
            for s in range(samples + 1):
                f = s / samples
                r = r_in + f * (r_out - r_in)
                if not outward:
                    r = r_out - (r - r_in)
                wr = min(w_max, w_min * (r / r_in))
                pts.append((cx + r * ca, cy + r * sa, wr))
            paths.append(pts)
    return paths
