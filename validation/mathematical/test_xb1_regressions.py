"""Regression witnesses for actual search omissions and independent audit gates."""
import json,shutil,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import pandas as pd
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'validation/mathematical'))
from src.q2.solve_q2 import load_tables
from src.q2.evaluator import MissionEvaluator
from src.q2.evaluator_sol import Solution,pack_key
from src.q2.operators import _insert_box,_repair_key
from src.q2.initial_solution import build_b1
from xb1_validate import check_package

class SearchRegressions(unittest.TestCase):
    def test_c_new_sortie_survives_crowded_insertions(self):
        ev=MissionEvaluator(load_tables());bid=ev.boxes.iloc[0].box_id;svc=ev.box_idx.loc[bid].service_id
        ms=[pack_key('A',[svc],{svc:['placeholder']}) for _ in range(15)]
        options=_insert_box(ev,ms,bid,None,'same')
        self.assertEqual({x[-1]['uav_type'] for x in options if len(x)==16},{'A','B','C'})

    def test_c_cross_service_merge_reachable(self):
        ev=SimpleNamespace(types=pd.DataFrame(index=['A','B','C']),nodes=pd.DataFrame([dict(node_id='S001',x_m=0,y_m=0),dict(node_id='S002',x_m=1,y_m=1)]))
        raw=[pack_key('A',['S001'],{'S001':['a']}),pack_key('B',['S002'],{'S002':['b']})]
        def evaluate(ms,*args):
            if len(ms)==1 and ms[0]['uav_type']!='C':return None
            return Solution(missions=ms,metrics=dict(sorties=len(ms),energy=10*len(ms),makespan=100*len(ms),J_time=.5))
        base=evaluate(raw)
        with patch('src.q2.initial_solution.evaluate_solution',evaluate):result=build_b1(ev,None,base)
        self.assertEqual(result.metrics['sorties'],1);self.assertEqual(result.missions[0]['uav_type'],'C')

    def test_lateness_precedes_normalized_delivery(self):
        a=Solution(metrics=dict(J_late=0,J_norm=.9,makespan=100,energy=10,sorties=1))
        b=Solution(metrics=dict(J_late=1,J_norm=.1,makespan=100,energy=10,sorties=1))
        self.assertLess(_repair_key(a),_repair_key(b))

class AuditMutations(unittest.TestCase):
    def setUp(self):
        parent=ROOT/'results/xb1/test_work';parent.mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=parent);self.path=Path(self.temp.name)/'q2/pareto_schedules/XB01'
        shutil.copytree(ROOT/'results/q2/pareto_schedules/XB01',self.path)
    def tearDown(self):self.temp.cleanup()
    def test_reject_falsified_energy(self):
        p=self.path/'q2_sorties.csv';df=pd.read_csv(p);df.loc[0,'energy_kwh']-=.1;df.to_csv(p,index=False)
        with self.assertRaises(ValueError):check_package(self.path,'XB01')
    def test_reject_missing_box(self):
        p=self.path/'q2_box_delivery.csv';pd.read_csv(p).iloc[1:].to_csv(p,index=False)
        with self.assertRaises(ValueError):check_package(self.path,'XB01')
    def test_reject_displaced_trace(self):
        p=self.path/'transport_trace.csv';df=pd.read_csv(p);df.loc[0,'z']+=20;df.to_csv(p,index=False)
        with self.assertRaises(AssertionError):check_package(self.path,'XB01')

if __name__=='__main__':unittest.main()
