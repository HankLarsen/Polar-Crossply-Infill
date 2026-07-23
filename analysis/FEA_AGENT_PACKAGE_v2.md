# FEA agent package — v2 geometry

Supersedes `NEXT_AGENT_PROMPT.md` for anything touching mass or the radial ply. The
old prompt was written against v1 (constant-width banded spokes). **v2 changed the
radial geometry**, which changes the two things that most affected the comparison:
mass, and radial-ply hoop stiffness. Read this first.

---

## What changed from v1, and why it matters to the FEA

**v1 radial ply:** constant road width, spoke count doubled at band boundaries, tie
rings and anchors. Deposited 1.242× a solid layer while covering 0.834 — a large
over-deposition concentrated at the band boundaries. This inflated v1's per-mass
numbers (RAD by 1.56×, XPLY by 1.28×) *in the pattern's own favour*, which is the
error the previous FEA pass had to carry.

**v2 radial ply:** road width grows in proportion to radius (`w = w_min·r/r_in`,
capped at `w_max`), which holds coverage constant by construction. No tie rings, no
anchors, no circumferential step-overs.

### Corrected mass fractions — use these

Measured from the v2 generator with `analysis/mass_audit.py` semantics (deposition =
road length × width ÷ region area; coverage = rasterised, overlaps not double-counted):

| layup | v2 coverage | v2 deposition (= MASSFRAC) |
|---|---|---|
| ISO (solid) | 1.000 | 1.000 |
| HOOP | 0.999 | 1.009 |
| RAD | 0.992 | 0.981 |
| XPLY | 0.995 | 0.995 |
| G45 | ~1.0 | 1.000 |

```
MASSFRAC = {'ISO': 1.000, 'XPLY': 0.995, 'HOOP': 1.009, 'RAD': 0.981, 'G45': 1.000}
```

Note how close to 1.0 these now are. The v1 distortion is gone: at equal nominal
density the layups now genuinely use near-equal mass, so per-mass and per-part
comparisons nearly coincide. **Do not reuse the v1 `MASSFRAC`
(`RAD 1.242, XPLY 1.133`)** — `analysis/layups.py` may still contain it; treat the
table above as authoritative and update `layups.py` to match before running.

### The other v2 change the model must reflect

v1 tie rings gave the radial ply some *circumferential* (hoop-direction) continuity.
v2 removed them, so a v2 radial ply has **essentially zero hoop stiffness between
spokes** — it is purely radial roads at distinct angles. The hoop plies carry the
hoop direction entirely. In `layups.py::ply_Q()` the radial ply's transverse modulus
`E2` should therefore be modelled as ~0 (the code already knocks it down; with v2 the
knockdown should be near-total, not the old 0.02·E2 partial). Report sensitivity to
this choice — it is the single most important modelling assumption for the radial ply.

---

## Task (unchanged in spirit from the prior prompt)

Complete the comparative FEA study of polar cross-ply vs baselines. Full role,
workflow, load cases, and ground rules are in `NEXT_AGENT_PROMPT.md`; everything there
still applies **except** the mass fractions and the radial-ply stiffness note above.

### Conflict-of-interest reminder (still critical)

The pattern's inventor commissioned this. A prior pass contained an error that
inflated the pattern's own per-mass numbers, and it survived because it pointed in the
flattering direction. Apply more scrutiny to results favourable to polar cross-ply
than unfavourable ones, and say where you did. With v2 the mass distortion is gone,
which *removes* the previous thumb on the scale — verify that independently rather
than taking it on trust.

### Blocker (unchanged)

`capacity.py` imports `run_solid, run_torsion, D_of_r, RPM, DELTA, TORQUE, ORDER` from
a module `compare.py` that is **not in the repo**. Recover or rewrite it, and state
which.

### Findings to preserve

- Press-fit governs; spin does not, by ~2 orders of magnitude. 0.05 mm radial
  interference ≈ 46% of allowable from assembly alone; spin needs ~66,500 rpm.
- Case C torsion is statically determinate: `τ = T/(2πr²h)` is identical for every
  layup. Any FEA producing a layup-dependent Case C stress field is wrong.
- All material properties are literature/vendor placeholders; no coupons exist.
  Absolute stresses are indicative only; **ratios are the deliverable**.

### Deliverables

1. Resolve the `compare.py` blocker.
2. Update `layups.py::MASSFRAC` to the v2 table above; confirm via `mass_audit.py`
   semantics.
3. Set the v2 radial-ply `E2` knockdown and report sensitivity.
4. Independent verification of `axisym.py` (element formulation, B matrix, torsion
   weak form, stress recovery).
5. Mesh convergence + validation against the closed-form solutions
   (reproduced exactly in the existing report: hoop@bore 1.2429 MPa PLA at 10k rpm;
   Lamé bore hoop 25.56 MPa at 0.05 mm interference; K=1.0516; τ 0.6143 MPa per N·m).
6. Layup comparison per load case, as ratios, with corrected mass.
7. Findings separating DEMONSTRATED from ASSUMED, and an updated limitations list.

---

## Files

- `NEXT_AGENT_PROMPT.md` — the full prompt (read together with this file).
- `axisym.py` — axisymmetric Q8 FE with cylindrical orthotropy + torsion formulation.
- `layups.py` — CLT homogenisation; **update MASSFRAC and the radial E2 knockdown**.
- `capacity.py` — first-ply-failure; **needs compare.py**.
- `mass_audit.py` — reproduces coverage/deposition from the generator.
- `polar_crossply_FEA_report.md` — Steps 1–2 report (closed-form ground truth), with
  its v1 correction notice. Extend it; do not overwrite.
