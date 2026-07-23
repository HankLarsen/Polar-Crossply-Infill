# Spiral + caulk hoop mode (v2.1, experimental)

A seamless hoop-ply method that survived a test print. **Off by default** — the
generator's built-in version does not yet match the quality of the hand-tuned file it
was reverse-engineered from (see "Known gap" below). Enable it deliberately, print it,
compare against `rings` before trusting it.

## The idea

The bore void that sank every earlier spiral attempt is not solved geometrically here.
It is left to exist, then filled:

1. A constant-width spiral (at `w_min` = nozzle diameter) runs **rim → bore** and
   **terminates one pitch short of the bore**, leaving a crescent.
2. A dedicated **caulk sweep** fills that crescent with a road tapering thick → thin
   (0.6 → ~0.09 mm), following the spiral's handedness.
3. The caulk ends with an **early retract** so stored nozzle pressure bleeds into the
   thin tail instead of blobbing.

A cooling/hover pass was tried and found **unnecessary** — it prints fine without it,
so it is not included.

## Enable it

In a config JSON:

```json
{
  "hoop_mode": "spiral_caulk",
  "vw_w_min": 0.6,
  "vw_w_max": 1.2,
  "caulk_early_retract": 1.0
}
```

Or `Config(hoop_mode="spiral_caulk")` in code. Radial plies are unaffected; this only
changes hoop layers. Default remains `hoop_mode="rings"`.

Reference output: `examples/rotor_COREONE_F_spiralcaulk.gcode`.

## Status — parameterized version now matches the printed file

The generator was reverse-engineered from the printed file and now reproduces it:

| metric | generator | printed file |
|---|---|---|
| fill radial reach | 7.35 – 30.8 mm | 7.55 – 30.8 mm |
| spiral pitch | 0.60 mm | 0.60 mm |
| spiral width | 0.60 mm constant | 0.60 mm constant |
| caulk sweep | ~0.97 turn, 0.60 → 0.086 mm | ~0.97 turn, 0.597 → 0.086 mm |
| fill coverage (walls handle edges) | 0.997 | 0.999 |
| deposition | 0.984 | 0.995 |

The earlier apparent "gaps" at the bore (r 7.25–7.9) and rim (r 30–31.1) were a
measurement artifact: those bands are covered by the inner and outer **walls**, not by
the fill. The fill only has to meet the walls, and it does.

It is still **off by default** and still wants a fresh side-by-side print from the
parameterized output (the printed proof was the hand-built file, which is byte-similar
but not identical). Once that print confirms, it can become a supported option.

## What "done" looks like

- Hoop-layer coverage ≥ 0.99 including the first and last millimetre.
- Deposition ≤ ~1.02.
- A clean bore on the plate — no wedge, no blob at the caulk terminus.
- A side-by-side print against `rings` on the same machine and filament, judged by eye
  and (ideally) by a ring-pull test.

Until all four hold, this stays experimental and off by default.
