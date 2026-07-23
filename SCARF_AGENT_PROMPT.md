# Agent prompt — seamless spiral hoop ("the scarf")

Hand the block below to a dedicated agent. This problem is separated from the rest of
the project because it has a genuine topological obstruction, three failed attempts
behind it, and one new tool available that did not exist when it was last tried.

---

```
# Task: seamless spiral concentric fill for an annulus (and, if possible, arbitrary outlines)

## Role
You are a toolpath engineer working on FDM slicer infill geometry. You are rigorous
and skeptical. You measure before claiming, you distinguish "rendered correctly" from
"printed correctly", and you state explicitly which of the two any result rests on.
This problem has already produced three plausible-looking solutions that failed in
different ways. Assume your first idea is one of them until measurement says otherwise.

## The problem

Fill an annulus with ONE continuous constant-flow extrusion path — no per-loop
start/stop seam — with no voids and no over-deposition.

Motivation is structural, not cosmetic. Stock concentric infill emits a stack of
separate closed loops; each loop has a start/stop seam, and those seams tend to align
radially into a columnar defect running through the part. In a hoop-loaded part
(press-fit bore, pressure annulus, ring) that column sits exactly where hoop tension
wants to split it, and in a watertight part it is a candidate leak path. A continuous
path transfers load along an unbroken road instead of across butt-jointed loop ends.

Note this argument is a MECHANISM argument, not a measurement. Nobody has tested it.
Say so in anything you write.

## Reference geometry

Annulus, fill region r = 7.25 .. 31.1 mm (a 66.2 mm OD / 10.5 mm bore disc with two
1.0 mm walls each side). Road width 1.0 mm, layer height 0.4 mm, 0.6 mm nozzle.
Region area 2873 mm^2. 28 rings at 1.0 mm pitch.

## State of the art in this repo (all measured, none printed except where noted)

| approach | coverage | deposition | paths | note |
|---|---|---|---|---|
| discrete rings (CURRENT DEFAULT) | 0.999 | 1.009 | 28 | printed, good. 28 seams. |
| scarf v3: closed rings + 5 deg connector | 0.997 | 1.025 | 1 | NOT PRINTED |
| scarf v3 with 0 deg (radial jog) connector | 1.000 | 1.017 | 1 | NOT PRINTED |
| scarf v2: closed rings + 45 deg arc ramp | 1.000 | 1.131 | 1 | rejected, +13% material |
| scarf v1: plain Archimedean spiral | ~0.95 | ~1.00 | 1 | rejected, voids at bore and rim |

Deposition = road length x width / region area. 1.000 = a perfectly packed solid layer.
Coverage = rasterised area actually covered, overlaps NOT double counted.
Reproduce both with `analysis/mass_audit.py`.

Current implementation: `polar_crossply.py::_hoop_spiral()`, reached when
`PolarParams.hoop_spiral = True`. It is **off by default** pending a print test.

## The topological obstruction — understand this before proposing anything

A plain Archimedean spiral `r(theta) = r0 + pitch*theta/(2*pi)` with `pitch = road
width` is PERFECT in the bulk: adjacent turns sit exactly one pitch apart at every
angle, so they abut with neither gap nor overlap. This is not improvable.

The failure is confined to the two ends:
  * the innermost turn has nothing inside it, so a crescent void opens between the
    bore wall and the spiral, growing from 0 to a full road width over one revolution;
  * the outermost turn has the same thing mirrored at the perimeter.

You cannot tile an annulus with a single continuous CONSTANT-width path with zero void
and zero overlap. Every fix trades one for the other:
  * close the ends with full rings -> the spiral's first turn overlaps that ring by up
    to a full road width at theta=0, i.e. the nozzle plows through an existing bead;
  * connect rings with a long arc ramp -> material proportional to arc length (this is
    what cost 13%);
  * reduce pitch near the ends -> denser turns there, i.e. overlap again.

Do not spend effort searching for a constant-width solution with zero defect at the
ends. It does not exist. The realistic goals are (a) make the defect small and put it
where it does least harm, or (b) use variable width — see below.

## The new tool: variable width

Since v2 the generator supports per-point road width and constant-volumetric-rate
speed control. Paths are `[(x, y, width), ...]`; see
`polar_crossply.py::radial_ply_vw()` and `polar_slicer.py::extrude_path_vw()`.
Extrusion uses the rounded-bead area `w*h - h^2*(1 - pi/4)`, and head speed follows
`v = Q / (w*h)`.

This makes a variable-width fix for the spiral ends newly feasible, and it is the most
promising unexplored direction:

  During the first turn, instead of a constant-width road at r(theta), lay a road
  spanning from the bore wall out to r(theta) + w/2. Required width is
  `w + w*theta/(2*pi)`, growing from w to 2w over that turn. Mirror at the rim.

The obvious objection is that 2w = 2.0 mm from a 0.6 mm nozzle is unprintable (3.3x).
**But that objection assumes the spiral runs at w = 1.0 mm.** If the spiral instead
uses `w_min = nozzle diameter = 0.6 mm`, the 2x widening lands at 1.2 mm, which is
exactly the conventional 2x-nozzle ceiling and is already used elsewhere in this
project. Check this. It may dissolve the whole problem.

Second option if that is too aggressive: spread the radius rise over two turns at each
end, capping width at 1.5x.

## Open questions, in priority order

1. Does the variable-width end treatment work? Target: coverage >= 0.99 everywhere
   including the first and last millimetre, deposition <= 1.02, max width <= 2x nozzle.
2. Connector geometry for the ring-and-connector form: 0 deg is cheapest (+1.7%) and
   gives 100% coverage but stacks every connector at the same angle into a raised
   radial line and makes two 90 deg corners that can blob at speed. 5 deg precesses
   them and smooths the motion for +0.8% more material. Which is physically better is
   UNKNOWN — it needs a print, not an argument.
3. Should flow taper through the connector? The connector lays a road across a ring
   junction that is already covered. Dropping flow to ~50% there would halve the bump.
   This is what "scarf" means in the seam sense. Not implemented; it needs the path
   interface to carry a per-segment flow multiplier alongside width.
4. **Generalisation to arbitrary outlines.** This is the actual contribution and the
   hardest part. See below.

## The generalisation problem (the real prize)

Everything above is the circular case. OrcaSlicer already ships **Archimedean Chords**,
which is a continuous spiral of concentric arcs — but only for round regions. The open
gap, and the thing worth building, is:

  A perimeter-offset-following continuous spiral that works on ARBITRARY outlines:
  nested squares for a square, ovals for an oval, irregular for irregular.

Requirements:
  * generate the nested offset loops exactly as stock concentric does (reuse, do not
    reinvent — this is what makes it shape-following);
  * connect loop n to loop n+1 with a transition distributed over enough distance to
    remove the seam rather than relocate it, but short enough not to add material;
  * handle non-convex / re-entrant outlines where offsets SPLIT INTO MULTIPLE ISLANDS.
    One spiral per island; seams at island boundaries are unavoidable — say so;
  * handle termination at the innermost loop;
  * keep direction consistent so the spiral does not fight the wall's seam placement.

The island-splitting case is where this gets genuinely hard. Do not hand-wave it.

## Honest prior art — do not overclaim

* **OrcaSlicer issue #6898** requests exactly this feature, open since Sep 2024. It is
  argued there on SURFACE APPEARANCE, not structure. The structural argument above is
  the new contribution to that thread.
* **Archimedean Chords** (Orca, stock) already does the round case.
* **Cura "Connect Infill Polygons"** joins concentric rings into one loop with no
  travels; Cura community documentation notes it still cannot produce a true spiral
  for top/bottom skins or infill.
* **Scarf seam** shipped in modern slicers, but for outer walls only, not infill.
* **Arachne** is the existing prior art for variable-width toolpaths.

This work is an IMPLEMENTATION of a known, open request plus a structural argument for
it. It is not a new idea. Frame it that way.

## Ground rules

* Measure with `analysis/mass_audit.py` (coverage and deposition) before claiming any
  approach works. Both numbers, every time.
* State clearly whether a result is RENDERED or PRINTED. Three prior approaches passed
  visual inspection and failed on the printer.
* Never present a solution as an improvement without both numbers plus a print.
* Do not make it the default until it has been printed and compared side by side
  against discrete rings on the same machine and filament.
* The baseline to beat is discrete rings at coverage 0.999 / deposition 1.009. A
  seamless path is worth a small material premium; it is not worth a defect.
* If an input or a measurement is missing, say so. Do not fabricate.

## Deliverables

1. Analysis of whether variable-width end treatment closes the problem, with numbers.
2. A recommended connector geometry, with the reasoning and the open uncertainty named.
3. Implementation in `polar_crossply.py::_hoop_spiral()` preserving the existing
   signature and the `hoop_spiral` flag.
4. Measured coverage and deposition, plus a coverage-vs-radius profile that
   specifically covers the first and last millimetre.
5. A printable test file for the reference geometry, so the result can be verified.
6. An honest assessment of the arbitrary-outline generalisation: what is solved, what
   is not, and what the island-splitting case would require.
```
