# FEA & Test Plan — Polar Cross-Ply Infill

Purpose: produce **conventional, comparable, defensible** data for the polar
cross-ply pattern — not abstract one-off geometry, and not decorative FEA.

---

## The core problem this plan solves

Polar cross-ply is only meaningful on **axisymmetric** parts. That creates a
tension with standard testing, which is built around prismatic coupons:

- A **D638 dogbone cannot test the layup.** Radial spokes in a straight bar
  radiate from an arbitrary centroid; the pattern is meaningless there. Numbers
  from such a coupon would look comparable and mean nothing.
- But **FEA of an FDM part is worthless without orthotropic material data**, and
  that data is *exactly* what standard coupons are for.

Resolution: **two tiers.** Coupons characterize the MATERIAL. A standardized
*ring* test validates the PATTERN. FEA is validated against tier 1, then used to
predict tier 2 and the application part.

---

## Tier 1 — Material characterization (standard prismatic coupons)

Goal: measure the orthotropic constants that the FEA needs. Fully conventional;
directly comparable to published FDM data.

| Coupon | Standard | Road orientation to load axis | Yields |
|---|---|---|---|
| Tensile dogbone | ASTM D638 (ISO 527) | 0° (roads along load) | E₁, σ₁ᵘˡᵗ, ν₁₂ |
| Tensile dogbone | ASTM D638 | 90° (roads across load) | E₂, σ₂ᵘˡᵗ (bond-limited) |
| Tensile dogbone | ASTM D638 | ±45° | G₁₂ (shear modulus, via off-axis) |
| V-notch shear (optional, better G₁₂) | ASTM D5379 (Iosipescu) | in-plane | G₁₂, τᵘˡᵗ |
| Tensile bar, printed upright | ASTM D638 | Z (across layers) | E₃, interlayer σᵘˡᵗ |
| Short-beam shear | ASTM D2344 | — | interlaminar shear strength |
| Flexural bar (optional) | ASTM D790 | 0° / 90° | flexural modulus cross-check |

**Rules:** minimum 5 replicates per condition; identical machine, material lot,
nozzle, layer height, temperature, and cooling as the application part; report
mean ± standard deviation; record all process parameters. Print all coupons for a
given comparison in the same session where possible.

**Critical:** these coupons are printed with *unidirectional* roads — they are
measuring the material, not the pattern. Do not print polar infill into a dogbone.

---

## Tier 2 — Pattern validation (standardized axisymmetric tests)

Goal: test the layup in geometry where it is meaningful, using a **conventional
standardized method** so the numbers are comparable.

| Test | Standard | What it measures | Why it fits |
|---|---|---|---|
| **Split-disk / NOL ring** | **ASTM D2290** | apparent hoop tensile strength of a ring | The standard method for **filament-wound** rings and pipe — the exact structural analogue of this pattern. Conventional AND axisymmetric. |
| Short-beam shear | ASTM D2344 | interlaminar shear | probes the documented weak mode |
| Torsion, hub→rim | (custom fixture; report method fully) | in-plane shear capacity | the known worst case; must be reported, not hidden |
| Bore press-fit / pin push-out | (custom; report fully) | bore hoop capacity | the real-world failure location |

**Comparison set — same mass, same machine, same session, for every test:**
1. Polar cross-ply (this pattern)
2. All-concentric / hoop only
3. All-radial only
4. Generic 45° grid (the stock default)
5. Solid (upper-bound reference)

Report **ratios** between layups, not just absolute values. Ratios survive
material-lot and machine variation; absolutes do not.

---

## Tier 3 — FEA (only after Tier 1 exists)

FEA's job is to (a) be validated against measured coupons, then (b) predict
configurations you did not build. It is not a substitute for testing.

Sequence: closed-form → mesh convergence → validate vs Tier 1 → predict Tier 2.

---

## Agent prompt — copy/paste

```
# FEA Task: Orthotropic FDM Model — Coupon Validation, then Polar Cross-Ply Prediction

## Role
You are an FEA engineer specializing in additive-manufactured (FDM/FFF) polymer
parts. You are rigorous and skeptical. You state every assumption, refuse to
fabricate material data, prove mesh convergence, and validate against measured
data and closed-form solutions before trusting any result. If you lack an input
required for a valid result, STOP and request it. A colorful but unvalidated
result is worse than an honest "insufficient data."

## Context
"Polar cross-ply" is an FDM infill for axisymmetric parts. It alternates HOOP
plies (concentric/spiral roads, circumferential) with RADIAL plies (spokes,
bore→rim), so roads follow the two principal stress directions of a loaded disc.
Reference: https://github.com/HankLarsen/Polar-Crossply-Infill

IMPORTANT SCOPE RULE: this pattern is only meaningful on axisymmetric geometry.
Do NOT model polar infill in a prismatic dogbone — that configuration is
physically meaningless. Prismatic coupons are used ONLY to characterize and
validate the orthotropic MATERIAL model.

## Inputs provided
[PASTE Tier 1 measured coupon data here: E1, E2, E3, G12, nu12, and strengths
 at 0/90/±45/Z, with mean ± SD and n. If not yet measured, say so — see below.]

Application part: disc, OD 66.2 mm, bore 10.5 mm, height 9.4 mm,
road width 1.0 mm, layer height 0.4 mm.

## If material data is NOT supplied
Do not invent it. Either stop and request it, or proceed explicitly as a
RELATIVE-ONLY study using clearly-labeled published FDM values (cite sources),
stating in every conclusion that absolute stresses are indicative, not
predictive, until calibrated to measured coupons.

## Modeling requirements
1. FDM parts are ORTHOTROPIC. Roads are strong along their length, weaker across
   road-road bonds, weakest across layers (Z). An isotropic model is invalid and
   must never be reported as representative of the printed part.
2. Represent each layup as a laminate/ply stack with per-ply road direction:
   polar cross-ply (alternating R/H), all-hoop, all-radial, 45° grid, solid.
3. Compare at EQUAL MASS. Report ratios between layups.

## Workflow (in order — do not skip or reorder)
1. Restate the problem. List every assumption and material value with its source.
   Flag every unknown explicitly.
2. CLOSED FORM FIRST: for the axisymmetric in-plane cases compute the analytical
   solution — Lamé equations for the pressurized/press-fit annulus, rotating-disc
   equations for spin. This is ground truth.
3. Build the model: state element type, mesh, BCs, and how orthotropy is applied
   per ply (including local cylindrical coordinate system for radial/hoop plies).
4. MESH CONVERGENCE: refine until peak stress changes <5%. Show the study.
5. VALIDATE — TWO CHECKS, both required:
   a. Isotropic FEA case must reproduce the closed-form solution within a few %.
   b. Orthotropic model must reproduce the MEASURED Tier 1 coupon results
      (0°, 90°, ±45°, Z dogbones) within stated tolerance.
   If either fails, STOP and debug. Do not report unvalidated predictions.
6. Only then predict: ASTM D2290 split-disk ring, and the application disc.

## Load cases (keep separate)
- A: Centrifugal/spin — hoop & radial stress vs radius; locate peak (expect hoop
     max at bore); margin per layup.
- B: Bore press-fit/interference — bore hoop stress vs interference.
- C: In-plane torque hub→rim — the KNOWN weak mode. Quantify how much worse.
     Do not let modeling smoothness conceal it.
- D: Axial/plate bending — radial vs hoop bending stiffness.
- E: ASTM D2290 split-disk ring — predict apparent hoop strength per layup.

## Deliverables
- Assumptions & material table (sources; every unknown flagged)
- Closed-form results for A and B
- Mesh convergence evidence
- Validation evidence for BOTH checks in step 5
- Layup comparison per load case, as ratios, with peak locations and failure mode
- Plain-English findings that clearly separate DEMONSTRATED from ASSUMED
- Explicit limitations section, including what remains unvalidated

## Ground rules
- State assumptions before every result.
- Never present isotropic results as representative of a printed part.
- Never model polar infill in prismatic coupon geometry.
- If an input is missing, STOP and request it. Do not fabricate.
- Distinguish "computed from validated model" from "estimated from literature."
- Goal: a defensible relative comparison, not an impressive absolute number.
```

---

## Reporting

For the repo/README, report in this order: measured Tier 1 constants → measured
Tier 2 ratios (with method and n) → FEA predictions clearly labeled as
predictions. State the machine, material, and all process parameters. Publish the
raw data alongside the summary.

Standards cited (verify current revisions before formal use): ASTM D638, D790,
D2290, D2344, D5379; ISO 527.
