# Polar Cross-Ply FDM Infill — Comparative FEA Study

> **⚠ CORRECTION NOTICE (added 2026-07). Read before using this document.**
>
> 1. **This report covers Steps 1–2 only** (assumptions + closed-form ground truth).
>    Steps 3–6 exist as code (`axisym.py`, `layups.py`, `capacity.py`) but are not
>    written up here.
> 2. **§1.3 is superseded.** It states that at 100 % density all five layups have
>    identical mass "by construction." They do not. Radial plies are not fully dense
>    (areal coverage sweeps 1.00 → 0.50 within each band), and separately, coverage is
>    not the same quantity as mass. Deposition-based mass fractions are
>    `{ISO 1.000, XPLY 1.103, HOOP 0.964, RAD 1.242, G45 1.000}`.
> 3. **Comparative per-mass results are withdrawn pending re-run.** The superseded
>    mass fractions inflated per-mass performance of RAD by 1.56× and XPLY by 1.25×,
>    i.e. in favour of the pattern under study.
>
> See `README.md` in this folder for the full correction log. The closed-form results
> in §3 are unaffected and have been independently reproduced.


**Reference part:** rotor, OD 66.2 mm / bore 10.5 mm / height 9.4 mm, 100 % density,
road width 1.0 mm, layer height 0.4 mm.
**Source of pattern definition:** `SPEC.md`, `polar_crossply.py`, `polar_slicer.py`
(HankLarsen/Polar-Crossply-Infill).

**Status of this document:** Steps 1–2 of the required workflow complete
(assumptions + closed-form ground truth). FEA build, mesh convergence, validation,
and the layup comparison follow in Steps 3–6.

---

## 0. Statement of what this study can and cannot establish

No coupon data exists for this part, this filament, or this printer. The project's own
`PUBLISHING_MEMO.md` lists strength coupons as the highest-value open item — they have
not been run. Per the analysis brief, this study therefore proceeds down path (b):
**clearly-labelled placeholder properties from published literature, used for a
RELATIVE comparison between layups.**

Consequently:

- **Absolute stresses and margins in this report are indicative, not predictive.**
  They must not be used for design sign-off.
- **Ratios between layups are the deliverable.** These are far more robust than the
  absolutes, because they are driven by the *anisotropy ratios* (E₁/E₂, E₁/E₃, σ₁/σ₃)
  rather than by absolute stiffness, and the anisotropy ratios are the better-measured
  quantity in the literature.
- **Nothing here substitutes for the coupon program.** Section 6 lists exactly which
  coupons would make this predictive.

---

## 1. Geometry, coordinates, and layup definitions

### 1.1 Geometry

| Quantity | Symbol | Value |
|---|---|---|
| Bore radius | *a* | 5.250 mm |
| Outer radius | *b* | 33.100 mm |
| Height | *h* | 9.400 mm |
| Radius ratio | *b/a* | 6.305 |
| Layer height | — | 0.400 mm |
| Road width | — | 1.000 mm |
| Total layers | — | 23 (from height / layer height) |

### 1.2 Ply material axes

Every layup is built from the same anisotropic *ply*. Ply axes are:

| Axis | Direction | Physical meaning | Load path |
|---|---|---|---|
| **1** | along the road | continuous extruded polymer | strongest |
| **2** | in-plane, across roads | road-to-road side bond | weaker |
| **3** | build (Z) | layer-to-layer weld | weakest |

For the polar layups, axis 1 maps to θ in a **hoop ply** and to r in a **radial ply**.
Axis 3 is always Z. This mapping is the entire mechanical content of the pattern.

### 1.3 Layups compared (all at equal mass)

At 100 % density every candidate is fully solid, so **mass is identical across all
five layups by construction** — the equal-mass constraint in the brief is satisfied
exactly, with no density bookkeeping required.

| ID | Layup | Description |
|---|---|---|
| **ISO** | solid isotropic ideal | reference only; *not* representative of a printed part |
| **XPLY** | polar cross-ply | alternating R,H per `ply_sequence = "R,H"` |
| **HOOP** | all-concentric | stock concentric infill, every layer |
| **RAD** | all-radial | every layer spokes |
| **G45** | generic ±45° grid | conventional slicer default, alternating |

### 1.4 Pattern features carried into the model

From `polar_crossply.py` / `SPEC.md`, three features materially affect the mechanics
and are **not** cosmetic:

1. **Radius-banded spokes** (`banding = "doubling"`, `band_ratio = 2.0`). Spoke count
   doubles outward so circumferential road spacing stays roughly constant. Consequence:
   a radial ply's *hoop* stiffness is not zero and is **radius-dependent** — it steps up
   at each band boundary. A naive "radial ply = E₁ in r, E₂ in θ" smear is wrong near
   band edges. Modelled as radius-varying properties; band edges taken from
   `_band_edges()`.
2. **Seamless spiral hoop plies** (`hoop_spiral = True`). Removes the stacked
   start/stop seam that would otherwise be a columnar defect line. Modelled as
   *absence* of a seam knockdown, not as added strength.
3. **Helical spoke stagger** (`auto_phase_stagger = True`). Inter-spoke gaps advance
   around the part rather than columning in Z. Same treatment: it removes a defect,
   it does not add material.

> **Flagged modelling limitation.** Items 2 and 3 are *defect-suppression* features.
> A homogenised continuum model cannot reward them, because a homogenised model never
> had the stacked seam in the first place. **The FEA will therefore systematically
> under-credit polar cross-ply relative to a seamed concentric baseline.** This is a
> conservative bias in the direction of *not* overselling the pattern, which is the
> right direction for a study whose author is also the pattern's author.

---

## 2. Material property table

### 2.1 Two placeholder sets

Two materials are carried through every load case, per the brief: **PLA** (desktop FFF,
the accessible case) and **PC** (unfilled polycarbonate, the engineering case). No
fibre-doped materials.

**Every value below is a placeholder. Nothing here is measured on this part.**

#### Set "PLA-LIT" — desktop FFF PLA

| Property | Value | Source / basis | Confidence |
|---|---|---|---|
| E₁ (road) | 3.50 GPa | Sadeghi et al., *Int. J. Adv. Manuf. Technol.* 2020, on-edge 0° | ⚠ literature scatter 1.3–3.5 GPa |
| E₂ (in-plane transverse) | 2.10 GPa | ratio E₂/E₁ = 0.60 from Krupnin et al., *Materials* 16(22):7229, 2023 (753/1255 MPa) | ⚠ ratio borrowed from a different filament |
| E₃ (Z) | 2.10 GPa | upright modulus ≈ 40 % below on-edge (same 2020 source) | ⚠ |
| ν₁₂ | 0.32 | Krupnin 2023, DIC | ⚠ |
| ν₁₃, ν₂₃ | 0.32, 0.35 | **assumed** — not measured anywhere located | ❌ **UNKNOWN** |
| G₁₂ (in-plane shear) | 1.0 GPa | **estimated**, bracketed 0.78–1.33 GPa (matrix-bound vs isotropic-bound) | ❌ **UNKNOWN — drives Case C** |
| G₁₃, G₂₃ | 0.70 GPa | **assumed** bond-dominated | ❌ **UNKNOWN** |
| σ₁ (road tensile) | 55 MPa | 2020 source, on-edge 0° | ⚠ |
| σ₂ (transverse tensile) | **not located** | — | ❌ **UNKNOWN** |
| σ₃ (interlayer tensile) | **5 – 35 MPa** | see note below | ❌ **UNKNOWN, 7× spread** |
| S₁₂ (in-plane shear str.) | **not located** | — | ❌ **UNKNOWN — drives Case C** |
| ρ | 1240 kg/m³ nominal | PLA bulk | ⚠ real print likely 3–5 % lower (porosity) |

> **The σ₃ problem.** The literature disagrees violently on PLA interlayer tensile
> strength. One 2020 study reports upright strength ~91 % below on-edge (→ ≈5 MPa);
> another reports 90° build orientation at 30–35 MPa. That is a **7× spread on the
> single property that governs Case C and every out-of-plane conclusion.** A central
> value of 20 MPa is used, and all Case C results will be reported as a *band* across
> 5–35 MPa rather than a point value. Anyone quoting a single Case C number from this
> study without the band is misusing it.

#### Set "PC-STRAT" — unfilled polycarbonate

| Property | Value | Source / basis | Confidence |
|---|---|---|---|
| E₁ | 2.25 GPa | Stratasys FDM PC data sheet, F900/T16, XZ orientation, ASTM D638 | ✓ vendor, SD 0.050 |
| E₃ | 2.13 GPa | same sheet, ZX orientation | ✓ SD 0.11 |
| E₂ | 2.13 GPa | **assumed equal to E₃** — not on the data sheet | ❌ **UNKNOWN — see warning** |
| σ₁ (yield) | 57.9 MPa | same sheet, XZ | ✓ SD 1.6 |
| σ₃ (break) | 35.5 MPa | same sheet, ZX (no yield point) | ⚠ **SD 9.0 — 25 % CoV** |
| ν | 0.38 | **assumed**, bulk PC | ❌ **UNKNOWN** |
| G₁₂, G₁₃, G₂₃ | derived from E, ν | **no measured shear data** | ❌ **UNKNOWN** |
| ρ | 1200 kg/m³ | specific gravity 1.20, same sheet | ✓ |

> **Two warnings on the PC set.**
> 1. **The Stratasys data is from an industrial heated-chamber machine** (F900, 0.254 mm
>    layers). Interlayer bonding there is much better than on an open-frame desktop
>    printer. **These PC numbers are optimistic for a desktop print** — the real desktop
>    E₃/E₁ and σ₃/σ₁ will be worse, which *increases* the value of an in-plane-aligned
>    pattern. Using this set is therefore conservative for the pattern's case.
> 2. **E₂ is genuinely unmeasured**, and setting E₂ = E₃ is a modelling choice, not a
>    fact. Since in-plane anisotropy E₁/E₂ is precisely what the polar cross-ply pattern
>    exploits, **the entire PC comparison is hostage to this one assumed number.**
>    Sensitivity to it will be reported explicitly.

### 2.2 The ratios that actually drive the comparison

| Ratio | PLA-LIT | PC-STRAT | Why it matters |
|---|---|---|---|
| E₁/E₂ (in-plane) | 1.67 | 1.06 *(assumed)* | governs the stiffness benefit of aligning roads to principal stress |
| E₁/E₃ (out-of-plane) | 1.67 | 1.06 | governs Case D |
| σ₁/σ₃ | 2.8 (band 1.6–11) | 1.63 | governs how badly any out-of-plane load path is punished |

**Prediction to be tested, stated before the FEA is run:** the benefit of polar
cross-ply scales with in-plane anisotropy E₁/E₂. PLA is ~1.7; PC (as assumed) is ~1.06.
**The pattern should therefore show a clearly smaller advantage in PC than in PLA.**
If the FEA shows the opposite, the model is wrong and must be debugged, not reported.

---

## 3. Closed-form ground truth (Step 2)

Plane stress, isotropic, evaluated before any FEA. These are the reference solutions
the FEA must reproduce in Step 5.

### 3.1 Case A — centrifugal / spin

Timoshenko rotating-annulus, plane stress:

- σ_r(r) = (3+ν)/8 · ρω² · [ a² + b² − a²b²/r² − r² ]
- σ_θ(r) = (3+ν)/8 · ρω² · [ a² + b² + a²b²/r² − (1+3ν)/(3+ν) · r² ]

**Results at 10 000 rpm** (ω = 1047.2 rad/s):

| Material | Peak hoop @ bore | Peak radial @ r = √(ab) = 13.18 mm | Bore concentration |
|---|---|---|---|
| PLA (ρ 1240, ν 0.32) | **1.2429 MPa** | 0.4377 MPa | 2.010 |
| PC (ρ 1200, ν 0.38) | **1.2239 MPa** | 0.4312 MPa | 2.009 |

Peak hoop is at the **bore**, as expected. The bore concentration factor of 2.01
recovers the classical limit (→2 as a/b→0) to within 0.5 %, confirming the
implementation.

> **Finding, and it is an inconvenient one.** Stress scales exactly as ω². Taking the
> PLA road-direction placeholder of 55 MPa, hoop stress at the bore does not reach the
> road-direction allowable until roughly **66 000 rpm**, i.e. a rim speed near 230 m/s.
> **For any plausible service speed of a 66 mm printed rotor, centrifugal stress is
> negligible — it is a fraction of a percent of the allowable.** Case A will therefore
> discriminate cleanly between layups in *ratio* terms, but in a regime the part will
> never physically see. This must be stated plainly in any public write-up: spin
> loading is the pattern's best marketing story and its least practically relevant one.

### 3.2 Case B — bore press-fit / interference

Lamé, internal pressure *p* on the bore, free rim:

- σ_θ(r) = p·a²/(b²−a²) · (1 + b²/r²), σ_r(r) = p·a²/(b²−a²) · (1 − b²/r²)
- Bore stress concentration (b²+a²)/(b²−a²) = **1.0516**
- Interference against a rigid shaft: p = δ·E / ( a·[ (b²+a²)/(b²−a²) + ν ] )

**Results at 0.05 mm radial interference (0.10 mm diametral):**

| Material | Contact pressure | Hoop @ bore | Hoop @ rim |
|---|---|---|---|
| PLA (E 3.50 GPa) | 24.30 MPa | **25.56 MPa** | 1.25 MPa |
| PC (E 2.25 GPa) | 14.97 MPa | **15.74 MPa** | 0.77 MPa |

> **Finding.** A 0.05 mm radial interference — a routine, easily-achieved press fit,
> well inside normal printed-part tolerance — produces bore hoop stress of ~26 MPa in
> PLA. Against the 55 MPa road-direction placeholder that is **~46 % of allowable from
> assembly alone, before any service load.** Press-fit, not spin, is the governing load
> case for this part by roughly two orders of magnitude. This is where the hoop plies
> earn their keep, and it is the case the study should lead with.

### 3.3 Case C — in-plane torque, hub → rim

Equilibrium of an annular disc under in-plane torque gives, exactly:

**τ_rθ(r) = T / (2π r² h)**

| Location | Radius | τ_rθ at T = 1 N·m |
|---|---|---|
| Bore | 5.250 mm | **0.6143 MPa** |
| Rim | 33.100 mm | 0.0155 MPa |

> **Important structural point, and it changes how Case C must be run.**
> This stress field is **statically determinate**. It follows from equilibrium alone
> and is therefore **identical for every layup** — isotropic, cross-ply, concentric,
> radial, ±45° grid. No FEA can produce a different Case C stress field, and any FEA
> that does is wrong.
>
> The layups differ in Case C **only** in (i) shear *strength* allowable and (ii)
> torsional *stiffness* (twist rate). So Case C is not a stress-comparison problem at
> all — it is an allowables comparison. This is why the weakness is real and
> unavoidable: **no in-plane road arrangement that lacks ±45° content can reduce the
> shear stress it must carry.** It can only be made of material that survives it.
>
> Isotropic reference twist rates (upper-bound stiffness, since no layup beats
> isotropic in shear): PLA 0.013 °/N·m, PC 0.021 °/N·m.

### 3.4 Case D — axial / plate bending

No closed form is used as ground truth here. The isotropic annular-plate solutions
(Roark) exist, but the quantity of interest — the *ratio* of radial to hoop flexural
rigidity D_r/D_θ for each layup — is inherently a laminate-theory / FEA result. Case D
will be validated against the isotropic Roark case only, and reported as a stiffness
ratio.

---

## 4. Planned FEA model (Step 3 — not yet run)

| Aspect | Plan |
|---|---|
| Cases A, B | 2-D axisymmetric, quadratic quadrilateral elements, cylindrical orthotropy |
| Case C | axisymmetric-with-torsion (u_θ d.o.f. only), same mesh |
| Case D | axisymmetric plate bending, same mesh |
| Layup representation | ply-level orthotropic properties in (r, θ, z), smeared through thickness by classical laminate theory; radial plies given **radius-dependent** properties per the banding schedule |
| Boundary conditions | A: free-free + rotational body load. B: prescribed radial displacement at bore. C: torque couple bore→rim. D: axial pressure, simply supported at rim |
| Mesh convergence | refine until peak stress changes < 5 %, reported as a table |
| Validation | isotropic FEA vs §3 closed form, target < 2 % |
| Toolchain | Python / scikit-fem 12.0.2, numpy 2.4.4, scipy 1.17.1 |

---

## 5. Open items before Step 3

None blocking. Steps 3–6 can proceed on the placeholder sets above.

---

## 6. Coupon program required to make this predictive

Listed in priority order. Items 1–3 are the ones that would change conclusions, not
just sharpen them.

1. **Interlayer tensile (σ₃) and interlayer shear** — the 7× literature spread on σ₃
   is the single largest source of uncertainty in this study. Upright tensile bars,
   printed on the actual machine with the actual filament.
2. **In-plane shear (S₁₂, G₁₂)** — governs Case C entirely, and no value for FDM PLA
   was located. ±45° tensile per ASTM D3518.
3. **In-plane transverse (E₂, σ₂)** — 90° raster bars. For PC this is the assumed
   number the whole comparison rests on.
4. **Road-direction (E₁, σ₁)** — 0° raster bars. Best-covered in the literature, so
   lowest priority despite being the headline number.
5. **As-printed density** — simple mass/volume, to correct the nominal ρ for porosity.
6. **The three application-level tests already in `SPEC.md` §8** — ring hoop tensile,
   radial pull, hub→rim torsion, at equal mass vs stock concentric. These validate the
   *pattern*; items 1–4 validate the *model*. Both are needed, and they are not
   substitutes for each other.

---

## 7. Limitations (running list, to be extended)

1. No measured properties for this part/filament/printer. All absolutes are indicative.
2. σ₃ for PLA carries a 7× literature spread; Case C results are bands, not values.
3. PC E₂ is assumed, not measured, and the PC comparison is sensitive to it.
4. PC data is from an industrial heated-chamber machine; desktop results will be worse.
5. Vendor XZ specimens are printed with default toolpaths (contours + raster), so E₁
   from such sources is a *part-level* modulus, not a true unidirectional ply modulus.
   This blurs the ply-axis definitions used here.
6. Homogenised continuum modelling cannot credit the spiral-seam and helical-stagger
   defect-suppression features; the study under-credits polar cross-ply as a result.
7. Linear elastic, room temperature, quasi-static, no fatigue, no creep, no moisture,
   no residual print stress, no warpage.
8. Perfect road-to-road and layer-to-layer bonding assumed within the homogenisation;
   real voids at road intersections are not modelled.

---

*Steps 1–2 complete. Proceeding to Step 3 (FEA build), Step 4 (mesh convergence),
Step 5 (validation against §3), then Step 6 (layup comparison).*
