# Changelog

## v2.0 — 2026-07-22 (current)

**Variable-width radial plies.** Road width now grows in proportion to radius,
from `vw_w_min` (nozzle diameter) to `vw_w_max` (nozzle max road width). Since
coverage = n·w(r)/(2πr), holding width proportional to r keeps coverage exactly
constant, so one band spans a radius ratio of `w_max / w_min` with no
divergence. Width is produced by holding volumetric rate constant and slowing
the head: v = Q / (w·h).

Measured from generated G-code, reference rotor:

| | v1 (banded) | v2 (variable-width) |
|---|---|---|
| radial-ply coverage | 0.834 | 0.94 – 1.00 |
| radial-ply deposition | 1.242 | ~1.00 |
| waste (deposition ÷ coverage) | 1.49× | ~0.97× |
| bands | 3 | 2 |
| part mass | 40.4 g | 35.8 g |

- **No road crossings.** Tie rings, band-crossing anchors and circumferential
  step-overs are gone. Every road is purely radial at a distinct angle, so roads
  cannot cross. Spokes are emitted in serpentine order; the hop between them is
  about one arc-pitch, below `travel_retract_min`, so they do not retract.
- **The last band absorbs the remainder** (`min_band`, default 2 mm) so spoke
  tips butt against the perimeter wall rather than leaving a bare ring. Width
  caps at `w_max` out there, so rim coverage settles near 0.95 rather than 1.00.
- Reference profile: `profiles/rotor_coreone_v2.json`.
- Reference output: `examples/rotor_COREONE_E_varwidth_full.gcode`.
- **Test printed and confirmed**: no stringing, no rim gap, no over-extrusion.

### Also fixed in this cycle

- **Extrusion math.** Bead cross-section was computed as `w·h`. It is now
  `w·h − h²(1 − π/4)`, the rounded-rectangle form Slic3r/PrusaSlicer use, since
  an extruded road has rounded edges. The old form over-extruded by 4.5% at
  0.2 mm layers and **8.6% at 0.4 mm**, and was present in every file up to v5.
  Now matches a known-good PrusaSlicer export to four decimal places
  (0.07958 E/mm, 0.1914 mm²).
- **Hoop ring count** used `floor`, leaving a bare strip up to one pitch wide at
  the perimeter. Now `ceil`. This predated the spiral work.

### Known / deferred

- `hoop_spiral` stays **off**. Three attempts: v1 (plain Archimedean spiral)
  left crescent voids at bore and rim; v2 (45° arc ramps) closed the voids but
  added 13% material; v3 (short connectors) measures well at +1.7–2.5% but is
  **not yet test printed**. See `SPIRAL_CONCENTRIC.md`.
- The study in `analysis/` still assumes v1 geometry. `MASSFRAC` and the
  comparative results need re-running against v2 — see
  `analysis/NEXT_AGENT_PROMPT.md`.
- `SPEC.md` still documents the v1 banded parameters.

## v1.0 — 2026-07-21

Initial release. Banded radial plies (spoke-count doubling), constant road
width, tie rings and anchors. Published to GitHub and Printables.
