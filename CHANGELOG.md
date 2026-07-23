# Changelog

## v3.1 — 2026-07-23 (current)

**The extrusion model is now validated against measured parts.** Six print
iterations drove total deposition from 1.152 to 1.005; predicted and measured
height agree to ~0.2%.

### The core correction: solid-packing width

Adjacent roads must be spaced at `s = w - h(1 - pi/4)` — the bead's *occupied*
width once its rounded shoulders nest, not its widest dimension. Equivalently
`w = s + h(1 - pi/4)`. Every dimensional error this cycle traced to violating it:

| symptom | cause | measured |
|---|---|---|
| under-extruded, dashed roads | 0.6 road at 0.6 pitch = 14% under-packed | visible grooves everywhere |
| over-extruded, domed, OD grew with Z | width set to 1.2x pitch instead of pitch + h(1-pi/4) | height +6 to +8.8% |
| groove between perimeters | walls spaced by full `line_width` | 9.4% too far apart |
| ~2% residual | last hoop ring truncated to 0.164 mm from its neighbour | pitch now snapped |

Deposition ratio by version: **1.152 -> 1.021 -> 1.019 -> 1.005**.

### Changed

- **Road width derived, not chosen.** `w = pitch + h(1 - pi/4)`, computed from
  the *actual* layer height, so the 0.2 mm first layer no longer inherits the
  0.4 mm value (was ~7% over on that layer).
- **Radial width law follows arc pitch**: `w(r) = 2*pi*r/n + h(1 - pi/4)`,
  capped at `w_max`. Previously `w_min * r/r_in`, which inherited any
  width/pitch ratio error and drifted with radius.
- **Pitch snapping**: `pitch = span / round(span / pitch_target)` so rings
  divide the span exactly. Solved by fixed-point iteration since width depends
  on pitch and pitch depends on width through the radius limits.
- **Perimeter spacing** uses the same rule instead of full `line_width`.
- **Hoop plies are seam-distributed concentric rings** (`rings_seamed`), seams
  advanced by the golden angle both across rings within a layer and across
  layers. Replaces the spiral.
- **Wall seams** golden-distributed the same way.

### Abandoned, with reasons — do not rebuild

- **Seamless spiral hoop, all four attempts.** v1 Archimedean left crescent
  voids at bore and rim; v2 (45 deg arc ramps) closed them but added 13%
  material; v3 (short connectors) measured well but was never printed;
  v4 (truncate + tapered caulk) printed but the bore terminus blobs and strings.
  Rings are trivially reliable and the golden angle solves their only cost.
- **Scarfed helical wall.** A full-circumference Z-ramp cannot work on layer 0:
  it ramps the nozzle 0.2 -> 0.4 mm over a flat bed, up to 2x under-extruded,
  and the whole wall stack lifts off. Confirmed on a printed part — the outer
  perimeter came away by hand.
- **Golden-angle advance on a ramped wall.** Breaks Z-registration; the gap
  swings 0.247-0.647 mm for a 0.4 mm layer, and the tall end exceeds what a
  0.6 mm nozzle can lay.

### Known / deferred

- Radial plies sit at 1.014 — that is the band-gap caulk, deliberate, not error.
- `SPEC.md` still documents the v2 scheme; it predates the width law, seamed
  rings and pitch snapping.
- No strength data exists. See `RING_TEST_PLAN.md`.

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

## v1.0 — 2026-07-21

Initial release. Banded radial plies (spoke-count doubling), constant road
width, tie rings and anchors. Published to GitHub and Printables.
