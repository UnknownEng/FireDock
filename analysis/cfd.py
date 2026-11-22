"""
CFD airflow simulation of the drone: 3D lattice-Boltzmann (D3Q19, BGK + Smagorinsky LES), numba-parallel.

Cases
  cube      solver validation: cube face-on to the flow, compare Cd with the published value (~1.05)
  hover     4 actuator discs (the props) at hover thrust push air down through the frame; the force the downwash
            puts on the arms / legs / body is the thrust lost to the airframe ("download")
  ff0       forward flight 15 m/s, level (props removed, rotating blades are not modelled)
  ff25      forward flight 15 m/s, 25 deg nose-down (typical fast cruise attitude)

Geometry is the real CAD model (cad/build.py), voxelised on a 4 mm grid. Coarse LES: results are indicative
engineering numbers (+-20-30 %), which is why the cube validation is included.

Runs on the GPUs through OpenCL (NVIDIA first, then Intel integrated, both at once, each taking the next case);
falls back to the CPU (numba, all cores) when no GPU is found.
Run:  .venv\\Scripts\\python analysis\\cfd.py              (all cases)
      .venv\\Scripts\\python analysis\\cfd.py hover ff0     (selected cases)
      .venv\\Scripts\\python analysis\\cfd.py --cpu         (also use the CPU as a third worker)
Writes output/cfd/ (run_log_*.txt shows which device ran which case).
"""
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numba as nb  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output" / "cfd"
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / "cad"))

DX = 4.0  # mm per lattice cell
RHO_AIR, NU_AIR = 1.225, 1.5e-5
CS_SMAG = 0.15
TAU_LADDER = (0.5008, 0.502, 0.506)  # fall back to more viscosity if a run goes unstable

CX = np.array([0, 1, -1, 0, 0, 0, 0, 1, -1, 1, -1, 1, -1, 1, -1, 0, 0, 0, 0], dtype=np.int64)
CY = np.array([0, 0, 0, 1, -1, 0, 0, 1, -1, -1, 1, 0, 0, 0, 0, 1, -1, 1, -1], dtype=np.int64)
CZ = np.array([0, 0, 0, 0, 0, 1, -1, 0, 0, 0, 0, 1, -1, -1, 1, 1, -1, -1, 1], dtype=np.int64)
OPP = np.array([0, 2, 1, 4, 3, 6, 5, 8, 7, 10, 9, 12, 11, 14, 13, 16, 15, 18, 17], dtype=np.int64)
W = np.array([1 / 3] + [1 / 18] * 6 + [1 / 36] * 12)
FLUID, SOLID, EQUIL, OUTFLOW = 0, 1, 2, 3


# ----------------------------------------------------------------------------- solver
@nb.njit(parallel=True, fastmath=True, cache=True)
def lbm_step(fin, fout, flag, fz, tau0, csm, ubx, uby, ubz, acc, do_acc):
    nx, ny, nz = flag.shape
    Fx = 0.0
    Fy = 0.0
    Fz = 0.0
    smag = 18.0 * math.sqrt(2.0) * csm * csm
    for i in nb.prange(nx):
        f = np.empty(19)
        feq = np.empty(19)
        for j in range(ny):
            for k in range(nz):
                fl = flag[i, j, k]
                if fl == 1:
                    continue
                if fl == 2:
                    usq = ubx * ubx + uby * uby + ubz * ubz
                    for q in range(19):
                        cu = CX[q] * ubx + CY[q] * uby + CZ[q] * ubz
                        fout[q, i, j, k] = W[q] * (1.0 + 3.0 * cu + 4.5 * cu * cu - 1.5 * usq)
                    continue
                for q in range(19):
                    si = i - CX[q]
                    sj = j - CY[q]
                    sk = k - CZ[q]
                    if si < 0:
                        si += nx
                    elif si >= nx:
                        si -= nx
                    if sj < 0:
                        sj += ny
                    elif sj >= ny:
                        sj -= ny
                    if sk < 0:
                        sk += nz
                    elif sk >= nz:
                        sk -= nz
                    if flag[si, sj, sk] == 1:          # half-way bounce-back + momentum exchange
                        v = fin[OPP[q], i, j, k]
                        Fx += -2.0 * CX[q] * (v - W[q])
                        Fy += -2.0 * CY[q] * (v - W[q])
                        Fz += -2.0 * CZ[q] * (v - W[q])
                        f[q] = v
                    else:
                        f[q] = fin[q, si, sj, sk]
                rho = 0.0
                jx = 0.0
                jy = 0.0
                jz = 0.0
                for q in range(19):
                    rho += f[q]
                    jx += CX[q] * f[q]
                    jy += CY[q] * f[q]
                    jz += CZ[q] * f[q]
                ux = jx / rho
                uy = jy / rho
                uz = jz / rho
                usq = ux * ux + uy * uy + uz * uz
                pxx = 0.0
                pyy = 0.0
                pzz = 0.0
                pxy = 0.0
                pxz = 0.0
                pyz = 0.0
                for q in range(19):
                    cu = CX[q] * ux + CY[q] * uy + CZ[q] * uz
                    feq[q] = W[q] * rho * (1.0 + 3.0 * cu + 4.5 * cu * cu - 1.5 * usq)
                    d = f[q] - feq[q]
                    pxx += CX[q] * CX[q] * d
                    pyy += CY[q] * CY[q] * d
                    pzz += CZ[q] * CZ[q] * d
                    pxy += CX[q] * CY[q] * d
                    pxz += CX[q] * CZ[q] * d
                    pyz += CY[q] * CZ[q] * d
                pin = math.sqrt(pxx * pxx + pyy * pyy + pzz * pzz + 2.0 * (pxy * pxy + pxz * pxz + pyz * pyz))
                tau = 0.5 * (tau0 + math.sqrt(tau0 * tau0 + smag * pin / rho))
                om = 1.0 / tau
                du = fz[i, j, k] / rho                 # exact-difference forcing (actuator discs)
                if du != 0.0:
                    uz2 = uz + du
                    usq2 = ux * ux + uy * uy + uz2 * uz2
                    for q in range(19):
                        cu2 = CX[q] * ux + CY[q] * uy + CZ[q] * uz2
                        feq2 = W[q] * rho * (1.0 + 3.0 * cu2 + 4.5 * cu2 * cu2 - 1.5 * usq2)
                        fout[q, i, j, k] = f[q] - om * (f[q] - feq[q]) + (feq2 - feq[q])
                else:
                    for q in range(19):
                        fout[q, i, j, k] = f[q] - om * (f[q] - feq[q])
                if do_acc:
                    acc[0, i, j, k] += ux
                    acc[1, i, j, k] += uy
                    acc[2, i, j, k] += uz + 0.5 * du
                    acc[3, i, j, k] += rho
    return Fx, Fy, Fz


def equilibrium(shape, u):
    f = np.empty((19,) + shape, dtype=np.float32)
    usq = sum(c * c for c in u)
    for q in range(19):
        cu = CX[q] * u[0] + CY[q] * u[1] + CZ[q] * u[2]
        f[q] = W[q] * (1 + 3 * cu + 4.5 * cu * cu - 1.5 * usq)
    return f


# ----------------------------------------------------------------------------- GPU (OpenCL) solver
# Same algorithm as lbm_step above, written in OpenCL C so it runs on the NVIDIA MX450 and the Intel Iris Xe.
CL_SRC = r"""
__constant int CX[19] = {0,1,-1,0,0,0,0,1,-1,1,-1,1,-1,1,-1,0,0,0,0};
__constant int CY[19] = {0,0,0,1,-1,0,0,1,-1,-1,1,0,0,0,0,1,-1,1,-1};
__constant int CZ[19] = {0,0,0,0,0,1,-1,0,0,0,0,1,-1,-1,1,1,-1,-1,1};
__constant int OPP[19] = {0,2,1,4,3,6,5,8,7,10,9,12,11,14,13,16,15,18,17};
__constant float W[19] = {1.0f/3.0f, 1.0f/18.0f,1.0f/18.0f,1.0f/18.0f,1.0f/18.0f,1.0f/18.0f,1.0f/18.0f,
    1.0f/36.0f,1.0f/36.0f,1.0f/36.0f,1.0f/36.0f,1.0f/36.0f,1.0f/36.0f,
    1.0f/36.0f,1.0f/36.0f,1.0f/36.0f,1.0f/36.0f,1.0f/36.0f,1.0f/36.0f};

__kernel void lbm_step(__global const float* fin, __global float* fout, __global const uchar* flag,
                       __global const float* fz, const float tau0, const float smag,
                       const float ubx, const float uby, const float ubz,
                       __global float* acc, __global float* facc, const int do_acc,
                       const int nx, const int ny, const int nz)
{
    const int k = get_global_id(0), j = get_global_id(1), i = get_global_id(2);
    if (k >= nz || j >= ny || i >= nx) return;
    const long N = (long)nx * ny * nz;
    const long c = ((long)i * ny + j) * nz + k;
    const uchar fl = flag[c];
    if (fl == 1) return;
    if (fl == 2) {
        const float usq = ubx*ubx + uby*uby + ubz*ubz;
        for (int q = 0; q < 19; q++) {
            const float cu = CX[q]*ubx + CY[q]*uby + CZ[q]*ubz;
            fout[q*N + c] = W[q] * (1.0f + 3.0f*cu + 4.5f*cu*cu - 1.5f*usq);
        }
        return;
    }
    float f[19];
    float Fx = 0.0f, Fy = 0.0f, Fz = 0.0f;
    for (int q = 0; q < 19; q++) {
        int si = i - CX[q], sj = j - CY[q], sk = k - CZ[q];
        if (si < 0) si += nx; else if (si >= nx) si -= nx;
        if (sj < 0) sj += ny; else if (sj >= ny) sj -= ny;
        if (sk < 0) sk += nz; else if (sk >= nz) sk -= nz;
        const long s = ((long)si * ny + sj) * nz + sk;
        if (flag[s] == 1) {                       /* half-way bounce-back + momentum exchange */
            const float v = fin[OPP[q]*N + c];
            Fx -= 2.0f*CX[q]*(v - W[q]); Fy -= 2.0f*CY[q]*(v - W[q]); Fz -= 2.0f*CZ[q]*(v - W[q]);  /* minus the resting-air pressure */
            f[q] = v;
        } else {
            f[q] = fin[q*N + s];
        }
    }
    float rho = 0.0f, jx = 0.0f, jy = 0.0f, jz = 0.0f;
    for (int q = 0; q < 19; q++) { rho += f[q]; jx += CX[q]*f[q]; jy += CY[q]*f[q]; jz += CZ[q]*f[q]; }
    const float ux = jx/rho, uy = jy/rho, uz = jz/rho;
    const float usq = ux*ux + uy*uy + uz*uz;
    float feq[19];
    float pxx = 0, pyy = 0, pzz = 0, pxy = 0, pxz = 0, pyz = 0;
    for (int q = 0; q < 19; q++) {
        const float cu = CX[q]*ux + CY[q]*uy + CZ[q]*uz;
        feq[q] = W[q]*rho*(1.0f + 3.0f*cu + 4.5f*cu*cu - 1.5f*usq);
        const float d = f[q] - feq[q];
        pxx += CX[q]*CX[q]*d; pyy += CY[q]*CY[q]*d; pzz += CZ[q]*CZ[q]*d;
        pxy += CX[q]*CY[q]*d; pxz += CX[q]*CZ[q]*d; pyz += CY[q]*CZ[q]*d;
    }
    const float pin = sqrt(pxx*pxx + pyy*pyy + pzz*pzz + 2.0f*(pxy*pxy + pxz*pxz + pyz*pyz));
    const float tau = 0.5f*(tau0 + sqrt(tau0*tau0 + smag*pin/rho));
    const float om = 1.0f/tau;
    const float du = fz[c]/rho;                  /* exact-difference forcing (actuator discs) */
    if (du != 0.0f) {
        const float uz2 = uz + du;
        const float usq2 = ux*ux + uy*uy + uz2*uz2;
        for (int q = 0; q < 19; q++) {
            const float cu2 = CX[q]*ux + CY[q]*uy + CZ[q]*uz2;
            const float feq2 = W[q]*rho*(1.0f + 3.0f*cu2 + 4.5f*cu2*cu2 - 1.5f*usq2);
            fout[q*N + c] = f[q] - om*(f[q] - feq[q]) + (feq2 - feq[q]);
        }
    } else {
        for (int q = 0; q < 19; q++) fout[q*N + c] = f[q] - om*(f[q] - feq[q]);
    }
    if (do_acc) {
        acc[c] += ux; acc[N + c] += uy; acc[2*N + c] += uz + 0.5f*du; acc[3*N + c] += rho - 1.0f;
        if (Fx != 0.0f || Fy != 0.0f || Fz != 0.0f) { facc[c] += Fx; facc[N + c] += Fy; facc[2*N + c] += Fz; }
    }
}

__kernel void copy_face(__global float* f, const int axis, const int dst, const int src,
                        const int nx, const int ny, const int nz)
{
    const int a = get_global_id(0), b = get_global_id(1);
    const long N = (long)nx * ny * nz;
    long cd, cs;
    if (axis == 0) { if (a >= nz || b >= ny) return; cd = ((long)dst*ny + b)*nz + a; cs = ((long)src*ny + b)*nz + a; }
    else if (axis == 1) { if (a >= nz || b >= nx) return; cd = ((long)b*ny + dst)*nz + a; cs = ((long)b*ny + src)*nz + a; }
    else { if (a >= ny || b >= nx) return; cd = ((long)b*ny + a)*nz + dst; cs = ((long)b*ny + a)*nz + src; }
    for (int q = 0; q < 19; q++) f[q*N + cd] = f[q*N + cs];
}
"""
DEVICE = None          # pyopencl device when running on a GPU, None = CPU (numba)


def gpu_devices():
    """OpenCL GPUs in priority order: NVIDIA first, then Intel integrated."""
    try:
        import pyopencl as cl
        devs = [d for p in cl.get_platforms() for d in p.get_devices() if d.type & cl.device_type.GPU]
    except Exception:
        return []
    rank = lambda d: 0 if "NVIDIA" in d.name.upper() else 1 if "INTEL" in d.name.upper() else 2  # noqa: E731
    return sorted(devs, key=rank)


def _up(n, m):
    return (n + m - 1) // m * m


def simulate_cl(flag, fz, u_bc, u_init, outflow, steps, avg_from, label):
    import pyopencl as cl
    ctx = cl.Context([DEVICE])
    queue = cl.CommandQueue(ctx)
    prg = cl.Program(ctx, CL_SRC).build(options=["-cl-fast-relaxed-math"])
    knl, cpf = prg.lbm_step, prg.copy_face
    nx, ny, nz = flag.shape
    N = flag.size
    i32, f32 = np.int32, np.float32
    mf = cl.mem_flags
    d_flag = cl.Buffer(ctx, mf.READ_ONLY | mf.COPY_HOST_PTR, hostbuf=np.ascontiguousarray(flag))
    d_fz = cl.Buffer(ctx, mf.READ_ONLY | mf.COPY_HOST_PTR, hostbuf=np.ascontiguousarray(fz, dtype=np.float32))
    smag = 18.0 * math.sqrt(2.0) * CS_SMAG ** 2
    gsz, lsz = (_up(nz, 32), ny, nx), (32, 1, 1)
    for tau0 in TAU_LADDER:
        t0 = time.time()
        fh = equilibrium(flag.shape, u_init)
        d_a = cl.Buffer(ctx, mf.READ_WRITE | mf.COPY_HOST_PTR, hostbuf=fh)
        del fh
        d_b = cl.Buffer(ctx, mf.READ_WRITE, size=d_a.size)
        d_acc = cl.Buffer(ctx, mf.READ_WRITE, size=4 * N * 4)
        d_facc = cl.Buffer(ctx, mf.READ_WRITE, size=3 * N * 4)
        cl.enqueue_fill_buffer(queue, d_acc, f32(0), 0, 4 * N * 4)
        cl.enqueue_fill_buffer(queue, d_facc, f32(0), 0, 3 * N * 4)
        chk = np.empty(N, dtype=np.float32)
        ok = True
        for n in range(steps):
            knl(queue, gsz, lsz, d_a, d_b, d_flag, d_fz, f32(tau0), f32(smag), f32(u_bc[0]), f32(u_bc[1]),
                f32(u_bc[2]), d_acc, d_facc, i32(n >= avg_from), i32(nx), i32(ny), i32(nz))
            for ax, dst, src in outflow:
                a_len, b_len = {0: (nz, ny), 1: (nz, nx), 2: (ny, nx)}[ax]
                cpf(queue, (_up(a_len, 32), b_len), (32, 1), d_b, i32(ax), i32(dst % flag.shape[ax]),
                    i32(src % flag.shape[ax]), i32(nx), i32(ny), i32(nz))
            d_a, d_b = d_b, d_a
            if n % 500 == 0 or n == steps - 1:
                cl.enqueue_copy(queue, chk, d_a)          # rest-population plane, to catch a blow-up
                if not np.isfinite(chk[::7]).all():
                    ok = False
                    break
                rate = N * (n + 1) / (time.time() - t0) / 1e6
                print(f"  [{label}] {DEVICE.name.strip()} tau0={tau0} step {n}/{steps}  {rate:.0f} MLUPS", flush=True)
        if ok:
            nav = steps - avg_from
            acc = np.empty((4,) + flag.shape, dtype=np.float32)
            facc = np.empty((3, N), dtype=np.float32)
            cl.enqueue_copy(queue, acc, d_acc)
            cl.enqueue_copy(queue, facc, d_facc)
            queue.finish()
            for b in (d_a, d_b, d_acc, d_facc, d_flag, d_fz):
                b.release()
            acc /= nav
            acc[3] += 1.0
            return {"tau0": tau0, "F_avg": facc.sum(axis=1, dtype=np.float64) / nav, "acc": acc,
                    "facc": facc / nav, "seconds": time.time() - t0, "device": DEVICE.name.strip()}
        for b in (d_a, d_b, d_acc, d_facc):
            b.release()
        print(f"  [{label}] unstable at tau0={tau0}, retrying with more viscosity", flush=True)
    raise RuntimeError(f"{label}: unstable at every tau0")


def simulate(flag, fz, u_bc, u_init, outflow, steps, avg_from, label):
    """outflow: list of (axis, index_dst, index_src) faces copied after every step."""
    if DEVICE is not None:
        return simulate_cl(flag, fz, u_bc, u_init, outflow, steps, avg_from, label)
    for tau0 in TAU_LADDER:
        t0 = time.time()
        fin = equilibrium(flag.shape, u_init)
        fout = np.empty_like(fin)
        acc = np.zeros((4,) + flag.shape, dtype=np.float32)
        F = np.zeros(3)
        hist = []
        ok = True
        for n in range(steps):
            do_acc = n >= avg_from
            Fx, Fy, Fz = lbm_step(fin, fout, flag, fz, tau0, CS_SMAG, *u_bc, acc, do_acc)
            for ax, dst, src in outflow:
                sl_d = [slice(None)] * 4
                sl_s = [slice(None)] * 4
                sl_d[ax + 1], sl_s[ax + 1] = dst, src
                fout[tuple(sl_d)] = fout[tuple(sl_s)]
            if do_acc:
                F += (Fx, Fy, Fz)
            hist.append((Fx, Fy, Fz))
            fin, fout = fout, fin
            if n % 500 == 0 or n == steps - 1:
                if not np.isfinite(fin[0, ::3, ::3, ::3]).all():
                    ok = False
                    break
                rate = flag.size * (n + 1) / (time.time() - t0) / 1e6
                print(f"  [{label}] tau0={tau0} step {n}/{steps}  F=({Fx:.4f},{Fy:.4f},{Fz:.4f})  {rate:.0f} MLUPS",
                      flush=True)
        if ok:
            nav = steps - avg_from
            return {"tau0": tau0, "F_avg": F / nav, "acc": acc / nav, "hist": np.array(hist),
                    "seconds": time.time() - t0, "device": "CPU (numba, 8 threads)"}
        print(f"  [{label}] unstable at tau0={tau0}, retrying with more viscosity", flush=True)
    raise RuntimeError(f"{label}: unstable at every tau0")


# ----------------------------------------------------------------------------- geometry
@nb.njit(parallel=True, cache=True)
def voxelize(tri, tb, solid, x0, y0, z0, dx, sub):
    nx, ny, nz = solid.shape
    i0 = max(int((tb[:, 0].min() - x0) / dx) - 1, 0)
    i1 = min(int((tb[:, 1].max() - x0) / dx) + 2, nx)
    j0 = max(int((tb[:, 2].min() - y0) / dx) - 1, 0)
    j1 = min(int((tb[:, 3].max() - y0) / dx) + 2, ny)
    nt = tri.shape[0]
    for i in nb.prange(i0, i1):
        zs = np.empty(1024)
        for j in range(j0, j1):
            for si in range(sub):
                px = x0 + (i + (si + 0.5) / sub) * dx + 1.37e-4
                for sj in range(sub):
                    py = y0 + (j + (sj + 0.5) / sub) * dx + 2.71e-4
                    n = 0
                    for t in range(nt):
                        if px < tb[t, 0] or px > tb[t, 1] or py < tb[t, 2] or py > tb[t, 3]:
                            continue
                        x1, y1, z1 = tri[t, 0, 0], tri[t, 0, 1], tri[t, 0, 2]
                        x2, y2, z2 = tri[t, 1, 0], tri[t, 1, 1], tri[t, 1, 2]
                        x3, y3, z3 = tri[t, 2, 0], tri[t, 2, 1], tri[t, 2, 2]
                        d = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
                        if abs(d) < 1e-12:
                            continue
                        a = ((y2 - y3) * (px - x3) + (x3 - x2) * (py - y3)) / d
                        b = ((y3 - y1) * (px - x3) + (x1 - x3) * (py - y3)) / d
                        c = 1.0 - a - b
                        if a >= 0.0 and b >= 0.0 and c >= 0.0 and n < 1024:
                            zs[n] = a * z1 + b * z2 + c * z3
                            n += 1
                    if n < 2 or n % 2 == 1:
                        continue
                    zz = np.sort(zs[:n])
                    for p in range(0, n, 2):
                        za = zz[p]
                        zb = zz[p + 1]
                        th = min(0.3 * dx, 0.9 * (zb - za))
                        k0 = max(int((za - z0) / dx), 0)
                        k1 = min(int((zb - z0) / dx) + 1, nz)
                        for k in range(k0, k1):
                            lo = z0 + k * dx
                            ov = min(lo + dx, zb) - max(lo, za)
                            if ov >= th:
                                solid[i, j, k] = 1


def drone_triangles(transform=None):
    """Tessellated solids of the drone (no prop discs), each as an (n,3,3) array in mm."""
    import build
    S = build.build_shapes()
    out = []
    for name, shp, loc, _, _ in build.drone_items(S):
        if name.startswith("REF_prop"):
            continue
        v, f = shp.moved(loc).tessellate(0.2, 0.3)
        v = np.array([[p.x, p.y, p.z] for p in v])
        if transform is not None:
            v = transform(v)
        out.append((name, v[np.array(f)]))
    return out, build


def grid_for(tris, margins):
    allv = np.concatenate([t.reshape(-1, 3) for _, t in tris])
    lo, hi = allv.min(0), allv.max(0)
    (mx0, mx1), (my0, my1), (mz0, mz1) = margins
    origin = np.array([lo[0] - mx0, lo[1] - my0, lo[2] - mz0])
    n = np.ceil((np.array([hi[0] + mx1, hi[1] + my1, hi[2] + mz1]) - origin) / DX).astype(int)
    return origin, tuple(int(x) for x in n), lo, hi


def solid_mask(tris, origin, shape):
    solid = np.zeros(shape, dtype=np.uint8)
    for _, t in tris:
        tb = np.stack([t[:, :, 0].min(1), t[:, :, 0].max(1), t[:, :, 1].min(1), t[:, :, 1].max(1)], axis=1)
        voxelize(np.ascontiguousarray(t), tb, solid, origin[0], origin[1], origin[2], DX, 2)
    return solid


def write_vtk(path, origin, acc, solid, step=2):
    """Legacy binary VTK structured points (ParaView), every `step`-th cell."""
    u = acc[:3, ::step, ::step, ::step]
    rho = acc[3, ::step, ::step, ::step]
    s = solid[::step, ::step, ::step]
    nx, ny, nz = s.shape
    with open(path, "wb") as fh:
        hdr = (f"# vtk DataFile Version 3.0\nDocker Drone CFD (velocity in lattice units)\nBINARY\n"
               f"DATASET STRUCTURED_POINTS\nDIMENSIONS {nx} {ny} {nz}\n"
               f"ORIGIN {origin[0] + DX / 2:.3f} {origin[1] + DX / 2:.3f} {origin[2] + DX / 2:.3f}\n"
               f"SPACING {DX * step} {DX * step} {DX * step}\nPOINT_DATA {nx * ny * nz}\n")
        fh.write(hdr.encode())
        fh.write(b"VECTORS velocity float\n")
        fh.write(np.ascontiguousarray(np.moveaxis(u, 0, -1).transpose(2, 1, 0, 3)).astype(">f4").tobytes())
        fh.write(b"\nSCALARS density float 1\nLOOKUP_TABLE default\n")
        fh.write(np.ascontiguousarray(rho.transpose(2, 1, 0)).astype(">f4").tobytes())
        fh.write(b"\nSCALARS solid float 1\nLOOKUP_TABLE default\n")
        fh.write(np.ascontiguousarray(s.transpose(2, 1, 0)).astype(">f4").tobytes())
        fh.write(b"\n")


# ----------------------------------------------------------------------------- plotting
SOLID_CMAP = ListedColormap(["#3a3a40"])


def slice_plot(ax, field, solid2d, ext, cmap, vmin, vmax, uv=None, title="", label=""):
    im = ax.imshow(field.T, origin="lower", extent=ext, cmap=cmap, vmin=vmin, vmax=vmax, interpolation="bilinear")
    ax.imshow(np.ma.masked_where(solid2d.T == 0, solid2d.T), origin="lower", extent=ext, cmap=SOLID_CMAP,
              interpolation="nearest")
    if uv is not None:
        xs = np.linspace(ext[0], ext[1], field.shape[0])
        ys = np.linspace(ext[2], ext[3], field.shape[1])
        U, V = (np.where(solid2d, 0, c).T for c in uv)
        ax.streamplot(xs, ys, U, V, density=1.4, color=(1, 1, 1, 0.55), linewidth=0.5, arrowsize=0.6)
    ax.set_title(title, fontsize=10)
    ax.set_xlabel("mm")
    ax.set_ylabel("mm")
    plt.colorbar(im, ax=ax, shrink=0.8, label=label)


# ----------------------------------------------------------------------------- cases
def case_cube():
    side, U = 20, 0.08
    shape = (200, 100, 100)
    flag = np.zeros(shape, dtype=np.uint8)
    flag[50:50 + side, 40:40 + side, 40:40 + side] = SOLID
    solid = flag.copy()
    flag[0] = EQUIL
    flag[-1] = OUTFLOW
    fz = np.zeros(shape, dtype=np.float32)
    r = simulate(flag, fz, (U, 0.0, 0.0), (U, 0, 0), [(0, -1, -2)], 7000, 4000, "cube")
    cd = r["F_avg"][0] / (0.5 * U * U * side * side)
    res = {"Cd": round(float(cd), 3), "reference_Cd": 1.05, "reference": "Hoerner, Fluid-Dynamic Drag (cube face-on)",
           "cells_per_side": side, "blockage_pct": round(100 * side * side / (shape[1] * shape[2]), 1),
           "tau0": r["tau0"], "error_pct": round(100 * (cd - 1.05) / 1.05, 1), "seconds": round(r["seconds"]), "device": r["device"]}
    acc = r["acc"]
    fig, ax = plt.subplots(figsize=(10, 4.6), dpi=120)
    k = 50
    spd = np.hypot(acc[0, :, :, k], acc[1, :, :, k]) / U
    slice_plot(ax, spd, solid[:, :, k], (0, shape[0] * DX, 0, shape[1] * DX), "viridis", 0, 1.5,
               (acc[0, :, :, k], acc[1, :, :, k]), f"Solver check: cube, Cd = {cd:.2f} (published ~1.05)", "speed / U")
    fig.savefig(OUT / "cfd_validation_cube.png", facecolor="white", bbox_inches="tight")
    plt.close(fig)
    return res


def case_hover():
    tris, build = drone_triangles()
    origin, shape, lo, hi = grid_for(tris, ((190, 190), (190, 190), (420, 200)))  # discs reach 71 mm past the motors
    solid = solid_mask(tris, origin, shape)
    flag = solid.copy()
    for sl in (np.s_[0], np.s_[-1], np.s_[:, 0], np.s_[:, -1], np.s_[:, :, -1]):
        flag[sl] = EQUIL
    flag[:, :, 0] = OUTFLOW
    flag[solid == 1] = SOLID

    # unit scales: 10 m/s <-> 0.06 lattice
    u_ref = 0.06
    dt = u_ref * DX / 1000 / 10.0
    f_scale = RHO_AIR * (DX / 1000) ** 4 / dt ** 2          # N per lattice force unit
    auw_g = json.loads((ROOT / "output" / "report" / "analysis.json").read_text())["results"]["performance"]["AUW_g"]
    T_motor = auw_g / 1000 * 9.81 / 4
    F_lat = T_motor / f_scale
    zp = build.Z_MID + build.P["motor_h"] + 3.0
    r_hub, r_tip = build.P["motor_d"] / 2 + 0.5, build.P["prop_d"] / 2
    xc = origin[0] + (np.arange(shape[0]) + 0.5) * DX
    yc = origin[1] + (np.arange(shape[1]) + 0.5) * DX
    zc = origin[2] + (np.arange(shape[2]) + 0.5) * DX
    X, Y = np.meshgrid(xc, yc, indexing="ij")
    kz = np.where(np.abs(zc - zp) <= DX * 0.75)[0]
    fz = np.zeros(shape, dtype=np.float32)
    discs = []
    for a in build.ARM_ANGLES:
        mx, my = build.R * math.cos(math.radians(a)), build.R * math.sin(math.radians(a))
        rr = np.hypot(X - mx, Y - my)
        ann = (rr >= r_hub) & (rr <= r_tip)
        m3 = np.zeros(shape, dtype=bool)
        m3[:, :, kz] = ann[:, :, None]
        m3 &= flag == FLUID
        fz[m3] -= F_lat / m3.sum()                            # air pushed down
        discs.append((mx, my, ann))
    print(f"  hover grid {shape} = {np.prod(shape) / 1e6:.1f} M cells, thrust/motor {T_motor:.2f} N "
          f"= {F_lat:.3f} lattice", flush=True)
    r = simulate(flag, fz, (0.0, 0.0, 0.0), (0, 0, 0), [(2, 0, 1)], 9000, 5000, "hover")
    F = r["F_avg"] * f_scale
    acc = r["acc"]
    download = -F[2]
    total_T = 4 * T_motor
    # induced velocity in the disc plane vs momentum theory
    vi = []
    for mx, my, ann in discs:
        vi.append(-acc[2][:, :, kz].mean(axis=2)[ann].mean() / u_ref * 10.0)
    A = math.pi * (r_tip / 1000) ** 2
    vi_theory = math.sqrt(T_motor / (2 * RHO_AIR * A))
    res = {"thrust_per_motor_N": round(T_motor, 2), "download_on_airframe_N": round(download, 3),
           "download_pct_of_thrust": round(100 * download / total_T, 2),
           "flight_time_loss_pct": round(100 * (1 - (1 + download / total_T) ** -1.5), 1),
           "side_force_N": [round(F[0], 3), round(F[1], 3)],
           "induced_velocity_mps": round(float(np.mean(vi)), 2), "momentum_theory_induced_velocity_mps": round(vi_theory, 2),
           "grid": list(shape), "cell_mm": DX, "tau0": r["tau0"], "seconds": round(r["seconds"]), "device": r["device"]}

    # plots: diagonal slice through two motors, horizontal slice between props and arms
    ux, uy, uz = (acc[c] / u_ref * 10.0 for c in range(3))
    i0 = int(round((0 - origin[0]) / DX - 0.5))
    j0 = int(round((0 - origin[1]) / DX - 0.5))
    n = np.arange(-min(i0, j0, shape[0] - i0 - 1, shape[1] - j0 - 1), min(shape[0] - i0, shape[1] - j0))
    di, dj = i0 + n, j0 + n
    s_mm = n * DX * math.sqrt(2)
    uzd = uz[di, dj, :]
    usd = (ux[di, dj, :] + uy[di, dj, :]) / math.sqrt(2)
    sold = solid[di, dj, :]
    fig, axs = plt.subplots(1, 2, figsize=(15, 6.2), dpi=120)
    ext = (s_mm[0], s_mm[-1], zc[0], zc[-1])
    slice_plot(axs[0], -uzd, sold, ext, "inferno", 0, 16, (usd, uzd),
               "Hover downwash, slice through two motors (diagonal)", "downwash speed [m/s]")
    axs[0].axhline(zp, color="c", lw=0.6, ls="--")
    k = int(np.argmin(np.abs(zc + 10.0)))
    slice_plot(axs[1], -uz[:, :, k], solid[:, :, k], (xc[0], xc[-1], yc[0], yc[-1]), "inferno", 0, 16, None,
               "Downwash 10 mm under the frame (top view): the arms' wakes are the dark bands", "downwash speed [m/s]")
    fig.suptitle(f"Hover CFD: {download:.2f} N of the {total_T:.1f} N thrust lands on the airframe "
                 f"({res['download_pct_of_thrust']} %)", fontsize=12)
    fig.savefig(OUT / "cfd_hover_downwash.png", facecolor="white", bbox_inches="tight")
    plt.close(fig)
    write_vtk(OUT / "cfd_hover_half_res.vtk", origin, acc, solid)
    return res


def case_dock_takeoff():
    """Drone hovering with its feet 300 mm above the OPEN dock (covers flipped down, pushers parked), ground below.
    Shows where the prop wash goes and the force it puts on the drone, the dock and the ground. 8 mm cells."""
    global DX
    dx_saved, DX = DX, 8.0
    try:
        import build
        S = build.build_shapes()
        lift = build.L(build.V(0, 0, 300.0)) * build.drone_in_dock_location()
        bodies = {"drone": [(n, s, lift * loc) for n, s, loc, _, _ in build.drone_items(S) if not n.startswith("REF_prop")],
                  "dock": [(n, s, loc) for n, s, loc, _, _ in build.dock_items(S, "open")]}
        origin = np.array([-1000.0, -700.0, 0.0])
        shape = (250, 175, 140)
        label = np.zeros(shape, dtype=np.uint8)
        for lab, items in ((2, bodies["dock"]), (3, bodies["drone"])):
            for _, s, loc in items:
                v, f = s.moved(loc).tessellate(0.5, 0.4)
                t = np.array([[p.x, p.y, p.z] for p in v])[np.array(f)]
                m = np.zeros(shape, dtype=np.uint8)
                tb = np.stack([t[:, :, 0].min(1), t[:, :, 0].max(1), t[:, :, 1].min(1), t[:, :, 1].max(1)], axis=1)
                voxelize(np.ascontiguousarray(t), tb, m, origin[0], origin[1], origin[2], DX, 2)
                label[m == 1] = lab
        label[:, :, 0] = 1                                     # ground
        solid = (label > 0).astype(np.uint8)
        flag = solid.copy()
        for sl in (np.s_[0], np.s_[-1], np.s_[:, 0], np.s_[:, -1], np.s_[:, :, -1]):
            flag[sl] = EQUIL
        flag[solid == 1] = SOLID

        u_ref = 0.06
        dt = u_ref * DX / 1000 / 10.0
        f_scale = RHO_AIR * (DX / 1000) ** 4 / dt ** 2
        auw_g = json.loads((ROOT / "output" / "report" / "analysis.json").read_text())["results"]["performance"]["AUW_g"]
        T_motor = auw_g / 1000 * 9.81 / 4
        F_lat = T_motor / f_scale
        z_drone = 300.0 + build.DK.Z_DECK - build.LEG_BOTTOM
        zp = z_drone + build.Z_MID + build.P["motor_h"] + 3.0
        xc = origin[0] + (np.arange(shape[0]) + 0.5) * DX
        yc = origin[1] + (np.arange(shape[1]) + 0.5) * DX
        zc = origin[2] + (np.arange(shape[2]) + 0.5) * DX
        X, Y = np.meshgrid(xc, yc, indexing="ij")
        kz = int(np.argmin(np.abs(zc - zp)))
        fz = np.zeros(shape, dtype=np.float32)
        for a in build.ARM_ANGLES:
            mx, my = build.R * math.cos(math.radians(a)), build.R * math.sin(math.radians(a))
            rr = np.hypot(X - mx, Y - my)
            ann = (rr >= build.P["motor_d"] / 2 + 0.5) & (rr <= build.P["prop_d"] / 2) & (flag[:, :, kz] == FLUID)
            fz[:, :, kz][ann] -= F_lat / ann.sum()
        print(f"  dock_takeoff grid {shape} = {np.prod(shape) / 1e6:.1f} M cells at {DX} mm", flush=True)
        r = simulate(flag, fz, (0.0, 0.0, 0.0), (0, 0, 0), [], 7000, 4000, "dock_takeoff")
        acc = r["acc"]
        F_tot = r["F_avg"] * f_scale
        res = {"drone_feet_above_deck_mm": 300.0, "thrust_total_N": round(4 * T_motor, 2),
               "force_on_all_solids_N": [round(float(v), 3) for v in F_tot],
               "grid": list(shape), "cell_mm": DX, "tau0": r["tau0"], "seconds": round(r["seconds"]), "device": r["device"]}
        if "facc" in r:                                          # split the force by body (GPU path keeps it per cell)
            from scipy.ndimage import maximum_filter
            near = maximum_filter(label, size=3).reshape(-1)
            fa = r["facc"] * f_scale
            for lab, name in ((1, "ground"), (2, "dock"), (3, "drone")):
                res[f"downward_force_on_{name}_N"] = round(float(-fa[2][near == lab].sum()), 3)
            res["drone_download_pct_of_thrust"] = round(100 * res["downward_force_on_drone_N"] / (4 * T_motor), 2)
        # wash speed just above the deck
        kd = int(np.argmin(np.abs(zc - (build.DK.Z_DECK + 40))))
        uh = np.hypot(acc[0, :, :, kd], acc[1, :, :, kd]) / u_ref * 10.0
        res["max_wash_speed_40mm_above_deck_mps"] = round(float(np.where(solid[:, :, kd], 0, uh).max()), 1)

        ux, uz = acc[0] / u_ref * 10.0, acc[2] / u_ref * 10.0
        j = int(np.argmin(np.abs(yc)))
        spd = np.hypot(ux[:, j, :], uz[:, j, :])
        fig, axs = plt.subplots(1, 2, figsize=(16, 6.4), dpi=120)
        slice_plot(axs[0], spd, solid[:, j, :], (xc[0], xc[-1], zc[0], zc[-1]), "magma", 0, 14,
                   (ux[:, j, :], uz[:, j, :]), "Side view through the centre: air speed and flow lines", "air speed [m/s]")
        slice_plot(axs[1], np.where(solid[:, :, kd], np.nan, uh), solid[:, :, kd], (xc[0], xc[-1], yc[0], yc[-1]),
                   "magma", 0, 10, (acc[0, :, :, kd], acc[1, :, :, kd]), "Top view 40 mm above the deck: wash spreading out",
                   "air speed [m/s]")
        fig.suptitle("Take-off from the open dock (feet 300 mm above the deck): the prop wash hits the flat deck and "
                     "spreads out - nothing around the props", fontsize=11.5)
        fig.savefig(OUT / "cfd_dock_takeoff.png", facecolor="white", bbox_inches="tight")
        plt.close(fig)
        write_vtk(OUT / "cfd_dock_takeoff_half_res.vtk", origin, acc, solid)
        return res
    finally:
        DX = dx_saved


def case_forward(pitch_deg):
    U_ms, U = 15.0, 0.08
    th = math.radians(pitch_deg)

    def tf(v):
        x, y, z = -v[:, 0], -v[:, 1], v[:, 2]                  # nose faces the inlet (-x)
        return np.stack([x * math.cos(th) - z * math.sin(th), y, x * math.sin(th) + z * math.cos(th)], axis=1)

    tris, build = drone_triangles(tf)
    origin, shape, lo, hi = grid_for(tris, ((250, 600), (140, 140), (130, 130)))
    solid = solid_mask(tris, origin, shape)
    flag = solid.copy()
    flag[0] = EQUIL
    flag[-1] = OUTFLOW
    flag[solid == 1] = SOLID
    fz = np.zeros(shape, dtype=np.float32)
    print(f"  ff{pitch_deg} grid {shape} = {np.prod(shape) / 1e6:.1f} M cells", flush=True)
    r = simulate(flag, fz, (U, 0.0, 0.0), (U, 0, 0), [(0, -1, -2)], 9000, 5500, f"ff{pitch_deg}")
    dt = U * DX / 1000 / U_ms
    f_scale = RHO_AIR * (DX / 1000) ** 4 / dt ** 2
    F = r["F_avg"] * f_scale
    q = 0.5 * RHO_AIR * U_ms ** 2
    frontal = (solid.max(axis=0).sum()) * (DX / 1000) ** 2
    res = {"speed_mps": U_ms, "pitch_deg": pitch_deg, "drag_N": round(F[0], 3), "vertical_force_N": round(F[2], 3),
           "CdA_m2": round(F[0] / q, 5), "frontal_area_m2": round(frontal, 5), "Cd_on_frontal_area": round(F[0] / q / frontal, 2),
           "drag_power_W": round(F[0] * U_ms, 1), "drag_at_20mps_N": round(F[0] * (20 / U_ms) ** 2, 2),
           "grid": list(shape), "cell_mm": DX, "tau0": r["tau0"], "seconds": round(r["seconds"]), "device": r["device"]}

    acc = r["acc"]
    xc = origin[0] + (np.arange(shape[0]) + 0.5) * DX
    yc = origin[1] + (np.arange(shape[1]) + 0.5) * DX
    zc = origin[2] + (np.arange(shape[2]) + 0.5) * DX
    j = int(np.argmin(np.abs(yc)))
    spd = np.sqrt(acc[0, :, j, :] ** 2 + acc[2, :, j, :] ** 2) / U * U_ms
    cp = (acc[3, :, j, :] - 1.0) / 3.0 / (0.5 * U * U)
    fig, axs = plt.subplots(2, 1, figsize=(13, 9), dpi=120)
    ext = (xc[0], xc[-1], zc[0], zc[-1])
    slice_plot(axs[0], spd, solid[:, j, :], ext, "viridis", 0, 1.5 * U_ms, (acc[0, :, j, :], acc[2, :, j, :]),
               f"Side view, centre line: air speed (flow left to right, nose on the left)", "air speed [m/s]")
    slice_plot(axs[1], cp, solid[:, j, :], ext, "coolwarm", -1.2, 1.2, None, "Pressure coefficient Cp", "Cp")
    for ax in axs:
        ax.set_xlim(lo[0] - 150, hi[0] + 450)
    fig.suptitle(f"Forward flight {U_ms:.0f} m/s, {pitch_deg} deg nose-down: drag {F[0]:.2f} N, "
                 f"CdA {F[0] / q * 1e4:.0f} cm2", fontsize=12)
    fig.savefig(OUT / f"cfd_forward_{pitch_deg}deg.png", facecolor="white", bbox_inches="tight")
    plt.close(fig)
    if pitch_deg == 0:
        k = int(np.argmin(np.abs(zc - 6.0)))
        fig, ax = plt.subplots(figsize=(13, 6), dpi=120)
        spd = np.hypot(acc[0, :, :, k], acc[1, :, :, k]) / U * U_ms
        slice_plot(ax, spd, solid[:, :, k], (xc[0], xc[-1], yc[0], yc[-1]), "viridis", 0, 1.5 * U_ms,
                   (acc[0, :, :, k], acc[1, :, :, k]), "Top view at arm height: air speed", "air speed [m/s]")
        ax.set_xlim(lo[0] - 150, hi[0] + 450)
        fig.savefig(OUT / "cfd_forward_0deg_top.png", facecolor="white", bbox_inches="tight")
        plt.close(fig)
    write_vtk(OUT / f"cfd_forward_{pitch_deg}deg_half_res.vtk", origin, acc, solid)
    return res


def report(R):
    lines = ["# CFD airflow simulation", "",
             "Generated by `analysis/cfd.py`: 3D lattice-Boltzmann (D3Q19, BGK + Smagorinsky LES) on the real CAD geometry,",
             f"voxelised at {DX:.0f} mm. Coarse LES gives indicative numbers (about ±20-30 %), so the solver is first checked",
             "on a cube with a known drag coefficient.", ""]
    if "cube" in R:
        c = R["cube"]
        lines += ["## Solver check: cube", f"Cd = **{c['Cd']}** vs published {c['reference_Cd']} ({c['reference']}), "
                  f"error {c['error_pct']} %. ![cube](cfd_validation_cube.png)", ""]
    if "hover" in R:
        h = R["hover"]
        lines += ["## Hover: prop downwash on the frame",
                  "Each prop is an actuator disc carrying a quarter of the all-up weight. The downwash pushes on the arms, legs and",
                  "body; that force is thrust the motors make but the drone does not get.", "",
                  "| | |", "|---|---|",
                  f"| Thrust per motor | {h['thrust_per_motor_N']} N |",
                  f"| Download on the airframe | **{h['download_on_airframe_N']} N = {h['download_pct_of_thrust']} % of thrust** |",
                  f"| Effect on hover time | about −{h['flight_time_loss_pct']} % |",
                  f"| Induced velocity in the disc (CFD / momentum theory) | {h['induced_velocity_mps']} / "
                  f"{h['momentum_theory_induced_velocity_mps']} m/s |", "",
                  "Typical quads lose 3–10 % this way. The 4 mm grid draws the arms and legs slightly wider and thicker",
                  "than they are, so this is a conservative (high) estimate. ![hover](cfd_hover_downwash.png)", ""]
    ff = [R[k] for k in ("ff0", "ff25") if k in R]
    if ff:
        lines += ["## Forward flight at 15 m/s (props removed)", "| Attitude | Drag | CdA | Vertical force | Drag power |",
                  "|---|---|---|---|---|"]
        for f in ff:
            lines.append(f"| {'level' if f['pitch_deg'] == 0 else str(f['pitch_deg']) + '° nose-down'} | **{f['drag_N']} N** | {f['CdA_m2'] * 1e4:.0f} cm² | "
                         f"{f['vertical_force_N']} N | {f['drag_power_W']} W |")
        lines += ["", "Drag grows with speed squared (at 20 m/s: " +
                  ", ".join(f"{f['drag_at_20mps_N']} N at {f['pitch_deg']}°" for f in ff) + ").", ""]
        lines += [f"![ff{f['pitch_deg']}](cfd_forward_{f['pitch_deg']}deg.png)" for f in ff] + [""]
    if "dock_takeoff" in R:
        d = R["dock_takeoff"]
        lines += ["## Take-off from the open dock",
                  f"Drone hovering with its feet {d['drone_feet_above_deck_mm']:.0f} mm above the deck, covers flipped down, "
                  f"pushers parked, ground below ({d['cell_mm']:.0f} mm cells).", "",
                  "| | |", "|---|---|",
                  f"| Total thrust | {d['thrust_total_N']} N |"]
        for k in ("drone", "dock", "ground"):
            if f"downward_force_on_{k}_N" in d:
                lines.append(f"| Downward wash force on the {k} | {d[f'downward_force_on_{k}_N']} N |")
        if "drone_download_pct_of_thrust" in d:
            lines.append(f"| Download on the drone near the deck | {d['drone_download_pct_of_thrust']} % of thrust |")
        lines += [f"| Fastest wash 40 mm above the deck | {d['max_wash_speed_40mm_above_deck_mps']} m/s |", "",
                  "The wash hits the flat deck and spreads outward over the edges and the open covers; there are no walls",
                  "to trap it and blow it back into the props. ![dock take-off](cfd_dock_takeoff.png)", ""]
    lines += ["## Where each case ran"] + [f"* {k}: {v.get('device', 'CPU')}, {v['seconds'] / 60:.1f} min"
                                          for k, v in R.items()] + [""]
    lines += ["## Files", "* `*_half_res.vtk`: time-averaged velocity, density and solid mask (every 2nd cell) for ParaView",
              "* `cfd_results.json`: all numbers", "",
              "## Limits", "* 4 mm cells: plates and arms are a few cells thick, so small details are smoothed.",
              "* Props are actuator discs (no blades, no swirl); in forward flight the props are left out.",
              "* Free air only: ground effect and the dock walls during take-off are not included.",
              "* Velocity is time-averaged over the last part of each run."]
    (OUT / "cfd_report.md").write_text("\n".join(lines), encoding="utf-8")


CASE_ORDER = ["dock_takeoff", "ff25", "ff0", "hover", "cube"]   # biggest first, so the GPUs finish together


def run_case(c):
    if c == "cube":
        return case_cube()
    if c == "hover":
        return case_hover()
    if c == "dock_takeoff":
        return case_dock_takeoff()
    return case_forward(int(c[2:]))


def merged():
    R = {}
    for c in ("cube", "hover", "ff0", "ff25", "dock_takeoff"):
        p = OUT / f"cfd_{c}.json"
        if p.exists():
            R[c] = json.loads(p.read_text())
    return R


def worker(slot, cases):
    """Run cases on one device; each case is claimed with an exclusive file so two devices never run the same one."""
    global DEVICE
    devs = gpu_devices()
    DEVICE = devs[slot] if slot is not None and slot < len(devs) else None
    for c in cases:
        try:
            os.close(os.open(OUT / f".claim_{c}", os.O_CREAT | os.O_EXCL | os.O_WRONLY))
        except FileExistsError:
            continue
        print(f"=== {c} on {DEVICE.name.strip() if DEVICE is not None else 'CPU'}", flush=True)
        res = run_case(c)
        (OUT / f"cfd_{c}.json").write_text(json.dumps(res, indent=2))
        print(json.dumps(res, indent=2), flush=True)


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["worker"]:
        worker(None if args[1] == "cpu" else int(args[1]), args[2:])
        sys.exit()
    use_cpu = "--cpu" in args
    cases = [a for a in args if not a.startswith("--")] or CASE_ORDER
    for p in OUT.glob(".claim_*"):
        p.unlink()
    devs = gpu_devices()
    print("GPUs in priority order:", [d.name.strip() for d in devs] or "none")
    slots = [str(i) for i in range(len(devs))] + (["cpu"] if use_cpu or not devs else [])
    procs = []
    for slot in slots:
        log = open(OUT / f"run_log_{'gpu' + slot if slot != 'cpu' else 'cpu'}.txt", "w")
        procs.append(subprocess.Popen([sys.executable, "-u", __file__, "worker", slot, *cases],
                                      stdout=log, stderr=subprocess.STDOUT))
        time.sleep(5)      # the higher-priority device claims the biggest case first
    for p in procs:
        p.wait()
    for p in OUT.glob(".claim_*"):
        p.unlink()
    R = merged()
    (OUT / "cfd_results.json").write_text(json.dumps(R, indent=2))
    report(R)
    print(json.dumps(R, indent=2))
