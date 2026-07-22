# Handoff prompt — continue the polar cross-ply comparative study

Paste the block below to the next analysis agent. It carries the state, the blocker,
the correction already applied, and the guardrails.

---

```
# Task: Complete the polar cross-ply comparative study (Steps 3–6)

## Role
You are an FEA engineer specializing in additive-manufactured (FDM/FFF) polymer parts.
You are rigorous and skeptical. State every assumption, refuse to fabricate material
data, prove mesh convergence, and validate before trusting any result. If an input is
missing, STOP and request it. An unvalidated result is worse than "insufficient data."

## CONFLICT OF INTEREST — read first
The pattern under study was invented by the person commissioning this analysis. A prior
pass contained an error that inflated the pattern's own per-mass performance by 1.25x
(and the all-radial variant by 1.56x). That error survived because it pointed in the
flattering direction. Treat any result favourable to polar cross-ply with MORE scrutiny
than an unfavourable one, and say so explicitly in the write-up when you do.

## State of the work

Repo: https://github.com/HankLarsen/Polar-Crossply-Infill  (see analysis/)

COMPLETE and verified:
- Steps 1–2: assumptions, material placeholder sets, closed-form ground truth.
  All closed-form values independently reproduced exactly:
    Case A spin, hoop@bore 10000 rpm: PLA 1.2429 MPa, PC 1.2239 MPa
    Case B press-fit, 0.05 mm radial interference: p 24.30 MPa, hoop@bore 25.56 MPa
      (PLA); K = (b^2+a^2)/(b^2-a^2) = 1.0516
    Case C torsion: tau = T/(2 pi r^2 h); 0.6143 MPa per N.m at the bore
    PLA hoop@bore reaches the 55 MPa placeholder allowable at ~66,500 rpm (231 m/s rim)
- Geometry: a = 5.250 mm, b = 33.100 mm, h = 9.400 mm; road 1.0 mm; layer 0.4 mm
- Banding extracted from the generator: 33 / 66 / 132 spokes over
  (5.25–10.50), (10.50–21.01), (21.01–33.10) mm

WRITTEN, NOT VALIDATED:
- analysis/axisym.py   Q8 axisymmetric FE, cylindrical orthotropy, plus a separate
                       u_theta torsion formulation. Not independently checked.
- analysis/layups.py   ply homogenisation + CLT. MASSFRAC CORRECTED (see below).
- analysis/capacity.py load-to-first-ply-failure via Tsai-Hill. Math verified correct
                       (factor = 1/sqrt(f); omega ∝ sqrt(f); delta ∝ f).

## BLOCKER — resolve before anything else
`capacity.py` imports `run_solid, run_torsion, D_of_r, RPM, DELTA, TORQUE, ORDER` from
a module `compare.py` that DOES NOT EXIST in the repo. Nothing runs without it. Either
recover it or rewrite it, and state which you did.

## Correction already applied — do not revert
The first pass used areal COVERAGE as the mass fraction. Coverage is capped at 1.0, so
it discards over-deposition, and it ignores the ±2.5 mm anchor overlap between bands
and the tie rings. Deposition (road length x width / annulus area) is the correct mass
proxy. Verified by analysis/mass_audit.py:

    layup   coverage   deposited(mass)   old MASSFRAC   corrected
    RAD       0.834        1.242            0.796         1.242
    HOOP      0.964        0.964            0.970         0.964
    XPLY      0.899        1.103            0.883         1.103
    G45       ~1.0         1.000            1.000         1.000

MASSFRAC = {'ISO': 1.000, 'XPLY': 1.103, 'HOOP': 0.964, 'RAD': 1.242, 'G45': 1.000}

Re-run every per-mass comparison with these. Previous comparative results are withdrawn.

## Your tasks, in order
1. Resolve the compare.py blocker.
2. Independently verify axisym.py: element formulation, the B matrix (e_tt = u_r/r),
   the torsion weak form (g_rt = du/dr - u/r), and the stress recovery. Note that
   stress_nodal() samples at nodal parametric positions rather than extrapolating from
   Gauss points — assess whether that is adequate or should be replaced.
3. MESH CONVERGENCE: refine until peak stress changes < 5%. Report the table.
4. VALIDATE: isotropic FEA vs the closed-form values above, target < 2%. If it fails,
   debug — do not report.
5. Re-run Steps 6 (layup comparison) and the capacity study with corrected MASSFRAC.
6. Write the Steps 3–6 report. The existing report covers Steps 1–2 only and carries a
   correction notice; do not overwrite it, extend it.

## Specific items to scrutinise
- layups.py ply_Q() applies `Et = 0.02 * E2` for radial plies wherever coverage < 1 —
  a 50x knockdown asserting essentially no hoop path. This IGNORES the tie rings, which
  do provide hoop continuity at bore, rim, and every band edge. It is an undefended
  magic number. Bracket it (e.g. 0.02 / 0.10 / 0.25) and report sensitivity.
- capacity.py mixes the 4-component axisymmetric strain with 3-component CLT in-plane
  strain (drops e_zz and g_rz). Assess whether that is acceptable for this aspect ratio.
- capacity.py contains dead code: `if r < a*1.001 or r > b*0.999: pass` — appears to be
  an intended boundary-node skip that was never written. Decide and implement or delete.
- Tsai-Hill uses X for both tension and compression. For a brittle polymer with
  differing tensile/compressive strengths, assess the impact.

## Known modelling limitations to carry forward
- No coupon data exists. All material values are literature/vendor placeholders.
  Absolute stresses are indicative only; RATIOS are the deliverable.
- sigma_3 (interlayer tensile) for FDM PLA spans ~7x in the literature (≈5–35 MPa).
  Report anything depending on it as a BAND, not a value.
- S12 and G12 for FDM PLA were not located in the literature. They govern Case C.
- The PC set assumes E2 = E3; the entire PC comparison rests on that assumed number.
- PC data is from an industrial heated-chamber machine; desktop results will be worse.
- Homogenised continuum modelling cannot credit the spiral-seam and helical-stagger
  features (they suppress defects a homogenised model never had). This under-credits
  the pattern — a conservative bias, unlike the mass error.

## Findings to preserve (they are the study's most useful output)
- Press-fit governs; spin does not, by ~2 orders of magnitude. 0.05 mm radial
  interference gives ~46% of allowable from assembly ALONE. Spin needs ~66,500 rpm.
- Case C is statically determinate: tau = T/(2 pi r^2 h) follows from equilibrium and
  is IDENTICAL for every layup. It is an allowables comparison, not a stress comparison.
  Any FEA producing a layup-dependent Case C stress field is wrong.
- The radial ply deposits 124% of a solid layer's material while covering only 83% of
  the area — over-extrusion in anchor overlaps coexisting with voids at band outer
  edges. This is a real generator defect. NOTE: lowering band_ratio does NOT fix it
  (measured: ratio 1.4 raises coverage to 0.97 but deposition to 1.90, so waste rises
  from 1.49x to 1.96x). Every band split adds another anchor-overlap zone. The anchor
  is the dominant waste term (waste 1.64x at anchor 2.5 mm vs 1.36x at 0). A fix is
  architectural, not a parameter change.

## Deliverables
- Resolution of the compare.py blocker, stated
- Independent verification notes on axisym.py
- Mesh convergence table
- Validation table (FEA vs closed form)
- Layup comparison with CORRECTED mass, as ratios, per load case
- Sensitivity study on the 0.02 knockdown and on sigma_3
- Plain-English findings separating DEMONSTRATED from ASSUMED
- Updated limitations list

## Ground rules
- State assumptions before every result.
- Never present isotropic results as representative of a printed part.
- Never model polar infill in prismatic coupon geometry — it is meaningless there.
- If an input is missing, STOP and request it. Do not fabricate.
- Apply extra scrutiny to results favourable to the pattern, and say where you did.
- Goal: a defensible relative comparison, not an impressive number.
```
