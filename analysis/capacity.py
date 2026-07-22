"""Capacity form: load-to-first-ply-failure per layup. Avoids inventing an
operating point, and makes the equal-mass comparison unambiguous."""
import math, numpy as np
from compare import run_solid, run_torsion, D_of_r, RPM, DELTA, TORQUE, ORDER
from layups import (PLY, LAYUPS, MASSFRAC, laminate, ply_Q, phi_rad, a, b, h)


def ply_TH(mat, layup, eps3, r):
    """max Tsai-Hill index over plies for in-plane strain eps3=(e_rr,e_tt,g_rt)."""
    p = PLY[mat]
    worst = 0.0
    for kind in LAYUPS[layup]:
        Q = ply_Q(mat, kind, r)
        sg = Q @ eps3
        if kind == 'H':
            s1, s2, t12 = sg[1], sg[0], sg[2]
        elif kind in ('+45', '-45'):
            th = math.radians(45 if kind == '+45' else -45)
            c, s = math.cos(th), math.sin(th)
            T = np.array([[c*c, s*s, 2*s*c], [s*s, c*c, -2*s*c], [-s*c, s*c, c*c-s*s]])
            s1, s2, t12 = T @ sg
        else:
            s1, s2, t12 = sg[0], sg[1], sg[2]
        f = (s1/p['X'])**2 - (s1*s2)/p['X']**2 + (s2/p['Y'])**2 + (t12/p['S12'])**2
        worst = max(worst, f)
    return worst


def fpf_factor(mat, layup, case):
    """Load multiplier on the reference load at first ply failure."""
    co, s = run_solid(mat, layup, case)
    D = D_of_r(mat, layup)
    worst = 0.0
    for i in range(len(co)):
        r = co[i, 0]
        if r < a*1.001 or r > b*0.999:
            pass
        eps = np.linalg.solve(D(r), s[i])
        w = ply_TH(mat, layup, np.array([eps[0], eps[1], 0.0]), r)
        worst = max(worst, w)
    return 1.0/math.sqrt(worst)


print("="*96)
print("CAPACITY RESULTS -- load to FIRST PLY FAILURE (Tsai-Hill), equal-mass normalised")
print("="*96)

for mat in ('PLA', 'PC'):
    print("\n### %s" % mat)
    print("%-6s %8s | %11s %8s %10s | %11s %8s %10s" %
          ("layup", "mass", "burst rpm", "vs ISO", "per-mass", "max intf mm", "vs ISO", "per-mass"))
    baseA = baseB = None
    rows = []
    for L in ORDER:
        fA = fpf_factor(mat, L, 'A')
        fB = fpf_factor(mat, L, 'B')
        burst = RPM*math.sqrt(fA)          # stress ~ omega^2
        intf = DELTA*fB*1e3                # stress ~ delta
        if baseA is None: baseA, baseB = burst, intf
        rows.append((L, burst, intf))
        print("%-6s %8.3f | %11.0f %8.3f %10.3f | %11.4f %8.3f %10.3f" %
              (L, MASSFRAC[L], burst, burst/baseA, (burst/baseA)/MASSFRAC[L],
               intf, intf/baseB, (intf/baseB)/MASSFRAC[L]))

print("\n" + "="*96)
print("CASE C -- torque to first ply failure  (tau = T/(2 pi r^2 h), peak at bore)")
print("="*96)
for mat in ('PLA', 'PC'):
    print("\n### %s" % mat)
    print("%-6s %14s %10s %10s | %14s %10s" %
          ("layup", "T_fail N.m", "vs ISO", "per-mass", "twist deg/N.m", "vs ISO"))
    base = baseT = None
    for L in ORDER:
        A, _, _ = laminate(mat, L, a)
        # pure shear flow -> strain
        eps = np.linalg.solve(A, np.array([0.0, 0.0, 1.0]))
        f = ply_TH(mat, L, eps, a)
        tau_allow = 1.0/math.sqrt(f)
        Tf = tau_allow * 2*math.pi*a**2*h
        tw = math.degrees(run_torsion(mat, L))
        if base is None: base, baseT = Tf, tw
        print("%-6s %14.3f %10.3f %10.3f | %14.5f %10.3f" %
              (L, Tf, Tf/base, (Tf/base)/MASSFRAC[L], tw, tw/baseT))

print("\n" + "="*96)
print("SENSITIVITY -- Case C ordering vs the two UNMEASURED strengths S12 and Y")
print("="*96)
print("  (XPLY/HOOP fail in pure ply shear -> governed by S12;")
print("   G45 fails in ply transverse tension -> governed by Y)")
print("\n%-10s %10s | %14s %14s %12s" % ("S12 MPa", "Y MPa", "tau_allow 0/90", "tau_allow +-45", "G45 / 0-90"))
X = 55.0
for S12 in (15.0, 25.0, 35.0):
    for Y in (10.0, 20.0, 35.0):
        t090 = S12
        t45 = 1.0/math.sqrt(2/X**2 + 1/Y**2)
        print("%-10.0f %10.0f | %14.2f %14.2f %12.2f" % (S12, Y, t090, t45, t45/t090))
