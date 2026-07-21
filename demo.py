import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from polar_crossply import PolarParams, layer_paths, coverage, road_length, _band_edges

# Match the user's disc: bore r~5.23, outer r~33.09, 1.0mm road, ~1.0 spacing
p = PolarParams(center=(0,0), outer_radius=33.09, bore_radius=5.23,
                extrusion_width=1.0, line_spacing=1.0, ply_sequence="R,H",
                banding="doubling", band_ratio=2.0, phase_stagger_deg=3.0,
                anchor=2.5, tie_rings=True, spoke_continuity="zigzag")

print("Bands (r_in, r_out, spokes):")
for b in _band_edges(p): print("  %.2f  %.2f  %d"%b)

fig, axs = plt.subplots(1,3, figsize=(15,5.2), facecolor='white')
titles = ["Radial ply (layer 0)","Hoop ply (layer 1)","Radial ply, staggered (layer 2)"]
for ax,(idx,title) in zip(axs, [(0,titles[0]),(1,titles[1]),(2,titles[2])]):
    t, paths = layer_paths(p, idx)
    for pl in paths:
        xs=[q[0] for q in pl]; ys=[q[1] for q in pl]
        ax.plot(xs,ys,'-',lw=0.6,color='#111')
    ax.set_aspect('equal'); ax.axis('off')
    ax.set_title("%s   [%s]  cov=%.0f%%"%(title,t,100*coverage(p,paths)),fontsize=10)
plt.tight_layout(); plt.savefig("preview.png",dpi=130,bbox_inches='tight')

# report coverage for both ply types
for i in range(2):
    t,paths=layer_paths(p,i)
    print("layer %d  type=%s  road=%.0fmm  coverage=%.0f%%"%(i,t,road_length(paths),100*coverage(p,paths)))

# sparse example (density < 100%)
ps = PolarParams(outer_radius=33.09, bore_radius=5.23, extrusion_width=1.0,
                 line_spacing=3.0, ply_sequence="R,H", banding="doubling")
t,paths=layer_paths(ps,0)
print("sparse radial (spacing 3.0): coverage=%.0f%%"%(100*coverage(ps,paths)))
print("OK")
