# Polar Cross-Ply Infill

A **polar cross-ply** infill fills an axisymmetric region with roads aligned to a
polar coordinate system about a detected axis, alternating orientation between
layers:

- **Hoop plies** — concentric rings about the axis (roads run circumferentially).
- **Radial plies** — spokes from the bore outward, laid in radius *bands* so
  circumferential spacing stays roughly constant instead of diverging as `1/r`.

Alternating the two is cross-ply plywood in cylindrical coordinates: continuous,
load-path-aligned roads through the full thickness in **both** principal in-plane
directions of a disc/ring/annulus.

![radial ply vs hoop ply](examples/gcode_preview.png)

## Honest positioning (read this first)

This is a **special-purpose** pattern, not a general infill, and it is **not a new
principle**:

- **Concentric infill is already stock** in every major slicer — the hoop plies are
  not new. Only the radial plies + auto-centered alternation are.
- Aligning roads to principal-stress trajectories and alternating to balance
  anisotropy is well established (principal-stress-line / function-aware toolpaths;
  the cross-ply idea). For an axisymmetric disc under axisymmetric load the principal
  stress directions **are** radial and hoop — so this is the closed-form, FEA-free
  *special case* of principal-stress-line infill.
- The contribution is **practical**: a parameterized, dependency-free way to do the
  right thing automatically for a common geometry class (discs, rings, flywheels,
  pulleys, hubs, bearing carriers, pressure annuli) that grid/gyroid ignore and that
  stock concentric only half-serves.

**Use it for** parts loaded by spin, press-fit at the bore, or radial/hoop pressure.
**Don't use it for** non-axisymmetric parts, or parts whose dominant load is torque
hub→rim (this pattern is weakest in torsion — no ±45° reinforcement).

## What's in here

| File | For whom | What it is |
|---|---|---|
| `polar_crossply.py` | slicer devs | Dependency-free reference generator (the pattern math). Ports directly to a slicer `Fill` class. |
| `polar_slicer.py` | people who want to print | Standalone parametric G-code generator for axisymmetric parts. Prints today, no recompiled slicer needed. |
| `demo.py` | anyone | Renders `preview.png` and prints band/coverage stats. |
| `example_config.json` | printers | Example part definition for `polar_slicer.py --config`. |
| `SPEC.md` | slicer devs / PR authors | Full parameter spec, algorithm, mechanics, limitations, and integration plan for the Slic3r family + CuraEngine. |
| `HOWTO_PRINT.md` | printers | Two routes to print today: the generator, and a G-code post-processor for complex outlines. |

## Quickstart — print a part today

No third-party packages needed to generate G-code (Python 3.9+).

```bash
python polar_slicer.py --od 66.2 --id 10.5 --height 9.4 \
    --line_width 1.0 --nozzle_diameter 0.6 \
    --nozzle_temp 210 --bed_temp 60 \
    -o my_rotor.gcode
```

**Before printing:** set temperatures for your material, and paste your printer's
start/end G-code (`--start_gcode_file` / `--end_gcode_file`) — the built-in defaults
are generic Marlin and may not suit your machine. Then preview the `.gcode` and scrub
the layers before committing filament. See `HOWTO_PRINT.md`.

## Adding it natively to a slicer

See `SPEC.md` §7. In the Slic3r family (PrusaSlicer / OrcaSlicer / Bambu / SuperSlicer)
it's a new `InfillPattern` enum value + a `Fill`-derived class implementing
`_fill_surface_single`, clipping the generated polylines to the region ExPolygon. The
band/spoke math ports verbatim from `polar_crossply.py`.

## Status

Reference implementation and standalone generator are working and tested. Native
slicer integration is specified but not yet submitted upstream. Contributions and
print-test data welcome — especially hoop/radial/torsion coupon results vs stock
concentric.

## License

MIT — see `LICENSE`.
