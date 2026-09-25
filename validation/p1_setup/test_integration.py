"""Integration contracts for P1; complete-plan audits are separate."""
import copy,json,random,tempfile,unittest
from pathlib import Path
import numpy as np
from src.bench_p1.common import OUT,Preference,canonical,nondominated,signature,production_vector
from src.bench_p1.alns import Adaptive,repair,destroy,local_candidates
from src.q3.e7_pareto import dominates,unique_results
from src.bench.run import cpu

class Contracts(unittest.TestCase):
    def test_unit_mapping(self):
        m=canonical(dict(J_late=0,J_norm=.5,makespan=3600,energy=1,sorties=2),'Q2')
        self.assertEqual(m['makespan_s'],3600);self.assertEqual(m['energy_kwh'],1)
    def test_q3_split_sorties(self):
        a=dict(J_late=0,J_norm=.5,joint_makespan_s=100,total_energy_kwh=1,transport_sorties=20,relay_sorties=8)
        b=dict(a,transport_sorties=22,relay_sorties=5)
        self.assertFalse(dominates(a,b));self.assertFalse(dominates(b,a))
    def test_rounding_can_destroy_nondominance(self):
        a=dict(J_late=0,J_norm=.5000002,joint_makespan_s=100,total_energy_kwh=1,transport_sorties=2,relay_sorties=1)
        b=dict(a,J_norm=.5000001)
        rows=[dict(metrics=a),dict(metrics=b)]
        self.assertTrue(dominates(b,a));self.assertEqual(len(unique_results(rows)),1)
        self.assertEqual(nondominated(rows,'Q3')[0]['metrics'],b)
    def test_energy_tolerance(self):
        a=dict(J_late=0,J_norm=.5,joint_makespan_s=100,total_energy_kwh=1,transport_sorties=2,relay_sorties=1)
        self.assertFalse(dominates(dict(a,total_energy_kwh=1-5e-9),a))
        self.assertTrue(dominates(dict(a,total_energy_kwh=1-2e-8),a))
    def test_empty_archive(self):self.assertEqual(nondominated([],'Q2'),[])
    def test_preference_changes_ranking(self):
        with tempfile.TemporaryDirectory(dir=OUT) as d:
            p=Preference('Q2',d)
            a=dict(J_late=0,J_norm=.3,makespan=1000,energy=2,sorties=2)
            b=dict(a,J_norm=.5,makespan=500)
            self.assertLess(p.key(a),p.key(b));p.next();self.assertGreater(p.key(a),p.key(b))
    def test_zero_late_priority(self):
        with tempfile.TemporaryDirectory(dir=OUT) as d:
            p=Preference('Q2',d);a=dict(J_late=0,J_norm=.9,makespan=900,energy=20,sorties=9)
            b=dict(a,J_late=1,J_norm=.1,makespan=100,energy=1,sorties=1)
            self.assertLess(p.key(a),p.key(b))
    def test_adaptive_probabilities_update(self):
        a=Adaptive(['a','b']);a.update('a',8)
        self.assertGreater(a.weights['a'],a.weights['b'])
        r=random.Random(26092511);draws=[a.choose(r) for _ in range(1000)]
        self.assertGreater(draws.count('a'),draws.count('b'))
    def test_cache_dependency_invalidation(self):
        d=dict(scene='x',radio='r',route=['a','b'],step=.5,gamma=0)
        for key,value in [('scene','y'),('radio','s'),('route',['b','a']),('step',.25),('gamma',2)]:
            self.assertNotEqual(signature(d),signature(dict(d,**{key:value})))
    def test_run_cache_isolation(self):
        self.assertNotEqual(signature(dict(private_root='A',shape='x')),signature(dict(private_root='B',shape='x')))
    def test_search_files_have_no_holdout(self):
        for scope in ['Q2','Q3']:
            data=json.loads((OUT/'inputs'/f'search_{scope}.json').read_text())
            self.assertEqual(set(data),{'scope','objectives','search_weights'})
    def test_hard_deadlines_from_raw_flags(self):
        from src.reset.geometry import tables
        from src.q2.evaluator import MissionEvaluator
        ev=MissionEvaluator(tables())
        for b in ev.boxes.itertuples():
            ds=[]
            if b.is_medical:ds.append(b.expected_deadline_s)
            if b.is_first_batch:ds.append(b.first_deadline_s)
            self.assertEqual(ev.hard_deadline(b.box_id),min(ds) if ds else None)
    def test_cpu_clock(self):
        import os,time
        self.assertLess(abs(cpu(os.getpid())-time.process_time()),.05)

class SmallPhysicalCase(unittest.TestCase):
    def test_complete_two_box_domain_and_alns_moves(self):
        """All partitions/types/orders for two real boxes, earliest decoder only."""
        import itertools
        from src.reset.geometry import tables
        from src.q2.evaluator import MissionEvaluator
        from src.q2.scheduler import ResourceDecoder
        from src.q2.evaluator_sol import evaluate_solution,pack_key
        from src.bench_p1.common import write
        tab=tables();boxes=tab['boxes'].groupby('service_id',sort=True).head(1).iloc[:2].copy();tab['boxes']=boxes
        ev=MissionEvaluator(tab);dec=ResourceDecoder(tab);b=list(boxes.box_id);s=list(boxes.service_id);raw=[]
        for typ in 'ABC':
            for seq in itertools.permutations(s):raw.append([pack_key(typ,list(seq),{s[0]:[b[0]],s[1]:[b[1]]})])
        for types in itertools.product('ABC',repeat=2):
            ms=[pack_key(types[i],[s[i]],{s[i]:[b[i]]}) for i in range(2)]
            raw.extend([ms,list(reversed(ms))])
        solutions=[]
        for specs in raw:
            sol=evaluate_solution(specs,ev,dec,preserve_order=True)
            if sol:solutions.append(sol)
        self.assertTrue(solutions);rows=[];moves=[]
        with tempfile.TemporaryDirectory(dir=OUT) as d:
            pref=Preference('Q2',d)
            for axis in range(4):
                best=min(solutions,key=lambda x:pref.key(x.metrics))
                # A finite exact enumeration certificate, not a continuous-time optimum.
                rows.append(dict(preference_id=pref.ident,best=best.metrics,feasible_candidates=len(solutions)))
                for kind in ['random','timeliness','related']:
                    rng=random.Random(26092511);ms,loose=destroy(best,kind,rng,ev)
                    for r in ['greedy','regret2']:
                        out=repair(ms,loose,r,rng,ev,dec,pref,lambda:1000)
                        self.assertIsNotNone(out)
                        self.assertEqual(sorted(x for m in out.missions for bs in m['boxes_by_service'].values() for x in bs),sorted(b))
                        self.assertGreaterEqual(pref.key(out.metrics),pref.key(best.metrics))
                        moves.append(dict(axis=axis,destroy=kind,repair=r,metrics=out.metrics))
                pref.next()
        write(OUT/'small_domain_certificate.json',dict(status='ENUMERATED_DOMAIN_CHECKED',boxes=b,raw_candidates=len(raw),feasible_candidates=len(solutions),scope='ALL_TWO_BOX_PARTITIONS_TYPES_VISIT_ORDERS_AND_MISSION_ORDERS_WITH_FIXED_EARLIEST_RESOURCE_DECODER;NOT_ALL_CONTINUOUS_SCHEDULES',preferences=rows,repair_checks=moves,full_problem_global_optimum=False))
if __name__=='__main__':unittest.main()
