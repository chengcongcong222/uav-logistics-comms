"""Safe necessary geometry and sortie-specific sampling for E5.2.

The search is incomplete; accepted candidates receive dense numerical checks.
No changes to the frozen DEM occlusion or propagation model are made here.
"""
from __future__ import annotations

import numpy as np
from scipy.spatial.distance import pdist


def safe_bbox(points, d_tr, d_rg, gateway):
    p = np.asarray(points, dtype=float)[:, :3]
    low = np.maximum(p[:, :2].max(axis=0) - d_tr, np.asarray(gateway[:2]) - d_rg)
    high = np.minimum(p[:, :2].min(axis=0) + d_tr, np.asarray(gateway[:2]) + d_rg)
    if np.any(low > high):
        return None
    return float(low[0]), float(high[0]), float(low[1]), float(high[1])


def diameter_infeasible(points, d_tr):
    """Pairwise condition is cheap on phase vertices, not literally zero cost."""
    p = np.asarray(points, dtype=float)[:, :3]
    return len(p) > 1 and bool(np.any(pdist(p) > 2 * d_tr))


class SortieTrajectory:
    def __init__(self, frame, pareto_id, sortie_id):
        self.key = (str(pareto_id), str(sortie_id))
        f = frame[frame.task_id == sortie_id].sort_values('time')
        if f.empty:
            raise ValueError(f'Unknown sortie {self.key}')
        if (f.groupby('time')[['x', 'y', 'z']].nunique() > 1).any().any():
            raise ValueError(f'Conflicting phase endpoints {self.key}')
        f = f.drop_duplicates('time')
        self.times = f.time.to_numpy(float)
        self.xyz = f[['x', 'y', 'z']].to_numpy(float)

    def position(self, times):
        ts = np.atleast_1d(times).astype(float)
        if ts.min() < self.times[0] - 1e-7 or ts.max() > self.times[-1] + 1e-7:
            raise ValueError(f'Extrapolation forbidden {self.key}')
        return np.column_stack([np.interp(ts, self.times, self.xyz[:, i]) for i in range(3)])

    def vertices(self, start, end):
        if not end > start:
            raise ValueError('Nonpositive interval')
        return np.unique(np.r_[start, self.times[(self.times > start) & (self.times < end)], end])

    def sample_times(self, start, end, step=0.5):
        # Global lattice permits exact cache reuse after splitting; add all boundaries.
        lattice = np.arange(np.ceil(start / step), np.floor(end / step) + 1) * step
        return np.unique(np.r_[self.vertices(start, end), lattice])


def partition_interval(trajectory, start, end, max_duration=30.0):
    boundaries = trajectory.vertices(start, end)
    out = []
    for a, b in zip(boundaries[:-1], boundaries[1:]):
        n = max(1, int(np.ceil((b - a) / max_duration)))
        edges = np.linspace(a, b, n + 1)
        out.extend((float(x), float(y)) for x, y in zip(edges[:-1], edges[1:]))
    return out
