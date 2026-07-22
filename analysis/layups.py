"""
Step 6: layup homogenisation + comparative results.

CORRECTION vs the step-1/2 draft: radial plies are NOT fully dense.
Spoke count is set so arc-pitch = road width at each band's INNER radius and the
band splits when pitch reaches 2x width, so areal coverage sweeps 1.00 -> 0.50
within every band.  Measured area-weighted mean coverage = 0.796 (rasterised
check gives 0.834; see mass_audit.py).  Consequence, structural:
  - a radial ply has essentially NO continuous circumferential path wherever
    coverage < 1, so its hoop stiffness collapses -- it is not E2.

CORRECTION 2 (2026-07, from mass_audit.py): COVERAGE IS NOT MASS.
The earlier MASSFRAC used areal coverage phi as the mass fraction. That is wrong.
Coverage is capped at 1.0 and so discards over-deposition; it also ignores the
+-2.5 mm anchor overlap between bands and the tie rings. Measured deposition
(road length x width / annulus area) is the correct mass proxy:

    layup   coverage   DEPOSITED (mass)
    RAD       0.834        1.242
    HOOP      0.964        0.964
    XPLY      0.899        1.103
    G45       ~1.0         1.000

Using coverage as mass understated RAD by 1.56x and XPLY by 1.25x, which
INFLATED their per-mass performance by the same factors -- i.e. the error
flattered the pattern under study. MASSFRAC below is now deposition-based.

NOTE the radial ply simultaneously deposits 124% of the annulus area worth of
road AND leaves ~17% of the area as voids: material piles up in the anchor
overlaps and near each band's inner radius, while gaps open toward each band's
outer radius. That is a real toolpath-quality defect, not a modelling artefact.
See analysis/README.md, "Design consequence".

Mass should ultimately be MEASURED (weigh the printed specimens), not modelled.
"""
import math
import numpy as np

# ------------------------------------------------------------- ply property sets
PLY = {
 'PLA': dict(E1=3.50e9, E2=2.10e9, E3=2.10e9, n12=0.32, n13=0.32, n23=0.35,
             G12=1.00e9, G13=0.70e9, G23=0.70e9, rho=1240.0,
             X=55.0e6, Y=20.0e6, Z=20.0e6, S12=25.0e6),
 'PC':  dict(E1=2.25e9, E2=2.13e9, E3=2.13e9, n12=0.38, n13=0.38, n23=0.38,
             G12=0.815e9, G13=0.772e9, G23=0.772e9, rho=1200.0,
             X=57.9e6, Y=35.5e6, Z=35.5e6, S12=33.0e6),
}
# Y (transverse) and S12 are UNKNOWN placeholders -- see report section 2.

a, b, h = 5.250e-3, 33.100e-3, 9.400e-3
W = 1.0e-3                      # road width
ANCHOR = 2.5e-3
BANDS = [(5.25e-3, 10.50e-3, 33), (10.50e-3, 21.01e-3, 66), (21.01e-3, 33.10e-3, 132)]
PHI_HOOP = 0.9695


def phi_rad(r):
    """areal coverage of a radial ply at radius r (union of bands, capped)."""
    ns = [n for (r0, r1, n) in BANDS if (r0 - ANCHOR) <= r <= (r1 + ANCHOR)]
    if not ns:
        return 0.5
    return min(1.0, max(ns) * W / (2 * math.pi * r))


PHI_RAD_MEAN = 0.7960


# ------------------------------------------------------------------ CLT helpers
def Qmat(p, E1, E2, n12, G12):
    n21 = n12 * E2 / E1
    d = 1 - n12 * n21
    return np.array([[E1/d,       n12*E2/d, 0],
                     [n12*E2/d,   E2/d,     0],
                     [0,          0,        G12]])


def rotQ(Q, th):
    c, s = math.cos(th), math.sin(th)
    T = np.array([[c*c, s*s,  2*s*c],
                  [s*s, c*c, -2*s*c],
                  [-s*c, s*c, c*c - s*s]])
    R = np.diag([1, 1, 2])
    return np.linalg.inv(T) @ Q @ R @ T @ np.linalg.inv(R)


def ply_Q(mat, kind, r):
    """Reduced stiffness of one ply in (r,theta) axes, with coverage knockdown.

    kind: 'H' hoop (axis1 = theta), 'R' radial (axis1 = r), '+45'/'-45'.
    """
    p = PLY[mat]
    if kind == 'H':
        f = PHI_HOOP
        # axis1 = theta -> build Q in (r,theta) directly: E_r = E2, E_t = E1
        Q = Qmat(p, p['E2'], p['E1'], p['n12']*p['E2']/p['E1'], p['G12'])
        return f * Q
    if kind == 'R':
        f = phi_rad(r)
        # roads run radially. E_r scales with coverage.
        # Hoop path exists ONLY where spokes touch (coverage == 1).
        Er = p['E1']
        Et = p['E2'] if f >= 0.999 else 0.02 * p['E2']   # gaps -> no hoop path
        Q = Qmat(p, Er, Et, p['n12'], p['G12'])
        Q = f * Q
        if f < 0.999:                     # in-plane shear also needs continuity
            Q[2, 2] *= 0.15
        return Q
    if kind in ('+45', '-45'):
        Q0 = Qmat(p, p['E1'], p['E2'], p['n12'], p['G12'])
        return rotQ(Q0, math.radians(45 if kind == '+45' else -45))
    if kind == 'ISO':
        E, n = p['E1'], p['n12']
        return Qmat(p, E, E, n, E/(2*(1+n)))
    raise ValueError(kind)


LAYUPS = {
    'ISO':  ['ISO']*4,
    'XPLY': ['R', 'H', 'R', 'H'],
    'HOOP': ['H']*4,
    'RAD':  ['R']*4,
    'G45':  ['+45', '-45', '+45', '-45'],
}
# Deposition-based mass fractions (road length x width / annulus area),
# normalised to a perfectly-packed solid layer = 1.000. See mass_audit.py.
# Superseded values (coverage-based, WRONG as mass):
#   {'ISO':1.000,'XPLY':0.883,'HOOP':0.970,'RAD':0.796,'G45':1.000}
MASSFRAC = {'ISO': 1.000, 'XPLY': 1.103, 'HOOP': 0.964, 'RAD': 1.242, 'G45': 1.000}


def laminate(mat, layup, r):
    """Return (A_matrix_per_thickness, D_bend_per_I, ply_Qs) for a layup."""
    plies = LAYUPS[layup]
    n = len(plies)
    t = 1.0 / n                                   # normalised ply thickness
    zs = np.linspace(-0.5, 0.5, n + 1)
    A = np.zeros((3, 3)); Db = np.zeros((3, 3)); Qs = []
    for k, kind in enumerate(plies):
        Q = ply_Q(mat, kind, r)
        Qs.append(Q)
        A += Q * t
        Db += Q * (zs[k+1]**3 - zs[k]**3) / 3.0
    return A, Db * 12.0, Qs        # x12 so isotropic gives Db == A


def eff_inplane(A):
    """Effective in-plane engineering constants from the A matrix."""
    S = np.linalg.inv(A)
    Er, Et = 1/S[0, 0], 1/S[1, 1]
    nrt = -S[1, 0] / S[0, 0]
    Grt = 1/S[2, 2]
    return Er, Et, nrt, Grt
