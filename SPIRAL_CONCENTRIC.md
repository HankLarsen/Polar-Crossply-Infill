# Seamless Spiral Concentric — standalone feature proposal

Spun out of the polar cross-ply work because it stands on its own and has **much
broader applicability**: it improves any part using concentric infill, not just
axisymmetric ones.

---

## The idea

Stock concentric infill emits a stack of **separate closed loops**. Each loop has a
start/stop point — a seam. Those seams tend to align radially, producing a continuous
weak channel from the interior to the edge, repeated on every layer.

Connect the loops into **one continuous spiral** and the per-loop seams disappear:
one start, one end, load transferring along an unbroken road instead of across
butt-jointed loop ends. It is a scarf joint in the print plane.

---

## Honest prior-art position — read before proposing

This is **not a novel idea** and should never be presented as one.

| Existing thing | What it does | Gap it leaves |
|---|---|---|
| **OrcaSlicer #6898** (open since Sep 2024) | requests exactly this | argued on *surface appearance*, not structure; unimplemented |
| **Archimedean Chords** (Orca, stock) | continuous spiral of concentric arcs | **circles only** — #6898 notes it works "only for perfectly round areas" |
| **Cura "Connect Infill Polygons"** | joins concentric rings into one loop, no travels | joins rings; still not a shape-following spiral. Cura community notes Cura "cannot give you a spiral pattern for the Top/Bottom Skins or infill" |
| **Scarf seam** (shipped, modern slicers) | ramped seam on outer walls | walls only, not infill |
| **Spiral vase mode** | whole part as one spiral | single wall, no infill, whole-part only |

### The actual gap

> A **perimeter-offset-following continuous spiral** for concentric infill that works
> on **arbitrary outlines** — nested squares for a square, ovals for an oval,
> irregular for irregular — not just circles.

That is the contribution. It is an *implementation* of a known, open request, plus a
structural argument nobody has made for it yet.

### The new argument to contribute

#6898 is framed on print quality. The **structural** case is additive and unmade:

- Stacked loop seams form a **columnar defect line** through the part.
- In hoop-loaded parts (press-fit bores, pressure annuli, rings) that column sits
  exactly where hoop tension wants to split the part.
- In watertight parts it is a **candidate leak path**.
- Continuous spiral transfers load along an unbroken road rather than across
  butt-jointed loop ends.

**Caveat to state plainly:** this is a mechanism argument, not a measurement. It is
untested. Any proposal should say so.

---

## Sketch of the implementation

1. Generate the nested offset loops exactly as stock concentric does (this is the part
   that makes it shape-following — reuse, don't reinvent).
2. Connect loop *n* to loop *n+1* with a **gradual radial transition** distributed over
   one revolution, rather than a step at a single point. Distributing the step-over is
   what removes the seam rather than relocating it.
3. Handle the general cases honestly:
   - **Non-convex / re-entrant outlines** where offsets split into multiple islands →
     one spiral per island, seams unavoidable at island boundaries.
   - **Termination** at the innermost loop.
   - **Direction consistency** so the spiral does not fight the wall's seam placement.
4. Expose as an option on the existing concentric pattern (`concentric_spiral` or
   similar), not as a new pattern.

Step 3 is the real work. Steps 1–2 are straightforward; arbitrary topology is not.

### Reference

`polar_crossply.py::_hoop_spiral()` in this repo implements the **circular** case
(a true Archimedean spiral). Note this only covers what Archimedean Chords already
does — it is a reference for the connection logic, **not** the contribution. The
offset-polygon version is the contribution.

---

## Recommended route

**Comment on #6898 offering to implement it. Do not open a competing issue.**

Adding to an existing request is the collaborative move, gets the warmest reception,
and inherits whatever interest that thread has already accumulated. Opening a rival
issue for the same feature reads as territorial.

### Draft comment for #6898

```
Adding a structural argument for this that I don't think has come up in the thread —
it's been discussed here mainly as a surface-quality issue.

Separate loops each have a start/stop seam, and those seams tend to stack radially into
a continuous columnar defect through the part. For hoop-loaded parts (press-fit bores,
pressure annuli, rings) that column sits exactly where hoop tension wants to split the
part, and for watertight parts it's a candidate leak path. A continuous spiral transfers
load along an unbroken road instead of across butt-jointed loop ends — a scarf joint in
the print plane. To be clear, that's a mechanism argument, not a measurement: I haven't
tested it.

On scope: Archimedean Chords already covers the round case, as noted above. The gap
looks like a perimeter-offset-following spiral that works on arbitrary outlines —
nested squares for a square, ovals for an oval. The connection logic matters too:
distributing the step-over over a full revolution removes the seam, whereas stepping at
a single point just relocates it.

I have a working reference for the circular case and I'd be willing to have a go at the
offset-polygon version if there's maintainer appetite. Happy to be told it belongs
out-of-tree.
```

---

## Why this may land before polar cross-ply

- **Broader applicability** — helps any concentric print, not only axisymmetric parts.
- **Already requested** — demand is demonstrated; you are not arguing for a want.
- **Simpler** — no new pattern, no axis detection, no banding, no new parameters.
- **Lower risk for a maintainer** — an option on an existing pattern.

It is also a smaller credit claim: you would be implementing someone else's request,
not introducing an idea. That is a perfectly respectable contribution and the honest
framing.
