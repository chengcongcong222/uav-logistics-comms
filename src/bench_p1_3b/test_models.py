import unittest,math
from fractions import Fraction
from collections import Counter
import numpy as np
import pandas as pd
from ortools.sat.python import cp_model
from src.bench_p1_3b.common import *
from src.bench_p1_3b.transport import build_cp,warm_hint
from src.bench_p1_3b.bounds import build,down,up

class ModelTests(unittest.TestCase):
    def test_rounding_encloses_physical_intervals(self):
        for prep,duration,charge in [(1.03,10.02,4.004),(2,10,10),(330.000000001,1000.999999999,852.301621)]:
            self.assertLessEqual(Fraction(floor_units(prep),UNITS),Fraction.from_float(prep))
            self.assertGreaterEqual(Fraction(ceil_units(duration),UNITS),Fraction.from_float(duration))
            self.assertGreaterEqual(Fraction(ceil_units(duration+charge),UNITS),Fraction.from_float(duration+charge))
    def test_battery_recharge_changes_optimal_schedule(self):
        # Two UAVs but one battery: second takeoff waits for first recharge.
        p=dict(classes=[dict(key=['S',1,1,200,200,1],boxes=['B1','B2'])],patterns=[dict(type='A',counts=[[0,1]],sequence=['S'],duration=10.,prep=2.,charge=10.,energy=1.,delivery={'0':5.},zero_latest=190.,hard_latest=190.)])
        t=dict(uavs=pd.DataFrame(dict(uav_type=['A','A','B','C'])),batteries=pd.DataFrame(dict(uav_type=['A','B','C'],battery_pool_count=[1,1,1])))
        m,jobs,T,scale=build_cp(p,t,'makespan');s=cp_model.CpSolver();s.parameters.num_search_workers=1;s.parameters.random_seed=26092511;s.parameters.max_time_in_seconds=5
        self.assertEqual(s.solve(m),cp_model.OPTIMAL);self.assertEqual(s.value(T)/scale,28.)
        self.assertEqual(sum(s.value(j['z']) for j in jobs),2)
    def test_outward_arithmetic_is_conservative(self):
        for exact in [Fraction(1,3),Fraction(-11,7),Fraction(10000000001,3),Fraction(1,10**20)]:
            self.assertLessEqual(Fraction.from_float(down(exact)),exact)
            self.assertGreaterEqual(Fraction.from_float(up(exact)),exact)
    def test_complete_grid_hint_is_feasible(self):
        p=pool();m,jobs,T,scale=build_cp(p,tables(),'makespan');info=warm_hint(m,jobs,T,p);self.assertTrue(info['used'])
        s=cp_model.CpSolver();s.parameters.fix_variables_to_their_hinted_value=True;s.parameters.num_search_workers=1;s.parameters.random_seed=26092511;s.parameters.max_time_in_seconds=10
        self.assertEqual(s.solve(m),cp_model.OPTIMAL)
        expected=len(read(ROOT/'results/reset/q2/pareto_schedules/A11/missions.json'))
        self.assertEqual(sum(s.value(j['z']) for j in jobs),expected)
    def test_full_continuous_relaxation_contains_verified_A11(self):
        p=pool();t=tables();model,costs=build(p,t);x=np.zeros(len(model.names));index={n:i for i,n in enumerate(model.names)}
        missions=read(ROOT/'results/reset/q2/pareto_schedules/A11/missions.json');lookup={pattern_key(r):i for i,r in enumerate(p['patterns'])};bc={b:c for c,r in enumerate(p['classes']) for b in r['boxes']}
        for r in missions:
            key=(r['uav_type'],tuple(r['service_sequence']),tuple(sorted(Counter(bc[b] for b in r['box_ids']).items())));i=lookup[key]
            x[index[f'pattern_count_{i}']]+=1;x[index[f'sum_preparation_starts_{i}']]+=r['preparation_start_s']
        meta=read(ROOT/'results/reset/q2/pareto_schedules/A11/metadata.json');x[index['makespan']]=meta['makespan']
        self.assertLessEqual(max(model.violation(x).values()),1e-6)
        self.assertLessEqual(costs['J_norm']@x,meta['J_norm']+1e-12)
        self.assertAlmostEqual(costs['energy']@x,meta['energy'],places=8)
    def test_parallel_machine_workload_inequality(self):
        # Two explicit non-overlapping calendars, then every tangent remains a necessity.
        jobs=[(0.,3.),(3.,5.),(0.,4.),(4.,2.)];n=2;W=sum(p for s,p in jobs)
        lhs=sum(p*s+.5*p*p for s,p in jobs)
        self.assertGreaterEqual(lhs,W*W/(2*n))
        for w0 in [0,5,14,30]:self.assertGreaterEqual(lhs,w0*W/n-w0*w0/(2*n))

if __name__=='__main__':unittest.main()
