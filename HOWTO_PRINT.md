# How to actually print a polar cross-ply part (no custom slicer required)

Polar cross-ply can't be ticked as an option in stock PrusaSlicer/Orca/Cura without
recompiling. So there are two ways to print it **today**:

- **Route A — parametric generator (`polar_slicer.py`).** Works now, exact, for the
  parts this pattern is *for*: axisymmetric discs / rings / annuli. This is the
  recommended path and is how the reference rotor was actually made.
- **Route B — G-code post-processor.** For axisymmetric parts whose *outline* is too
  complex for Route A (keyed bores, mounting holes, non-flat profile). Described
  below; it's fiddlier and printer-recipe-specific.

---

## Route A — parametric generator (recommended)

You describe the part by numbers; the tool writes printable G-code with walls,
alternating radial/hoop plies, solid top/bottom caps, retraction, and z-hop.

### 1. Requirements
Python 3.9+. No third-party packages needed to generate G-code. (`demo.py`'s preview
needs matplotlib; the slicer itself does not.)

### 2. Point it at your part

```bash
python polar_slicer.py --od 66.2 --id 10.5 --height 9.4 \
    --line_width 1.0 --nozzle_diameter 0.6 \
    --nozzle_temp 210 --bed_temp 60 \
    -o my_rotor.gcode
```

`--id 0` makes a solid disc with no bore (the core is filled per the pattern).

Or drive everything from a JSON file (see `example_config.json`):

```bash
python polar_slicer.py --config example_config.json -o my_rotor.gcode
```

### 3. **Before you print — two things you MUST set**

1. **Temperatures** (`--nozzle_temp`, `--bed_temp`) to match your material.
2. **Start/End G-code.** The built-in defaults are generic Marlin (home, heat, prime
   line). They may not suit your machine. Export the start/end G-code from a *working*
   profile for your printer and pass them in:

   ```bash
   python polar_slicer.py --config example_config.json \
       --start_gcode_file my_start.gcode \
       --end_gcode_file my_end.gcode \
       -o my_rotor.gcode
   ```

   Placeholders available in start/end text: `{nozzle_temp} {bed_temp}
   {first_layer_height} {travel_mm_min} {bed_y_minus}` (and the prime-line
   `{prime_x0} {prime_x1} {prime_y}`).

### 4. Sanity-check before committing filament
- Open the `.gcode` in your slicer's or any G-code **previewer** (PrusaSlicer →
  File ▸ Import ▸ Import G-code, or gcode.ws / other viewers) and scrub the layers:
  confirm it's centered on the bed, walls look right, and layers alternate
  radial / hoop.
- The tool prints a summary (layer count, radial bands, filament length/mass). If the
  bands look wrong (e.g. one giant band), revisit `--infill_density` /
  `--band_ratio` / `--banding`.
- First print: watch the first few radial layers. If the nozzle knocks spokes, raise
  `--z_hop`.

### 5. Tuning cheatsheet
| Want | Change |
|---|---|
| Stronger hoop (spin / press-fit) | `--ply_sequence H,H,R` |
| Stronger radial | `--ply_sequence R,R,H` |
| Lighter / faster (sparse) | `--infill_density 40` |
| Fewer band seams stacking in Z | raise `--phase_stagger_deg` (3–5) |
| Cleaner spokes, more travels | `--spoke_continuity individual` |
| Nicer top surface | more `--solid_cap_layers` |
| Nozzle hitting spokes | raise `--z_hop` |

### What Route A cannot do
Only axisymmetric parts defined by OD / bore / height. No arbitrary outlines,
pockets, gear teeth, off-center holes, or non-flat top/bottom. For those → Route B.

---

## Route B — G-code post-processor (arbitrary outline, experimental)

Idea: slice the part **normally** in your slicer, then rewrite the fill on alternate
layers into radial spokes. This keeps your slicer's walls, supports, brims, and
complex outline, and only swaps the interior fill.

### Recipe
1. In PrusaSlicer/Orca, slice the part with:
   - the region you want cross-plied set to **solid infill** (or 0% infill +
     enough perimeters that the layer is otherwise empty inside the walls),
   - a **known center** — model centered on origin, or note the object center.
2. Run the post-processor. For each layer it:
   - finds the object center (largest enclosed hole, else outline centroid),
   - on **even** layers: leaves the (concentric-ish) fill alone → hoop ply,
   - on **odd** layers: deletes the interior fill moves and injects banded radial
     spokes (same `radial_ply()` geometry from `polar_crossply.py`), clipped to the
     layer's inner-wall loop, with z-hop travels between spokes.

### Status & honesty
This is the fragile part. Robustly parsing every slicer dialect, detecting the fill
region vs walls per layer, and clipping spokes to an arbitrary inner boundary is real
work and printer-recipe-specific. The reference `radial_ply()` math is done and
tested; the parsing/clipping wrapper is the remaining effort. If you want Route B, tell
me the exact slicer + a sample sliced G-code and I'll build the splicer around that
recipe (this is essentially a clean re-implementation of the original
`RADIAL_SPLICE_Zfix` approach, generalized and parameterized).

---

## Which route for which part

| Part | Route |
|---|---|
| Plain disc / ring / washer / flywheel blank / pulley blank | **A** |
| Disc with round bore, flat faces | **A** |
| Disc + keyway / hex bore / bolt circle / gear teeth / bosses | **B** |
| Non-flat (domed, stepped, tapered) profile | **B** (or extend A's profile support) |
| Not axisymmetric at all | neither — the pattern doesn't apply |
