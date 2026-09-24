#!/usr/bin/env python3
"""Targeted regressions for failures identified during the E52 takeover."""
from collections import Counter
from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from src.q3.e52_geometry import SortieTrajectory, safe_bbox, diameter_infeasible, partition_interval
from src.q3.e52_lazy import Engine, fingerprint


def trace():
    return pd.DataFrame([
        ['A',0,0,0,10],['A',0.25,2,0,10],['A',1,8,0,10],['A',31.2,8,0,10],
        ['B',0,100,100,300],['B',31.2,100,100,300],
    ],columns=['task_id','time','x','y','z'])


class RegressionTests(unittest.TestCase):
    def test_intersection_box_and_empty_domain(self):
        self.assertEqual(safe_bbox([[0,0,0],[6,4,0]],5,100,[0,0,0]),(1.,5.,-1.,5.))
        self.assertIsNone(safe_bbox([[0,0,0],[11,0,0]],5,100,[0,0,0]))

    def test_necessary_box_never_discards_known_feasible_site(self):
        rng=np.random.default_rng(20260924)
        for _ in range(100):
            relay=rng.normal(size=3)*20
            offsets=rng.normal(size=(10,3));offsets/=np.linalg.norm(offsets,axis=1)[:,None]
            points=relay+offsets*rng.uniform(0,5,size=(10,1))
            box=safe_bbox(points,5,1000,[0,0,0])
            self.assertIsNotNone(box)
            self.assertTrue(box[0]<=relay[0]<=box[1] and box[2]<=relay[1]<=box[3])

    def test_three_dimensional_diameter(self):
        self.assertTrue(diameter_infeasible([[0,0,0],[0,0,11]],5))
        self.assertFalse(diameter_infeasible([[0,0,0],[0,0,10]],5))

    def test_sortie_isolation_and_boundary_support(self):
        t=SortieTrajectory(trace(),'P01','A')
        np.testing.assert_allclose(t.position([0.125,0.5]),[[1,0,10],[4,0,10]])
        ts=t.sample_times(0.125,0.875)
        self.assertIn(0.125,ts);self.assertIn(0.875,ts);self.assertIn(0.25,ts)
        self.assertLessEqual(max(np.diff(ts)),0.5)
        with self.assertRaises(ValueError):t.position([-0.1])

    def test_conflicting_phase_endpoints_rejected(self):
        f=pd.concat([trace(),pd.DataFrame([['A',0,99,0,10]],columns=trace().columns)])
        with self.assertRaises(ValueError):SortieTrajectory(f,'P01','A')

    def test_partition_covers_endpoints_and_phase_boundaries(self):
        t=SortieTrajectory(trace(),'P01','A')
        intervals=partition_interval(t,0,31.2)
        self.assertEqual(intervals[0][0],0);self.assertEqual(intervals[-1][1],31.2)
        self.assertTrue(all(0<b-a<=30 for a,b in intervals))
        self.assertTrue(all(x[1]==y[0] for x,y in zip(intervals[:-1],intervals[1:])))

    def test_dense_check_rejects_phase_boundary_outage(self):
        engine=Engine.__new__(Engine);engine.stats=Counter()
        engine.access=lambda traj,site,t: (-1 if t==0.25 else 1,False)
        self.assertIsNone(engine.exact(SortieTrajectory(trace(),'P01','A'),{},0,1))

    def test_refinement_catches_outage_near_los_transition(self):
        engine=Engine.__new__(Engine);engine.stats=Counter()
        engine.access=lambda traj,site,t: (-1 if 0.1<t<0.2 else 1,t>=0.1)
        t=SortieTrajectory(trace().query('time != 0.25'),'P01','A')
        self.assertIsNone(engine.exact(t,{},0,1))

    def test_cache_identity_and_static_reuse(self):
        e=Engine();site=next(iter(e.sites.values()))
        a=e.trajectories['P01','M001'];b=e.trajectories['P02','M001']
        e.access(a,site,900.);e.access(a,site,900.);e.access(b,site,900.)
        self.assertEqual(e.stats['access_los_calls'],2)
        self.assertEqual(e.stats['access_cache_hits'],1)
        e.backhaul(site);e.backhaul(site)
        self.assertEqual(e.stats['rg_los_calls'],1)
        self.assertEqual(e.stats['rg_cache_hits'],1)
        first=e.energy(site,10);second=e.energy(site,20)
        self.assertEqual(e.stats['static_geometry_computations'],1)
        self.assertAlmostEqual(second['service_energy_kwh'],2*first['service_energy_kwh'])

    def test_fingerprint_covers_scientific_inputs(self):
        signature,files=fingerprint()
        self.assertEqual(len(signature),64)
        self.assertIn('src/common/transport_energy.py',files)
        self.assertTrue(any(name.endswith('.tif') for name in files))


if __name__=='__main__':
    unittest.main(verbosity=2)
