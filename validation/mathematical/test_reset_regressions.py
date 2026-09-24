"""Boundary-cell failures, preserved search order and fixed-Q4 rejection tests."""
import json,shutil,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'validation/mathematical'))
from src.reset.geometry import FlightDem
from src.q2.operators import _remove_boxes
from src.q2.evaluator_sol import evaluate_solution,pack_key
import reset_q4_validate as q4

class Boundaries(unittest.TestCase):
    def engine(self):
        e=FlightDem.__new__(FlightDem);e.cache={};e.dem=SimpleNamespace(arr=np.zeros((4,4)),nodata=-9999)
        e.pixels=lambda a,b,t:np.array(a)+(np.array(b)-np.array(a))*np.asarray(t)[...,None]
        return e
    def test_corner_supercover_and_reverse(self):
        e=self.engine();e.dem.arr[0,1]=123
        self.assertEqual(e.maximum((.5,.5),(2.5,2.5))['max_dem_m'],123)
        self.assertEqual(e.maximum((2.5,2.5),(.5,.5))['max_dem_m'],123)
    def test_edge_nodata_rejected(self):
        e=self.engine();e.dem.arr[0,1]=-9999
        with self.assertRaises(AssertionError):e.maximum((.5,1),(2.5,1))
    def test_outside_rejected(self):
        with self.assertRaises(AssertionError):self.engine().maximum((-.1,.5),(2,.5))
    def test_removal_keeps_route_order(self):
        raw=pack_key('C',['C','B','A'],{'A':['a'],'B':['b'],'C':['c','d']})
        ms,_=_remove_boxes([raw],{'d'})
        self.assertEqual(ms[0]['service_sequence'],['C','B','A'])
    def test_explicit_schedule_order_reaches_decoder(self):
        specs=[pack_key('A',[s],{s:[s]}) for s in ['late','early']]
        box=pd.DataFrame([dict(box_id='late',priority_weight=1,expected_deadline_s=100),dict(box_id='early',priority_weight=1,expected_deadline_s=10)]).set_index('box_id')
        def evaluate(typ,by,seq,**kwargs):return SimpleNamespace(box_ids=seq,hard_deadline_latest_start=100 if seq[0]=='late' else 10,initial_payload_kg=1)
        ev=SimpleNamespace(evaluate_mission=evaluate,box_idx=box);seen=[]
        def decode(ms):seen.extend(m.box_ids[0] for m in ms);return [],None,False
        evaluate_solution(specs,ev,SimpleNamespace(decode_order=decode),preserve_order=True)
        self.assertEqual(seen,['late','early'])

class Q4Mutations(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.out=Path(self.tmp.name)/'q4';shutil.copytree(ROOT/'results/reset/q4',self.out)
        self.old=q4.OUT;q4.OUT=self.out;self.d=self.out/'solutions/Q4_K2_005'
    def tearDown(self):q4.OUT=self.old;self.tmp.cleanup()
    def test_changed_frozen_time_rejected(self):
        p=self.d/'transport_sorties.csv';f=q4.read(p);f.loc[0,'takeoff_s']+=1;f.to_csv(p,index=False)
        with self.assertRaisesRegex(ValueError,'Frozen task value'):q4.validate()
    def test_understated_resource_rejected(self):
        p=self.out/'all_partitions.json';rows=json.loads(p.read_text());rows[0]['groups'][0]['resources']['TUAV_A']-=1;p.write_text(json.dumps(rows))
        with self.assertRaisesRegex(ValueError,'Nonminimal resource allocation'):q4.validate()
    def test_broken_dependency_rejected(self):
        p=self.d/'service_partition.csv';f=q4.read(p);f.loc[f.service_id=='S003','group_id']='G2';f.to_csv(p,index=False)
        with self.assertRaisesRegex(ValueError,'Cross-group mission dependency'):q4.validate()
if __name__=='__main__':unittest.main(verbosity=2)
