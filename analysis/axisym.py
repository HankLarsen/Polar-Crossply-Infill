"""
axisym.py -- axisymmetric finite elements with CYLINDRICAL ORTHOTROPY.

Two formulations:
  (1) AxisymSolid : u = (u_r, u_z).  Strains (e_rr, e_tt, e_zz, g_rz).
                    Used for load cases A (spin), B (press-fit), D (bending).
  (2) AxisymTorsion : u = u_theta(r,z).  Strains (g_rt, g_tz).
                    Used for load case C (in-plane hub->rim torque).

Q8 serendipity elements, 3x3 Gauss.  Written directly because cylindrical
orthotropy + the torsion weak form are not stock library forms.
"""
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

# ---------------------------------------------------------------- Q8 shapes
def q8_shape(xi, eta):
    x, e = xi, eta
    N = np.array([
        -0.25*(1-x)*(1-e)*(1+x+e), -0.25*(1+x)*(1-e)*(1-x+e),
        -0.25*(1+x)*(1+e)*(1-x-e), -0.25*(1-x)*(1+e)*(1+x-e),
         0.50*(1-x*x)*(1-e),        0.50*(1+x)*(1-e*e),
         0.50*(1-x*x)*(1+e),        0.50*(1-x)*(1-e*e)])
    dNx = np.array([
        0.25*(1-e)*(2*x+e),  0.25*(1-e)*(2*x-e),
        0.25*(1+e)*(2*x+e),  0.25*(1+e)*(2*x-e),
       -x*(1-e),             0.50*(1-e*e),
       -x*(1+e),            -0.50*(1-e*e)])
    dNe = np.array([
        0.25*(1-x)*(x+2*e),  0.25*(1+x)*(2*e-x),
        0.25*(1+x)*(x+2*e),  0.25*(1-x)*(2*e-x),
       -0.50*(1-x*x),       -e*(1+x),
        0.50*(1-x*x),       -e*(1-x)])
    return N, dNx, dNe

GP = np.array([-np.sqrt(3/5), 0.0, np.sqrt(3/5)])
GW = np.array([5/9, 8/9, 5/9])


# ------------------------------------------------------------------- meshes
def rect_mesh_q8(r0, r1, z0, z1, nr, nz):
    """Structured Q8 mesh of the rectangle [r0,r1] x [z0,z1]."""
    NR, NZ = 2*nr+1, 2*nz+1
    rr = np.linspace(r0, r1, NR)
    zz = np.linspace(z0, z1, NZ)
    R, Z = np.meshgrid(rr, zz, indexing='ij')
    gid = -np.ones((NR, NZ), dtype=int)
    coords = []
    for i in range(NR):
        for j in range(NZ):
            if (i % 2 == 1) and (j % 2 == 1):
                continue                      # drop Q8 centre node
            gid[i, j] = len(coords)
            coords.append((R[i, j], Z[i, j]))
    coords = np.array(coords)
    elems = []
    for ei in range(nr):
        for ej in range(nz):
            i0, j0 = 2*ei, 2*ej
            elems.append([gid[i0,   j0  ], gid[i0+2, j0  ],
                          gid[i0+2, j0+2], gid[i0,   j0+2],
                          gid[i0+1, j0  ], gid[i0+2, j0+1],
                          gid[i0+1, j0+2], gid[i0,   j0+1]])
    return coords, np.array(elems)


# --------------------------------------------------------------- material
def ortho_D_solid(Er, Et, Ez, nrt, nrz, ntz, Grz):
    """4x4 stiffness for (e_rr, e_tt, e_zz, g_rz), cylindrical orthotropy."""
    S = np.zeros((4, 4))
    S[0,0], S[1,1], S[2,2] = 1/Er, 1/Et, 1/Ez
    S[0,1] = S[1,0] = -nrt/Er
    S[0,2] = S[2,0] = -nrz/Er
    S[1,2] = S[2,1] = -ntz/Et
    S[3,3] = 1/Grz
    return np.linalg.inv(S)


def iso_D_solid(E, nu):
    return ortho_D_solid(E, E, E, nu, nu, nu, E/(2*(1+nu)))


# ------------------------------------------------------- solid formulation
class AxisymSolid:
    """u=(u_r,u_z). D may be a callable D(r) for radius-dependent layups."""

    def __init__(self, coords, elems, D):
        self.co, self.el = coords, elems
        self.D = D
        self.ndof = 2*len(coords)

    def _D_at(self, r):
        return self.D(r) if callable(self.D) else self.D

    def assemble(self, rho=0.0, omega=0.0):
        co, el = self.co, self.el
        rows, cols, vals = [], [], []
        F = np.zeros(self.ndof)
        for e in el:
            xy = co[e]
            dof = np.empty(16, dtype=int)
            dof[0::2] = 2*e
            dof[1::2] = 2*e + 1
            ke = np.zeros((16, 16))
            fe = np.zeros(16)
            for gi, wi in zip(GP, GW):
                for gj, wj in zip(GP, GW):
                    N, dNx, dNe = q8_shape(gi, gj)
                    J = np.array([[dNx @ xy[:,0], dNx @ xy[:,1]],
                                  [dNe @ xy[:,0], dNe @ xy[:,1]]])
                    detJ = np.linalg.det(J)
                    dN = np.linalg.solve(J, np.vstack([dNx, dNe]))
                    r = N @ xy[:,0]
                    B = np.zeros((4, 16))
                    B[0, 0::2] = dN[0]          # e_rr = du_r/dr
                    B[1, 0::2] = N / r          # e_tt = u_r/r
                    B[2, 1::2] = dN[1]          # e_zz = du_z/dz
                    B[3, 0::2] = dN[1]          # g_rz
                    B[3, 1::2] = dN[0]
                    w = wi*wj*detJ*2*np.pi*r
                    ke += w * (B.T @ self._D_at(r) @ B)
                    if rho and omega:
                        fe[0::2] += w * N * rho * omega**2 * r
            rows.append(np.repeat(dof, 16)); cols.append(np.tile(dof, 16))
            vals.append(ke.ravel())
            F[dof] += fe
        K = sp.coo_matrix((np.concatenate(vals),
                           (np.concatenate(rows), np.concatenate(cols))),
                          shape=(self.ndof, self.ndof)).tocsr()
        return K, F

    def solve(self, K, F, fixed, presc=None):
        u = np.zeros(self.ndof)
        if presc:
            for d, v in presc.items():
                u[d] = v
            F = F - K @ u
        free = np.setdiff1d(np.arange(self.ndof), fixed)
        u[free] = spla.spsolve(K[free][:, free].tocsc(), F[free])
        return u

    def stress_nodal(self, u):
        """Extrapolate-free nodal recovery: average Gauss-point stress by node."""
        co, el = self.co, self.el
        acc = np.zeros((len(co), 4)); cnt = np.zeros(len(co))
        # sample at the 8 nodal parametric positions (superconvergent enough
        # for Q8 when averaged; validated against closed form in step 5)
        pts = [(-1,-1),(1,-1),(1,1),(-1,1),(0,-1),(1,0),(0,1),(-1,0)]
        for e in el:
            xy = co[e]
            dof = np.empty(16, dtype=int); dof[0::2] = 2*e; dof[1::2] = 2*e+1
            ue = u[dof]
            for k, (gi, gj) in enumerate(pts):
                N, dNx, dNe = q8_shape(gi, gj)
                J = np.array([[dNx @ xy[:,0], dNx @ xy[:,1]],
                              [dNe @ xy[:,0], dNe @ xy[:,1]]])
                dN = np.linalg.solve(J, np.vstack([dNx, dNe]))
                r = N @ xy[:,0]
                B = np.zeros((4, 16))
                B[0,0::2] = dN[0]; B[1,0::2] = N/r
                B[2,1::2] = dN[1]; B[3,0::2] = dN[1]; B[3,1::2] = dN[0]
                acc[e[k]] += self._D_at(r) @ (B @ ue)
                cnt[e[k]] += 1
        return acc / cnt[:, None]


# ----------------------------------------------------- torsion formulation
class AxisymTorsion:
    """u_theta(r,z).  g_rt = du/dr - u/r ,  g_tz = du/dz."""

    def __init__(self, coords, elems, Grt, Gtz):
        self.co, self.el = coords, elems
        self.Grt, self.Gtz = Grt, Gtz
        self.ndof = len(coords)

    def _G(self, r):
        g1 = self.Grt(r) if callable(self.Grt) else self.Grt
        g2 = self.Gtz(r) if callable(self.Gtz) else self.Gtz
        return g1, g2

    def assemble(self):
        co, el = self.co, self.el
        rows, cols, vals = [], [], []
        for e in el:
            xy = co[e]
            ke = np.zeros((8, 8))
            for gi, wi in zip(GP, GW):
                for gj, wj in zip(GP, GW):
                    N, dNx, dNe = q8_shape(gi, gj)
                    J = np.array([[dNx @ xy[:,0], dNx @ xy[:,1]],
                                  [dNe @ xy[:,0], dNe @ xy[:,1]]])
                    detJ = np.linalg.det(J)
                    dN = np.linalg.solve(J, np.vstack([dNx, dNe]))
                    r = N @ xy[:,0]
                    Grt, Gtz = self._G(r)
                    B = np.vstack([dN[0] - N/r, dN[1]])
                    D = np.diag([Grt, Gtz])
                    ke += wi*wj*detJ*2*np.pi*r * (B.T @ D @ B)
            rows.append(np.repeat(e, 8)); cols.append(np.tile(e, 8))
            vals.append(ke.ravel())
        return sp.coo_matrix((np.concatenate(vals),
                              (np.concatenate(rows), np.concatenate(cols))),
                             shape=(self.ndof, self.ndof)).tocsr()

    def solve(self, K, F, fixed):
        u = np.zeros(self.ndof)
        free = np.setdiff1d(np.arange(self.ndof), fixed)
        u[free] = spla.spsolve(K[free][:, free].tocsc(), F[free])
        return u
