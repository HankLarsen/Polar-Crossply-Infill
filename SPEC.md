# Polar Cross-Ply Infill — Specification & Contribution Guide

**Status:** proposal / reference implementation
**Target:** open-source FDM slicers (Slic3r family: PrusaSlicer / OrcaSlicer / Bambu Studio / SuperSlicer; CuraEngine noted separately)
**Suggested license:** MIT

---

## 1. What this is (and what it is not)

A **polar cross-ply** infill fills a region with roads aligned to a *polar coordinate
system* about a detected or specified axis, and **alternates the road orientation
between layers**:

- **Hoop plies** — concentric rings about the axis (roads run circumferentially).
- **Radial plies** — spokes running from the bore outward (roads run radially),
  laid in **radius bands** so the circumferential road spacing stays roughly
  constant instead of diverging as `1/r`.

Alternating the two produces an FDM analogue of **cross-ply plywood in cylindrical
coordinates**: continuous, load-path-aligned roads through the full thickness in
*both* principal in-plane directions of an axisymmetric part.

**This is a special-purpose pattern, not a general infill.** It is only meaningful
when the region has a dominant rotational-symmetry axis (discs, rings, flywheels,
pulleys, hubs, bearing carriers, pressure annuli, encoder wheels). On arbitrary
geometry it is meaningless or actively worse than standard patterns.

### Honest prior-art positioning (read before writing a PR/paper)

- **Concentric infill is already stock** in every major slicer. The hoop plies are
  *not* a new contribution; only the radial plies + auto-centered alternation are.
- **Aligning roads to principal stress trajectories, and alternating orientation to
  balance anisotropy, are well-established** in the additive-manufacturing
  literature (principal-stress-line / function-aware / stress-field-aware
  toolpaths; the cross-ply/plywood principle). For an axisymmetric disc under
  axisymmetric load the principal-stress trajectories *are* the radial and hoop
  directions — so this pattern is the **closed-form, FEA-free special case** of
  principal-stress-line infill, not a new principle.
- The defensible contribution is **practical**: a parameterized, dependency-free
  slicer option that does the right thing automatically for a common geometry class
  that grid/gyroid ignore and that stock concentric only half-serves (hoop only).

If you publish, frame it as a convenience feature with an explicit limitations
section, and cite the PSL literature (Section 9).

---

## 2. When to use / when not to

**Use it when** the part is a disc/ring/annulus loaded predominantly by:
- centrifugal / spin loading (hoop-dominant, peaks at bore),
- press-fit or interference at the bore,
- radial or hoop pressure,
- axisymmetric axial/thrust load.

**Do not use it when:**
- the part is not axisymmetric (no natural axis → spokes are arbitrary),
- the dominant load is **torque transmitted hub→rim** (this pattern is *weakest*
  in torsion — no ±45° reinforcement; use a keyed metal hub or a ±45° pattern),
- the part is thin-walled shell where a single skin direction already governs.

---

## 3. Parameters

All options are `polar_*` and sit under Infill. Density is remapped to polar-native
spacing (Section 4.2). Names follow Slic3r option-key convention.

| Option key | Type | Default | Range | Meaning |
|---|---|---|---|---|
| `polar_center_mode` | enum | `auto_hole` | auto_hole, auto_centroid, manual | How to locate the axis. `auto_hole`: center on the largest interior hole in the region; `auto_centroid`: region area centroid; `manual`: use `polar_center_xy`. |
| `polar_center_xy` | coord | — | — | Explicit axis (only if manual). |
| `polar_core_radius` | float mm | `auto` | ≥0 | Radius below which the singularity is avoided; defaults to the detected bore radius, else `4×extrusion_width`. |
| `polar_core_fill` | enum | `concentric` | solid, concentric, none | Fill inside `polar_core_radius`. |
| `polar_ply_sequence` | string | `R,H` | R/H tokens | Repeating per-layer ply order. `R,H`=1:1; `H,H,R` biases hoop (spin/press-fit); `R,R,H` biases radial. |
| `polar_phase_stagger` | float ° | `0` | 0–180 | Rotate the spoke set by this angle on each successive **radial** ply, so spokes don't stack into continuous radial weak-seams. Analogous to fill-angle increment. Recommend 2–5°. |
| `polar_banding` | enum | `doubling` | none, doubling, geometric | How spoke count grows with radius. `doubling`: classic dartboard split (×2 at thresholds); `geometric`: recompute count to restore target pitch; `none`: fixed count (only for narrow annuli). |
| `polar_band_ratio` | float | `2.0` | 1.3–3.0 | Split a band when local arc-pitch exceeds `band_ratio × spacing`. 2.0 pairs with `doubling`. |
| `polar_spoke_continuity` | enum | `zigzag` | zigzag, individual | `zigzag`: out–step–in continuous path (fast, few seams; the field-proven form); `individual`: separate anchored spokes (cleaner, more travels). |
| `polar_anchor` | float mm | `2.5` | 0–20 | Length spokes overlap into rim/bore/tie rings. Reuses `infill_anchor` semantics; ties spokes into rings → connected truss. |
| `polar_tie_rings` | bool | `true` | — | On radial plies, also lay concentric tie rings at bore, rim, and each band edge, connecting spoke ends circumferentially. Large strength gain, small cost. |
| (reused) `infill_overlap` | % | 15% | — | Road-to-road / road-to-perimeter overlap. |
| (reused) travel `z_hop` | — | — | — | Recommended ON between spokes to avoid nozzle collision on the many short travels ("Zfix" in the origin part). |

**Density mapping:** the standard "infill %" is converted to a **target
center-to-center road spacing** `line_spacing`. Hoop plies use it as ring pitch;
radial plies use it as the target *arc-pitch*, held within `[spacing,
band_ratio×spacing]` by banding. 100% ⇒ `line_spacing = extrusion_width`.

---

## 4. Algorithm

Per region, per layer:

### 4.1 Setup (once per region)
1. **Resolve axis** from `polar_center_mode`.
2. **Resolve `core_radius`** (bore) and the region's max radius from the axis
   (clip to the region ExPolygon; for a true annulus these are the ID/OD).
3. **Resolve `line_spacing`** from infill density.

### 4.2 Ply selection
`ply = polar_ply_sequence[ layer_index mod len(sequence) ]`.

### 4.3 Hoop ply
Emit concentric circles about the axis from `core_radius + w/2` to `outer − w/2`
at pitch `line_spacing`. **Clip every ring to the region ExPolygon** (rings become
clipped arcs on non-circular / off-center regions; identical to circles on a true
disc). Note this differs from stock "concentric," which offsets inward from the
*perimeter*; polar-hoop draws true circles about the axis. They coincide for the
target geometry.

### 4.4 Radial ply (the core of the contribution)
1. **Band the radius.** Starting `n = ceil(2π·core_radius / spacing)` spokes at the
   bore, march outward; when arc-pitch `2π·r/n > band_ratio·spacing`, close the band
   at that radius and split (`doubling`: `n *= 2`). Repeat to the rim. This keeps
   circumferential coverage ~constant instead of falling as `1/r`.
2. **Emit spokes** for each band at angles `phase + 2πk/n`, from `band_inner −
   anchor` to `band_outer + anchor` (clipped to region), staggered by
   `phase_stagger × (radial-ply ordinal)`.
3. **Continuity:** `zigzag` chains spokes out/in with short circumferential steps at
   band edges; `individual` emits separate segments (anchor each end).
4. **Tie rings** (if enabled): one ring at bore, one at rim, one at each band edge,
   connecting spoke ends → the spokes become a connected radial truss rather than
   free cantilevers.

### 4.5 Core
Inside `core_radius`, fill per `polar_core_fill` (solid raster / a few concentric
rings / nothing). This removes the `r→0` density singularity.

### 4.6 Emit
Convert polylines to the slicer's extrusion path type with width/overlap. In the
reference implementation they are plain polylines; in-slicer they become
`ThickPolyline`/`ExtrusionEntity`.

---

## 5. Mechanical behavior (summary; see the analysis for detail)

- **Hoop tension (σθ)** — carried by hoop plies; the plies stack at the bore where
  σθ peaks. Best-supported load. Effective strength ~½ an all-hoop part.
- **Radial tension/compression (σr)** — carried by radial plies, anchored into
  rings. ~½ an all-radial part.
- **In-plane shear / torque hub→rim (τrθ)** — **weakest mode.** No road is aligned
  to the ±45° principal of torsional shear; carried by bead-shear and spoke bending.
- **Plate bending / axial** — extreme fibers are hoop; resists hoop-bending stress
  better than radial-bending. OK for gentle loads.
- **Interlaminar / Z** — the usual FDM weak plane; the ~90° road crossing between
  plies gives a small plywood-like interlock/crack-deflection bonus, but pure
  through-thickness tension/peel is unimproved.
- Stronger in compression than tension, as all FDM.
- **Balance costs magnitude:** only ~50% of the section works in any one principal
  direction. Bias with `polar_ply_sequence` toward the governing load.

---

## 6. Limitations & failure modes (must ship in user docs)

1. Axisymmetric geometry only; garbage on general parts.
2. Center singularity → handled by `polar_core_radius`/`core_fill`; don't set core
   radius to 0.
3. Coverage divergence with radius → handled by banding; `none` banding only suits
   narrow annuli.
4. Band edges are density discontinuities and potential circumferential gap/seam
   lines; `tie_rings` mitigates. Stagger radial plies (`phase_stagger`) so band
   seams don't stack in Z.
5. Torsion weakness — document; recommend metal hub for driven parts.
6. Many short travels on radial plies → enable z-hop; expect more seams/zits than a
   continuous pattern. `zigzag` minimizes this.

---

## 7. Integration — Slic3r family (PrusaSlicer / Orca / Bambu / SuperSlicer)

These share the Slic3r engine; adding an infill is a known procedure.

1. **Enum + options.** Add `ipPolarCrossPly` to `InfillPattern` (`libslic3r/PrintConfig.hpp`),
   register the `polar_*` `ConfigOptionDef`s, and add the UI entries
   (`src/slic3r/GUI/ConfigManipulation.cpp`, preset pages). Add the label to the
   Fill-pattern combo.
2. **New fill class.** `src/libslic3r/Fill/FillPolarCrossPly.{hpp,cpp}` deriving from
   `Fill`. Implement:
   ```cpp
   void _fill_surface_single(const FillParams &params,
                             unsigned int thickness_layers,
                             const std::pair<float,Point> &direction,
                             ExPolygon expolygon,
                             Polylines &polylines_out) override;
   ```
   Inside: resolve axis from the ExPolygon (largest hole for `auto_hole`, else
   centroid); pick ply from `this->layer_id` and `polar_ply_sequence`; build hoop
   circles or banded spokes exactly as Section 4; **clip to `expolygon`** with
   `intersection_pl(paths, expolygon)`; append to `polylines_out`. Honor
   `params.density` → `line_spacing`, and `params.anchor_length`.
3. **Register** the class in the Fill factory (`Fill::new_from_type`,
   `src/libslic3r/Fill/Fill.cpp`).
4. **Anchoring** is provided by the base infill anchor machinery; set
   `params.anchor_length`/`anchor_length_max` from `polar_anchor`.
5. Port the reference `polar_crossply.py` band/spoke math verbatim — it is written
   to translate directly (pure arithmetic, no numpy).

The community guide "Coding Custom Infills for the Slic3r-Based Slicers" documents
the build and the exact files to touch; follow it for the wiring, use this spec for
the geometry.

### CuraEngine alternative
Different engine/vocabulary. Add an `EFillMethod` value and an `Infill` branch in
`src/infill.cpp` / `src/infill/`, or prototype faster as a **post-processing Python
plugin** that rewrites the infill region of the sparse-infill polygons. The geometry
math is identical.

---

## 8. Validation plan

- **Coverage check** (in `polar_crossply.py`): road_length×width / annulus_area
  should track the requested density within a few %.
- **Print tests:** ring-on-ring hoop tensile (bore burst / diametral pull), radial
  pull, and torsion (hub→rim) coupons, vs stock concentric and vs solid, same mass.
  Expect: hoop ≥ concentric; radial ≫ concentric; torsion ≤ both (document it).
- **Slice sanity:** no "print stability" warnings; spokes anchored; no zero-length
  or region-escaping paths after clipping.

---

## 9. References (prior art to cite)

- Principal-stress-line / function-aware toolpath planning for AM (stress-aligned
  infill; adaptive density along load paths).
- Stress-field-aware / stress-driven infill mapping for continuous-fiber composites
  (reported ~200–300% stiffness, up to ~156% strength vs uniform toolpaths).
- Michell load-path / truss theory (the classical optimality basis for aligning
  material to stress trajectories).
- Multi-axis / reinforced-FDM fiber-alignment work (out-of-plane extensions).
- Stock **concentric** infill in Slic3r/PrusaSlicer/Cura (the shipped half).

(Fill in DOIs at submission; the searches used to assemble this list are in the
chat that generated this document.)

---

## 10. Files in this reference bundle

- `polar_crossply.py` — dependency-free generator (parameters, hoop/radial plies,
  banding, ties, layer walk, coverage). Ports directly to the Fill class.
- `demo.py` — reproduces a real disc, prints bands/coverage, renders `preview.png`.
- `SPEC.md` — this document.
