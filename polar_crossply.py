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

# TODO (next iteration): this is HARDCODED and it is wrong on any layer whose
# height differs from it -- notably the FIRST layer at 0.2 mm, where the
# solid-packing width law w = arc_pitch + h(1-pi/4) then over-commands by ~7%.
# It does not compound (one layer only) but it shows as a proud bottom face /
# elephant's foot. Fix: pass the actual layer height into radial_ply_vw and
# hoop_rings_seamed instead of reading this constant.
LAYER_H_FOR_WIDTH = 0.4   # layer height used by the solid-packing width law
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
             min_band: float = 4.0, embed: float = 0.0,
             pitch: float = None) -> List[Tuple[float, float, int]]:
    """Bands sized by the width ratio. If the remainder after a band is
    shorter than `min_band` it is ABSORBED into that band rather than starting
    a stub band: width simply caps at w_max and coverage dips a little toward
    the rim (~0.95 at full extension), which is far better than leaving a bare
    ring between the last spoke tips and the perimeter wall."""
    pit = pitch if pitch else w_min          # SPACING (may differ from width)
    ratio = max(1.05, w_max / w_min)
    out: List[Tuple[float, float, int]] = []
    # embed: start inside the bore wall and finish inside the perimeter wall, so
    # the spokes key into the walls instead of merely butting against them.
    r = max(w_min, p.bore_radius - embed)
    r_end = p.outer_radius - end_gap + embed
    guard = 0
    while r < r_end - 1e-6 and guard < 64:
        guard += 1
        r_top = min(r * ratio, r_end)
        if r_end - r_top < min_band:
            r_top = r_end                      # absorb the remainder
        n = max(3, int(round(2 * math.pi * r / pit)))   # count from PITCH
        out.append((r, r_top, n))
        if r_top >= r_end - 1e-6:
            break
        r = r_top + band_gap
    return out


def radial_ply_vw(p: PolarParams, ply_index: int = 0,
                  w_min: float = 0.6, w_max: float = 1.2,
                  end_gap: float = 1.2, band_gap: float = 0.3,
                  samples: int = 6, embed: float = 0.0, pitch: float = None,
                  layer_h: float = LAYER_H_FOR_WIDTH,
                  caulk_bands: bool = True,
                  caulk_lap: float = 0.4) -> List[List[Tuple[float, float, float]]]:
    cx, cy = p.center
    phase = math.radians(p.phase_stagger_deg) * ply_index
    paths: List[List[Tuple[float, float, float]]] = []
    for (r_in, r_out, n) in vw_bands(p, w_min, w_max, end_gap, band_gap, embed=embed, pitch=pitch):
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
                # width for SOLID packing at this radius: the tangential gap
                # between adjacent spokes is the arc pitch, so the road must be
                # arc_pitch + h(1-pi/4) -- NOT w_min scaled by r/r_in, which
                # inherits any width/pitch ratio error and drifts with radius.
                wr = min(w_max, 2.0 * math.pi * r / n + layer_h * (1.0 - math.pi / 4.0))
                pts.append((cx + r * ca, cy + r * sa, wr))
            paths.append(pts)

    # ---- band-boundary + bore caulk pass ---------------------------------
    # Two circumferential seams need filling on a radial ply, and BOTH exist
    # even when band_gap == 0:
    #   * each internal band boundary, where the inner band's spokes arrive at
    #     their WIDEST (w_max) and the outer band's leave at their NARROWEST
    #     (w_min). The serpentine U-turns leave a scalloped notch ring.
    #   * the bore, where the innermost spokes start and their U-turns leave the
    #     same scalloping against the wall.
    # CAULKING, literally: the already-solidified spoke ends on either side of
    # the seam act as a MOULD. The ring is injected into that bounded channel,
    # so the material is constrained by existing walls rather than piling up on
    # a flat surface. That is why it fills instead of ridging, and it is why the
    # band gap should be KEPT and filled rather than closed -- the gap is what
    # gives the caulk somewhere to go, and keeps the two bands' U-turns apart.
    # Ring width = gap + lap, so it keys onto the spoke ends at both edges.
    # Emitted LAST so it beds into spoke ends already placed.
    if caulk_bands:
        bands = vw_bands(p, w_min, w_max, end_gap, band_gap, embed=embed, pitch=pitch)
        seg = max(8, int(360.0 / 3.0))
        seams = []
        if bands:
            seams.append((bands[0][0], bands[0][0]))        # bore scallop ring
        for k in range(len(bands) - 1):
            seams.append((bands[k][1], bands[k + 1][0]))    # band boundary
        for (r_lo, r_hi) in seams:
            r_mid = 0.5 * (r_lo + r_hi)
            wring = max(0.0, r_hi - r_lo) + caulk_lap
            if r_mid <= wring / 2:
                continue
            ring = [(cx + r_mid * math.cos(2 * math.pi * i / seg),
                     cy + r_mid * math.sin(2 * math.pi * i / seg),
                     wring) for i in range(seg + 1)]
            paths.append(ring)
    return paths


# ----------------------------------------------------------------------------
# SPIRAL + CAULK HOOP PLY  (v2.1 experimental)
# ----------------------------------------------------------------------------
# The seamless-hoop approach that survived a test print (no cooling pass needed).
# A variable-width spiral runs rim -> bore and terminates early, leaving a small
# crescent at the bore. A dedicated CAULK sweep then fills that crescent with a
# road that tapers thick->thin, finishing with an early retract so stored nozzle
# pressure bleeds into the thin tip rather than blobbing.
#
# Returns a list of typed paths:
#   ("spiral", [(x, y, w), ...])   variable-width, one continuous rim->bore path
#   ("caulk",  [(x, y, w), ...])   tapered crescent fill; caller applies early retract
#
# hoop_spiral must be False for this; select via hoop_mode = "spiral_caulk".
# ----------------------------------------------------------------------------
def hoop_spiral_caulk(p: PolarParams, w_min: float = None, w_max: float = None,
                      seg_deg: float = 3.0, caulk_taper: float = 0.14,
                      caulk_turns: float = 0.97, bore_overshoot: float = 0.2):
    """Reverse-engineered from a printed, working file.

    Measured recipe (0.6 mm nozzle reference part, fill region r 7.55..30.8):
      * spiral: CONSTANT width = w_min, pitch = w_min, rim -> bore, ~38.7 turns.
        It overshoots the fill inner edge by `bore_overshoot` toward the bore
        wall (ends at r_in - bore_overshoot), so the innermost turn sits tight
        against the bore.
      * caulk: ~0.97-turn sweep just OUTSIDE the spiral terminus, r ~8.15 -> 7.86,
        tapering 0.6 -> 0.086 mm (i.e. w_min -> caulk_taper*w_min), filling the
        crescent between the spiral's inner turns and the bore.
      * caller applies an early retract on the caulk tail.

    `w_max` is accepted for signature compatibility but not used: the printed
    spiral is constant width. Widening it is a future variant, not this one.
    """
    cx, cy = p.center
    wmin = w_min if w_min else p.extrusion_width
    r_out = p.outer_radius - wmin / 2.0
    r_in = p.bore_radius + wmin / 2.0
    r_end = max(wmin, r_in - bore_overshoot)      # overshoot toward the bore wall
    if r_out <= r_end:
        return []
    pitch = wmin
    n_turns = (r_out - r_end) / pitch
    steps = max(2, int(n_turns * (360.0 / seg_deg)))
    spiral = []
    for i in range(steps + 1):
        f = i / steps
        r = r_out - f * (r_out - r_end)
        th = 2 * math.pi * n_turns * f            # rim -> bore, CW
        spiral.append((cx + r * math.cos(th), cy + r * math.sin(th), wmin))

    # caulk: one ~full turn just outboard of the spiral end, tapering thick->thin.
    # It sits a little OUTSIDE r_end (where the last full-width turn couldn't reach
    # cleanly) and sweeps inward slightly while thinning to a hair.
    th0 = 2 * math.pi * n_turns
    c_r_start = r_end + pitch                      # ~one pitch out from the terminus
    c_r_end = r_end + 0.5 * pitch
    caulk = []
    csteps = max(12, int(caulk_turns * 360.0 / seg_deg))
    for i in range(csteps + 1):
        f = i / csteps
        r = c_r_start - f * (c_r_start - c_r_end)
        th = th0 + 2 * math.pi * caulk_turns * f
        w = max(0.08, wmin * (1.0 - f) + caulk_taper * wmin * f)
        caulk.append((cx + r * math.cos(th), cy + r * math.sin(th), w))

    out = [("spiral", spiral)]
    if len(caulk) >= 2:
        out.append(("caulk", caulk))
    return out


# ----------------------------------------------------------------------------
# SCARFED PERIMETER WALLS  (v2.2)
# ----------------------------------------------------------------------------
# Each wall layer is a FULL-CIRCUMFERENCE Z-ramp: the wall climbs one layer
# height over a complete revolution, so the lap joint is spread around the whole
# ring instead of concentrated at a point seam.
#
# The ramp start (the one remaining junction) advances by the GOLDEN ANGLE
# (137.5 deg) each layer. That is the maximally-even distribution -- the same
# reason sunflower seed spirals never form radial lines -- so junctions never
# stack into a column and never cluster, at any layer count.
#
# Returns [(x, y, z), ...] -- note the Z varies ALONG the path.
# ----------------------------------------------------------------------------
GOLDEN_ANGLE_DEG = 137.50776405003785


def scarfed_wall_loop(center, radius, z_base, layer_h, layer_index,
                      seg_deg=4.0, golden_deg=0.0, direction=1,
                      overlap_deg=0.0):
    """One turn of a CONTINUOUS HELIX wall: ramps z_base -> z_base + layer_h
    over exactly 360 deg, starting at the same angle every layer.

    With golden_deg = 0 and overlap_deg = 0 this is a true helix: layer N ends
    at angle phi, height z+lh, and layer N+1 begins at angle phi, height z+lh --
    the SAME POINT. There is no junction to distribute because there is no
    junction, and Z-registration is exact (gap = layer_h at every angle).

    Advancing the start angle (golden_deg > 0) breaks that registration: the two
    layers sit at different fractions of their ramps, so the gap swings by
    layer_h * advance/360. At the golden angle that is 0.247-0.553 mm for a
    0.4 mm layer -- the tall end exceeds what a 0.6 mm nozzle can lay, and the
    result is visibly varying perimeter width. Keep it at 0.

    overlap_deg is likewise 0: in a continuous helix the scarf is inherent
    (every point of a turn bonds to the turn directly beneath it, all the way
    around). A non-zero overlap would lap at the same angle every layer and
    stack into exactly the vertical seam this is meant to remove.
    """
    phi = math.radians((layer_index * golden_deg) % 360.0) if golden_deg else 0.0
    total = 360.0 + max(0.0, overlap_deg)
    steps = max(12, int(total / seg_deg))
    cx, cy = center
    pts = []
    for i in range(steps + 1):
        f = i / steps
        th = phi + direction * math.radians(total) * f
        z = z_base + min(1.0, f * total / 360.0) * layer_h
        pts.append((cx + radius * math.cos(th), cy + radius * math.sin(th), z))
    return pts


def scarfed_wall_loops(center, cfg_like, z_base, layer_h, layer_index,
                       seg_deg=4.0, overlap_deg=0.0):
    """All perimeter loops for one layer, each scarfed and corkscrewed.

    cfg_like needs: od, id, line_width, outer_walls, inner_walls.
    Outer walls run CCW, inner walls CW, as usual.
    """
    loops = []
    w = cfg_like.line_width
    # outer walls, working inward
    for k in range(cfg_like.outer_walls):
        r = cfg_like.od / 2.0 - w * (0.5 + k)
        loops.append(scarfed_wall_loop(center, r, z_base, layer_h, layer_index,
                                       seg_deg, direction=1, overlap_deg=overlap_deg))
    # inner (bore) walls, working outward
    if cfg_like.id > 0:
        for k in range(cfg_like.inner_walls):
            r = cfg_like.id / 2.0 + w * (0.5 + k)
            loops.append(scarfed_wall_loop(center, r, z_base, layer_h, layer_index,
                                           seg_deg, direction=-1, overlap_deg=overlap_deg))
    return loops


# ----------------------------------------------------------------------------
# PLAIN SPIRAL + DOUBLE CAULK  (v2.2)  -- "spiral_2caulk"
# ----------------------------------------------------------------------------
# A plain Archimedean spiral tiles the bulk PERFECTLY (adjacent turns sit exactly
# one pitch apart). It fails only at the two ends, where a crescent opens against
# the inner and outer walls. So: run the full spiral, then caulk BOTH crescents.
#
# Measured on the reference annulus: plain spiral alone = 0.975 coverage, with
# 100% everywhere except r 7.25-7.85 (51%) and r 30.45-31.10 (53%).
# ----------------------------------------------------------------------------
def hoop_spiral_2caulk(p: PolarParams, w: float = None, seg_deg: float = 3.0,
                       caulk_taper: float = 0.14, caulk_turns: float = 1.0,
                       pitch: float = None):
    cx, cy = p.center
    ww = w if w else p.extrusion_width          # ROAD WIDTH
    pit = pitch if pitch else ww                 # TURN SPACING (may be < width)
    r0 = p.bore_radius + ww / 2.0
    rmax = p.outer_radius - ww / 2.0
    if rmax <= r0:
        return []
    n_turns = (rmax - r0) / pit                  # spacing sets the turn count
    steps = max(2, int(n_turns * (360.0 / seg_deg)))
    spiral = []
    for i in range(steps + 1):
        f = i / steps
        r = r0 + f * (rmax - r0)          # bore -> rim
        th = 2 * math.pi * n_turns * f
        spiral.append((cx + r * math.cos(th), cy + r * math.sin(th), ww))

    def crescent(r_from, r_to, th_start, turns):
        out = []
        cs = max(12, int(abs(turns) * 360.0 / seg_deg))
        for i in range(cs + 1):
            f = i / cs
            r = r_from + f * (r_to - r_from)
            th = th_start + 2 * math.pi * turns * f
            wd = max(0.08, ww * (1.0 - f) + caulk_taper * ww * f)
            out.append((cx + r * math.cos(th), cy + r * math.sin(th), wd))
        return out

    # inner crescent: hugs the bore wall, laid before the spiral leaves it
    inner = crescent(r0, p.bore_radius + 0.12, 0.0, -caulk_turns)
    # outer crescent: hugs the perimeter wall at the spiral's terminus
    outer = crescent(rmax, p.outer_radius - 0.12,
                     2 * math.pi * n_turns, caulk_turns)

    out = [("caulk", inner), ("spiral", spiral), ("caulk", outer)]
    return out


# ----------------------------------------------------------------------------
# SEAM-DISTRIBUTED CONCENTRIC HOOP RINGS  (v3.0)
# ----------------------------------------------------------------------------
# Replaces the spiral+caulk hoop ply. The spiral was seamless in principle but
# its bore terminus never printed cleanly: the tapered caulk tail blobs and
# strings, and the crescent it fills is the least controllable part of the path.
#
# Discrete rings are trivially reliable -- they are what stock concentric does --
# and the ONE thing they cost, a start/stop seam per ring, is exactly what the
# golden angle fixes. Each ring's seam is advanced by 137.5 deg from the ring
# inside it, and the whole set is advanced again per layer, so no two seams in
# the part share an angle and none stack in Z.
#
# Returns [(x, y, w), ...] paths so the variable-width emitter carries the
# correct road width (which is wider than the ring pitch, so the beads nest).
# ----------------------------------------------------------------------------
def hoop_rings_seamed(p: PolarParams, w: float = None, pitch: float = None,
                      seg_deg: float = 3.0, layer_index: int = 0,
                      golden: float = GOLDEN_ANGLE_DEG,
                      layer_h: float = LAYER_H_FOR_WIDTH):
    cx, cy = p.center
    kk = 1.0 - math.pi / 4.0
    pit_target = pitch if pitch else (w if w else p.extrusion_width)
    # Width for SOLID packing at THIS layer height, and a pitch SNAPPED so the
    # rings divide the span exactly. Stepping by a fixed pitch and truncating
    # leaves the last ring a fraction of a step from its neighbour (0.164 mm on
    # the reference part) -- a near-duplicate ring laid on material already
    # there, worth ~2% excess over the layer. Snapping spreads that fraction
    # across every gap instead: pitch = span / round(span / pitch_target).
    # Width depends on pitch and pitch depends on width (through r0/r_max), so
    # solve the pair by fixed-point iteration; it converges in ~3 passes.
    ww = pit_target + layer_h * kk
    pit = pit_target
    for _ in range(6):
        r0 = p.bore_radius + ww / 2.0
        r_max = p.outer_radius - ww / 2.0
        if r_max <= r0:
            return []
        n_gaps = max(1, int(round((r_max - r0) / pit_target)))
        pit = (r_max - r0) / n_gaps
        ww_new = pit + layer_h * kk
        if abs(ww_new - ww) < 1e-9:
            break
        ww = ww_new
    radii = [r0 + k * pit for k in range(n_gaps + 1)]
    steps = max(24, int(360.0 / seg_deg))
    out = []
    for i, r in enumerate(radii):
        # golden advance on BOTH indices: ring-within-layer and layer-within-part
        phase = math.radians((layer_index * golden + i * golden * 0.5) % 360.0)
        ring = [(cx + r * math.cos(phase + 2 * math.pi * k / steps),
                 cy + r * math.sin(phase + 2 * math.pi * k / steps), ww)
                for k in range(steps + 1)]
        out.append(ring)
    return out
