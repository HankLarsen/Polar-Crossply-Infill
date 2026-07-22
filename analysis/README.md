# Analysis — comparative study of polar cross-ply

Supporting analysis for the polar cross-ply pattern. **This folder has a different
evidential status from the rest of the repo:** the code and spec are the deliverable;
this is an in-progress study built on *placeholder material properties*, and its
comparative results are **not yet publishable**. Read §Status before citing anything.

---

## Status

| Part | State | Publishable? |
|---|---|---|
| Closed-form stress solutions (spin, press-fit, torsion) | complete, **independently reproduced** | **yes** |
| Material property survey + gap list | complete | yes, as a gap list |
| FEA implementation (`axisym.py`) | written, not independently validated here | not yet |
| Layup homogenisation (`layups.py`) | **mass bookkeeping corrected** — see below | not yet |
| Capacity / per-mass comparison (`capacity.py`) | **cannot run — `compare.py` missing**; must be re-run with corrected mass | **no** |

**No coupon data exists** for this part, filament, or printer. Every material value is
a literature or vendor placeholder. Absolute stresses are indicative only. The
comparative ratios are the intended deliverable and they are **not** finalised.

---

## Correction log

### 1. Coverage was used as mass (2026-07) — corrected

The first pass set `MASSFRAC` from areal **coverage**. Coverage is capped at 1.0, so
it discards over-deposition, and it ignores the ±2.5 mm anchor overlap between bands
and the tie rings. Deposition (road length × width ÷ annulus area) is the correct
mass proxy.

| layup | coverage | deposited (mass) | old MASSFRAC | corrected |
|---|---|---|---|---|
| RAD | 0.834 | **1.242** | 0.796 | **1.242** |
| HOOP | 0.964 | 0.964 | 0.970 | 0.964 |
| XPLY | 0.899 | **1.103** | 0.883 | **1.103** |
| G45 | ~1.0 | 1.000 | 1.000 | 1.000 |

Because `capacity.py` divides by `MASSFRAC`, the error **inflated per-mass performance
of RAD by 1.56× and XPLY by 1.25×** — i.e. it flattered the pattern under study. That
is the opposite of the report's stated conservative bias, and it is why the
comparative results must be re-run before publication.

Reproduce with `python mass_audit.py`.

### 2. Report is stale relative to the code

`polar_crossply_FEA_report.md` is **Steps 1–2 only**. Its §1.3 claim that "mass is
identical across all five layups by construction" is superseded — first by the
coverage finding, then by the deposition correction above. A Steps 3–6 write-up does
not yet exist.

---

## Findings that ARE solid

All closed-form results were recomputed independently and reproduce exactly.

**Press-fit governs; spin is irrelevant.** For this 66 mm rotor:

- Centrifugal hoop stress at the bore is **1.24 MPa at 10 000 rpm** (PLA placeholder).
  It does not reach the 55 MPa road-direction allowable until **≈66 500 rpm**, a rim
  speed of **231 m/s**. Spin loading is the pattern's best marketing story and its
  least practically relevant one.
- A routine **0.05 mm radial interference** press-fit produces **≈25.6 MPa** bore hoop
  stress — **~46 % of allowable from assembly alone**, before any service load.

Press-fit exceeds spin by roughly two orders of magnitude for realistic operation.
**This is the load case the pattern should be argued on**, and it is where the hoop
plies (which stack at the bore, where hoop stress peaks) do real work.

**Torsion is an allowables problem, not a stress problem.** The in-plane torque field
τ = T/(2πr²h) is *statically determinate* — it follows from equilibrium alone and is
therefore **identical for every layup**. Layups differ only in shear allowable and
twist rate. No in-plane road arrangement lacking ±45° content can reduce the shear it
must carry; it can only be made of material that survives it. This is why the torsion
weakness is structural and unavoidable, not a tuning problem.

---

## Design consequence — a real defect this exposed

The radial ply **deposits 124 % of the material a perfectly-packed solid layer needs,
while covering only 83 % of the area.** Material piles up in the anchor overlaps and
near each band's inner radius; voids open toward each band's outer radius.

That is a toolpath-quality defect in the generator, not a modelling artefact.

**The obvious fix does not work.** Lowering `band_ratio` was proposed to keep coverage
more uniform. Measured, it buys coverage at a worse price in material:

| banding | band_ratio | coverage | deposited | waste (dep/cov) | bands |
|---|---|---|---|---|---|
| doubling | 2.0 | 0.834 | 1.242 | **1.49×** | 3 |
| doubling | 1.4 | 0.972 | 1.904 | 1.96× | 4 |
| geometric | 1.6 | 0.882 | 1.445 | 1.64× | 4 |
| geometric | 1.4 | 0.974 | 1.994 | 2.05× | 6 |

Coverage rises to ~0.97, but deposition nearly doubles, so waste gets worse. Cause:
every band split adds another ±`anchor` overlap zone where material is laid twice, and
with `doubling` the spoke count jumps 2× for a band that needed ~1.4×.

The **anchor overlap is the dominant waste term**:

| anchor (geometric, ratio 1.6) | coverage | deposited | waste |
|---|---|---|---|
| 2.5 mm | 0.882 | 1.445 | 1.64× |
| 1.5 mm | 0.861 | 1.312 | 1.52× |
| 0.5 mm | 0.833 | 1.180 | 1.42× |
| 0.0 mm | 0.820 | 1.113 | **1.36×** |

**Conclusion: there is no parameter setting that fixes this.** Coverage and material
efficiency trade against each other under the current band+anchor architecture, because
every band boundary costs a duplicated-material zone. A real fix is architectural —
e.g. interdigitating spokes across a band boundary instead of overlapping them, tapering
spoke width with radius, or anchoring into the tie ring without duplicating road length.
Reproduce with `mass_audit.py`.

---

## Files

| File | What |
|---|---|
| `polar_crossply_FEA_report.md` | the study report (Steps 1–2; see correction log) |
| `axisym.py` | axisymmetric Q8 FE with cylindrical orthotropy + a separate torsion formulation |
| `layups.py` | ply homogenisation, CLT, coverage model, **corrected** `MASSFRAC` |
| `capacity.py` | load-to-first-ply-failure (Tsai-Hill) per layup — **needs `compare.py`** |
| `mass_audit.py` | reproducible coverage/mass measurement behind the correction |

---

## What would make this predictive

In priority order — items 1–3 change conclusions, not just sharpen them:

1. **Interlayer tensile σ₃ and interlayer shear.** Literature spans a **7× range** for
   FDM PLA (≈5 to ≈35 MPa). Largest single uncertainty in the study.
2. **In-plane shear S₁₂, G₁₂** (ASTM D3518, ±45° tensile). Governs the torsion case
   entirely; no FDM PLA value was located.
3. **In-plane transverse E₂, σ₂** (90° raster bars). For the PC set this is an
   *assumed* number that the whole PC comparison rests on.
4. Road-direction E₁, σ₁ (0° raster bars) — best covered in the literature.
5. **As-printed density** — and simply **weighing specimens**, which settles the mass
   question directly rather than modelling it.
6. The application-level tests in `../RING_TEST_PLAN.md`.

Items 1–4 validate the *model*; item 6 validates the *pattern*. Both are needed and
neither substitutes for the other.
