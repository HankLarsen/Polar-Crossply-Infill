# Polar Cross-Ply Infill — Specification & Contribution Guide

**Version:** 2.0 (variable-width radial plies)

> **⚠ THIS DOCUMENT IS BEHIND THE CODE (as of v3.1).** It predates three
> corrections that matter more than anything described below:
> **(1)** road width must be *derived*, not chosen — `w = pitch + h(1 − π/4)`,
> the spacing at which rounded bead shoulders nest. Violating this caused every
> dimensional error found in testing.
> **(2)** hoop plies are now seam-distributed concentric rings, not a spiral —
> all four spiral attempts failed on the plate.
> **(3)** pitch is snapped so roads divide the span exactly.
> See `CHANGELOG.md` for the measured before/after. Integration guidance in §7
> remains broadly valid; the parameter table in §3 does not.
**Status:** proposal / reference implementation, test printed
**Target:** open-source FDM slicers (Slic3r family: PrusaSlicer / OrcaSlicer / Bambu Studio / SuperSlicer; CuraEngine noted separately)
**License:** MIT

> **v1 → v2:** the radial ply no longer holds road width constant and grows the
> *spoke count* to chase coverage. It now grows the **road width** in proportion to
> radius, which holds coverage exactly constant. Tie rings, band-crossing anchors and
> circumferential step-overs are gone. See Appendix A for the measured before/after,
> and for what failed along the way.

---

## 1. What this is (and what it is not)

A **polar cross-ply** infill fills a region with roads aligned to a *polar coordinate
system* about a detected or specified axis, and **alternates road orientation between
layers**:

- **Hoop plies** — concentric rings about the axis (roads run circumferentially).
  This is stock concentric infill, reused.
- **Radial plies** — spokes running from the bore outward, with **road width
  proportional to radius**.

Alternating the two produces an FDM analogue of **cross-ply plywood in cylindrical
coordinates**: continuous, load-path-aligned roads through the full thickness in
*both* principal in-plane directions of an axisymmetric part.

### The central idea of v2

Circumferential coverage of a radial ply is

```
    coverage(r) = n · w(r) / (2 π r)
```

where `n` is spoke count and `w` is road width. v1 held `w` constant, so coverage fell
as `1/r` and had to be rescued by periodically doubling `n` — which introduced band
boundaries, tie rings and anchors, all of which deposit material twice in the same
place.

Setting **`w(r) ∝ r`** makes coverage *identically constant*. One band then spans a
radius ratio of exactly `w_max / w_min` with no divergence at all, and the machinery
that existed to paper over the divergence is no longer needed.

Width is produced not by changing the extruder, but by **holding volumetric rate
constant and slowing the head**:

```
    v(r) = Q / (w(r) · h)
```

with `Q` the volumetric rate and `h` the layer height. This is the same principle a
slicer's `max_volumetric_speed` already applies (Section 7.3).

**This is a special-purpose pattern, not a general infill.** It is only meaningful
when the region has a dominant rotational-symmetry axis (discs, rings, flywheels,
pulleys, hubs, bearing carriers, pressure annuli, encoder wheels). On arbitrary
geometry it is meaningless or actively worse than standard patterns.

### Honest prior-art positioning (read before writing a PR/paper)

- **Concentric infill is already stock** in every major slicer. The hoop plies are
  *not* a contribution; only the radial plies + auto-centred alternation are.
- **Variable-width extrusion is not new either.** Arachne (Cura, later
  PrusaSlicer/Orca) already produces variable-width wall paths, and gap fill has
  varied width for years. The contribution is *what* the width is varied to achieve:
  constant polar coverage.
- **Aligning roads to principal stress trajectories, and alternating orientation to
  balance anisotropy, are well established** in the AM literature
  (principal-stress-line / stress-field-aware toolpaths; the cross-ply principle).
  For an axisymmetric disc under axisymmetric load the principal-stress trajectories
  *are* the radial and hoop directions — so this pattern is the **closed-form,
  FEA-free special case** of principal-stress-line infill, not a new principle.
- The defensible contribution is **practical**: a parameterized, dependency-free
  slicer option that does the right thing automatically for a common geometry class
  that grid/gyroid ignore and that stock concentric only half-serves (hoop only).

If you publish, frame it as a convenience feature with an explicit limitations
section, and cite the PSL literature (Section 9).

---

## 2. When to use / when not to

**Use it when** the part is a disc/ring/annulus loaded predominantly by:
- press-fit or interference at the bore *(the governing case in practice — see
  `analysis/`)*,
- radial or hoop pressure,
- centrifugal / spin loading (hoop-dominant, peaks at bore),
- axisymmetric axial/thrust load.

**Do not use it when:**
- the part is not axisymmetric (no natural axis → spokes are arbitrary),
- the dominant load is **torque transmitted hub→rim** (this pattern is *weakest* in
  torsion — no ±45° reinforcement; use a keyed metal hub or a ±45° pattern),
- the part is a thin-walled shell where a single skin direction already governs.

---

## 3. Parameters

All options are `polar_*` and sit under Infill. Names follow Slic3r option-key
convention.

### 3.1 Core

| Option key | Type | Default | Range | Meaning |
|---|---|---|---|---|
| `polar_center_mode` | enum | `auto_hole` | auto_hole, auto_centroid, manual | How to locate the axis. `auto_hole`: centre on the largest interior hole; `auto_centroid`: region area centroid; `manual`: use `polar_center_xy`. |
| `polar_center_xy` | coord | — | — | Explicit axis (manual only). |
| `polar_core_radius` | float mm | `auto` | ≥0 | Radius below which the `r→0` singularity is avoided. Defaults to the detected bore radius, else `4 × extrusion_width`. |
| `polar_core_fill` | enum | `concentric` | solid, concentric, none | Fill inside `polar_core_radius`. |
| `polar_ply_sequence` | string | `R,H` | R/H/G tokens | Repeating per-layer ply order. `R,H` = 1:1; `H,H,R` biases hoop (spin, press-fit); `R,R,H` biases radial. `G` = ±45° rectilinear, for baseline comparisons. |
| `polar_phase_stagger` | float ° / `auto` | `auto` | 0–180 | Rotate the spoke set on each successive **radial** ply so inter-spoke gaps helix rather than stacking into a vertical weak channel. `auto` sweeps one inter-spoke pitch across the radial plies in the part; manual recommend 2–5°. |

### 3.2 Radial ply — variable width (v2)

| Option key | Type | Default | Range | Meaning |
|---|---|---|---|---|
| `polar_radial_mode` | enum | `vw` | vw, banded | `vw`: variable width (current). `banded`: v1 constant-width spoke doubling, retained for comparison only — see Appendix A. |
| `polar_w_min` | float mm | `nozzle_diameter` | ≥ nozzle | Road width at each band's inner radius. Below nozzle diameter is not physical. |
| `polar_w_max` | float mm | `2 × nozzle_diameter` | ≤ ~2× nozzle | Road width ceiling. **This parameter sets band span**: one band covers a radius ratio of `w_max / w_min`. |
| `polar_vol_rate` | float mm³/s | `8.0` | machine-dependent | Volumetric rate held constant across the width sweep; head speed follows from it. Must not exceed the hot end's sustainable rate. |
| `polar_end_gap` | float mm | `0` | ≥0 | Distance the outermost spokes stop short of the perimeter. `0` butts them against the wall. |
| `polar_band_gap` | float mm | `0.3` | ≥0 | Radial gap between bands, so one band's U-turns cannot land on the neighbour's. |
| `polar_min_band` | float mm | `2.0` | ≥0 | If the remainder after a band is shorter than this, it is **absorbed** into that band rather than starting a stub band. Width then caps at `w_max`, so coverage tapers to ~0.95 at the rim — better than a bare ring. |

### 3.3 Hoop ply

| Option key | Type | Default | Range | Meaning |
|---|---|---|---|---|
| `polar_hoop_form` | enum | `rings` | rings, spiral | `rings`: discrete concentric loops. **Proven**: 99.9% coverage, +1% material. `spiral`: one continuous seamless path, no per-ring seam. Measures at +1.7–2.5% material with equal coverage, but is **not yet test printed** — see `SPIRAL_CONCENTRIC.md`. |
| `polar_connector_deg` | float ° | `5` | 0–90 | (spiral only) angular advance of the ring-to-ring connector. `0` is cheapest but stacks connectors into a radial line and makes two 90° corners; `5` precesses them and smooths the motion. |

### 3.4 Reused

| Option | Meaning |
|---|---|
| `infill_overlap` | Road-to-road / road-to-perimeter overlap. |
| `z_hop` | Recommended ON: radial plies make many short travels between spokes. |
| `max_volumetric_speed` | If set, the slicer already produces the v2 speed schedule for free (Section 7.3). |

**Density mapping:** hoop plies use infill density as ring pitch. Radial plies at 100%
density use `w_min = nozzle_diameter`. Below 100%, scale `w_min` down or reduce spoke
count — but note that reducing coverage below 1.0 reintroduces the divergence v2 exists
to eliminate, so sparse polar cross-ply is not recommended.

---

## 4. Algorithm

Per region, per layer.

### 4.1 Setup (once per region)
1. **Resolve axis** from `polar_center_mode`.
2. **Resolve `core_radius`** (bore) and the region's max radius from the axis, clipped
   to the region ExPolygon. For a true annulus these are the ID/OD.
3. **Resolve widths** `w_min`, `w_max` and volumetric rate `Q`.

### 4.2 Ply selection
`ply = polar_ply_sequence[ layer_index mod len(sequence) ]`.

### 4.3 Hoop ply — reuse concentric
Emit the region's **perimeter offset inward** at pitch `line_spacing`, from the inner
wall to `outer − w/2`. That is **stock concentric infill**, and it is the right choice
rather than "true circles about the axis": perimeter-offset generalizes to any outline
(nested squares for a square, ovals for an oval) and covers the corners, whereas true
circles leave a non-circular region's corners with radial coverage only. On a clean
centred disc the two coincide.

Ring count must use **`ceil`**, not `floor` — otherwise a bare strip up to one pitch
wide is left at the perimeter.

With `polar_hoop_form = spiral`, connect the offset loops into one continuous path by
joining each closed loop to the next with a **short** connector. The connector must be
short: a long arc ramp adds material proportional to its arc length and costs ~13% over
a layer (Appendix A).

### 4.4 Radial ply — variable width (the core of v2)

1. **Band the radius by the width ratio.** Starting at `r = core_radius`:

   ```
   r_top = min(r · (w_max / w_min), r_end)
   if (r_end − r_top) < min_band:  r_top = r_end       # absorb the remainder
   n     = round(2 π r / w_min)                         # spokes in this band
   next r = r_top + band_gap
   ```

   where `r_end = outer_radius − end_gap`. Each band spans a radius ratio of
   `w_max / w_min` and carries a fixed spoke count.

2. **Emit spokes** at angles `phase + 2πk/n`, running the full band from `r_in` to
   `r_out`, with width

   ```
   w(r) = min(w_max, w_min · r / r_in)
   ```

   and head speed `v = Q / (w(r) · h)`. Coverage is then constant at
   `n · w_min / (2π r_in) ≈ 1.0` throughout the band, by construction.

   `phase` advances by `phase_stagger × (radial-ply ordinal)` — the helical winding
   advance, so inter-spoke gaps do not column up in Z.

3. **Ordering.** Emit spokes in serpentine order (alternate outward/inward). The hop
   between adjacent spokes is then about one arc-pitch, shorter than
   `travel_retract_min`, so it costs no retract.

4. **No tie rings, no anchors, no circumferential step-overs.** Every road is purely
   radial at a distinct angle, so **radial roads cannot cross one another**. This is
   both a print-quality property and the reason v2 does not over-deposit.

### 4.5 Core
Inside `core_radius`, fill per `polar_core_fill`. This removes the `r→0` singularity.

### 4.6 Emit
Radial-ply paths carry a **per-point width**, so they are not plain polylines. In the
reference implementation each path is `[(x, y, w), …]`. In-slicer they become a
`ThickPolyline` or a sequence of `ExtrusionPath`s each with its own `width`
(Section 7.2). Hoop plies are constant width and remain plain polylines.

---

## 5. Mechanical behaviour (summary; see `analysis/` for detail)

- **Hoop tension (σθ)** — carried by hoop plies, which stack at the bore where σθ
  peaks. Best-supported load. Effective strength ~½ an all-hoop part.
- **Radial tension/compression (σr)** — carried by radial plies. ~½ an all-radial part.
- **In-plane shear / torque hub→rim (τrθ)** — **weakest mode.** No road is aligned to
  the ±45° principal of torsional shear. Note this case is *statically determinate*:
  `τ = T/(2πr²h)` follows from equilibrium alone and is therefore identical for every
  layup. No in-plane road arrangement can reduce the shear it must carry; only the
  allowable changes. The weakness is structural, not a tuning problem.
- **Plate bending / axial** — extreme fibres are hoop; resists hoop-bending better than
  radial-bending. Fine for gentle loads.
- **Interlaminar / Z** — the usual FDM weak plane. The ~90° road crossing between plies
  gives a small plywood-like interlock, but through-thickness peel is unimproved.
- **Balance costs magnitude:** only ~50% of the section works in any one principal
  direction. Bias with `polar_ply_sequence` toward the governing load.
- **v2 note:** removing tie rings removes the circumferential continuity that made the
  radial ply a connected truss. Radial-ply hoop stiffness is now essentially zero
  between spokes; the hoop plies carry that direction. This is the intended division of
  labour, but it means `polar_ply_sequence` must include hoop plies.

---

## 6. Limitations & failure modes (must ship in user docs)

1. **Axisymmetric geometry only.** Garbage on general parts.
2. **Centre singularity** → handled by `polar_core_radius` / `core_fill`; never set
   core radius to 0.
3. **Width ceiling at the rim.** The outermost band caps at `w_max`, so if the
   remainder was absorbed (`min_band`), coverage tapers to ~0.95 near the perimeter.
   Acceptable under squish; if not, reduce `min_band` to force another band, at the
   cost of many short spokes.
4. **Band boundaries** remain small circumferential discontinuities, separated by
   `band_gap`. Stagger radial plies (`phase_stagger`) so they do not stack in Z.
5. **Torsion weakness** — document it; recommend a metal hub for driven parts.
6. **Many short travels** on radial plies. Serpentine ordering keeps them under the
   retract threshold, but enable z-hop and watch for stringing on wet filament.
7. **Volumetric rate is a hard constraint.** `polar_vol_rate` must be sustainable by the
   hot end at the widest road, or the wide sections under-extrude. The failure is
   silent — it shows as thin roads at large radius.
8. **`w_max` beyond ~2× nozzle diameter is not printable.** The road will not lay flat.

---

## 7. Integration — Slic3r family (PrusaSlicer / Orca / Bambu / SuperSlicer)

These share the Slic3r engine; adding an infill is a known procedure. v2 needs one
thing v1 did not: **variable-width extrusion paths**. That machinery already exists.

### 7.1 Enum + options
Add `ipPolarCrossPly` to `InfillPattern` (`libslic3r/PrintConfig.hpp`), register the
`polar_*` `ConfigOptionDef`s, add UI entries (`src/slic3r/GUI/ConfigManipulation.cpp`,
preset pages) and the label in the Fill-pattern combo.

### 7.2 New fill class
`src/libslic3r/Fill/FillPolarCrossPly.{hpp,cpp}` deriving from `Fill`.

For **hoop plies**, reuse the existing concentric fill and return plain `Polylines`
via the usual override:

```cpp
void _fill_surface_single(const FillParams &params,
                          unsigned int thickness_layers,
                          const std::pair<float,Point> &direction,
                          ExPolygon expolygon,
                          Polylines &polylines_out) override;
```

For **radial plies** the width varies along each spoke, so constant-width `Polylines`
are insufficient. Two workable routes, both using machinery already in the tree:

- **`ThickPolyline`** — carries a per-point width and is what the medial-axis and
  Arachne code paths already produce. Build one spoke per `ThickPolyline` and convert
  to extrusion entities with the existing gap-fill helper.
- **Per-segment `ExtrusionPath`** — sample each spoke into a handful of segments and
  emit each as an `ExtrusionPath` with its own `width`. Coarser, but a smaller change.

Either way, override `fill_surface_extrusion()` rather than only
`_fill_surface_single()`, so the fill can emit extrusion entities directly instead of
being forced through constant-width polylines.

Clip everything to the region with `intersection_pl(paths, expolygon)`. Resolve the
axis from the ExPolygon (largest hole for `auto_hole`, else centroid) and pick the ply
from `this->layer_id` and `polar_ply_sequence`.

### 7.3 Speed — you may get it for free
The v2 width sweep assumes constant volumetric rate, i.e. the head slows as the road
widens. **PrusaSlicer's `max_volumetric_speed` already does exactly this**: it caps
feedrate based on the cross-sectional area of the extrusion. If the fill emits correct
per-path widths and the user has a sensible `max_volumetric_speed`, the speed schedule
falls out of existing machinery and the fill need not set feedrates itself.

If it must be explicit, set path speed from `v = polar_vol_rate / (w · layer_height)`.

### 7.4 Register
Add the class to the Fill factory (`Fill::new_from_type`, `src/libslic3r/Fill/Fill.cpp`).

### 7.5 Port
`polar_crossply.py::vw_bands()` and `radial_ply_vw()` are pure arithmetic with no
dependencies and translate directly.

### CuraEngine alternative
Different engine and vocabulary. Add an `EFillMethod` value and an `Infill` branch in
`src/infill.cpp` / `src/infill/`. Cura's variable-width machinery is Arachne, which
originated there, so the width side is well supported. A faster prototype route is a
post-processing plugin that rewrites the infill region.

---

## 8. Validation plan

**Static (in this repo):**
- `analysis/mass_audit.py` — measures **areal coverage** (rasterised, overlaps not
  double-counted) and **deposition** (road length × width ÷ region area) directly from
  the generator. Healthy v2 radial ply: coverage ≈ 1.00, deposition ≈ 1.00, ratio ≈ 1.0.
  A ratio well above 1.0 means material is being laid twice somewhere.
- **Extrusion cross-check:** compare commanded E per mm against a known-good export
  from a mainstream slicer at the same width and layer height. They should match to
  four decimal places. Bead area is `w·h − h²(1 − π/4)`, not `w·h`.
- **Slice sanity:** monotonic Z, no zero-length or region-escaping paths after clipping,
  spokes reaching the wall.

**Physical:**
- `RING_TEST_PLAN.md` — ASTM D2290 split-disk **method** (non-standard printed
  specimen) comparing polar cross-ply against all-hoop, all-radial, ±45° grid and solid
  at equal mass. Report ratios, not absolutes.
- ASTM D2344 short-beam shear for the interlaminar weak mode.
- ASTM D638 coupons at 0°/90°/±45°/Z to supply orthotropic constants for FEA.
- **Weigh the specimens.** It settles the mass question directly rather than modelling it.

**Print-quality checks specific to v2:**
- No visible ring of bulges at band boundaries (that was the v1 anchor overlap).
- No bare ring between the outermost spoke tips and the perimeter wall.
- No stringing from the inter-spoke travels.

---

## 9. References (prior art to cite)

- Principal-stress-line / function-aware toolpath planning for AM (stress-aligned
  infill; adaptive density along load paths).
- Stress-field-aware / stress-driven infill mapping for continuous-fibre composites
  (reported ~200–300% stiffness, up to ~156% strength vs uniform toolpaths).
- Michell load-path / truss theory (classical optimality basis for aligning material to
  stress trajectories).
- **Arachne variable-width toolpath generation** (Cura, later PrusaSlicer/Orca) — the
  prior art for varying road width within a path.
- Stock **concentric** infill in Slic3r/PrusaSlicer/Cura (the shipped half).
- Hoop-plus-helical **filament winding** practice for pressure vessels and flywheels
  (the closest manufacturing analogue).

(Fill in DOIs at submission.)

---

## Appendix A — v1 → v2, measured

Reference rotor: OD 66.2 mm, bore 10.5 mm, height 9.4 mm, 0.6 mm nozzle, 0.4 mm layers.

| | v1 (banded, constant width) | v2 (variable width) |
|---|---|---|
| radial-ply areal coverage | 0.834 | 0.94 – 1.00 |
| radial-ply deposition | 1.242 | ~1.00 |
| ratio (deposition ÷ coverage) | 1.49× | ~0.97× |
| bands | 3 | 2 |
| part mass | 40.4 g | 35.8 g |

v1 simultaneously **deposited 124% of a solid layer's material while covering only 83%
of the area** — material piling up in the anchor overlaps and tie rings while voids
opened toward each band's outer edge. On printed parts this appeared as raised, ropey
rings at the band boundaries with clean gapped spokes between them. No parameter setting
fixed it: lowering `band_ratio` raised coverage to 0.97 but pushed deposition to 1.90,
because every extra band boundary adds another duplicated-material zone. The anchor was
the dominant term (deposition 1.242 at 2.5 mm anchor, 1.021 at 0 mm).

### Things that were tried and failed — do not repeat

- **Hoop spiral v1, plain Archimedean.** Perfect tiling in the bulk (adjacent turns sit
  exactly one pitch apart) but the innermost and outermost turns never close, leaving a
  crescent **void** growing to a full road width at both bore and rim.
- **Hoop spiral v2, closed rings joined by 45° arc ramps.** Closed the voids, but the
  ramp is ~16 mm of extra road per ring at r = 20 mm, i.e. **+13% material** over the
  layer. The ramp was *added* to the rings rather than replacing part of them.
- **Extrusion as `w·h`.** Roads have rounded edges; the correct bead area is
  `w·h − h²(1 − π/4)`. The naive form over-extrudes 4.5% at 0.2 mm layers and **8.6% at
  0.4 mm**, and is invisible in any render.
- **Ring count via `floor`.** Leaves a bare strip up to one pitch wide at the perimeter.
  Use `ceil`.

Every one of these was found by printing, not by rendering.

---

## 10. Files in this reference bundle

- `polar_crossply.py` — dependency-free generator: `vw_bands()`, `radial_ply_vw()`,
  `hoop_ply()`, `grid_ply()`, layer walk, coverage. Ports directly to the Fill class.
- `polar_slicer.py` — standalone parametric G-code generator (prints today, no
  recompiled slicer needed). Contains the extrusion and speed maths.
- `profiles/` — Core One start/end blocks and the v2 reference profile.
- `demo.py` — prints band/coverage stats and renders `preview.png`.
- `analysis/` — comparative study, mass audit, correction log.
- `RING_TEST_PLAN.md`, `FEA_AND_TEST_PLAN.md` — physical validation programme.
- `SPIRAL_CONCENTRIC.md` — the seamless-hoop feature as a standalone proposal.
- `CHANGELOG.md` — version history.
- `SPEC.md` — this document.
