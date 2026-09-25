import unittest,tempfile
from types import SimpleNamespace
from pathlib import Path
import numpy as np
from src.bench_p1_4.fixed import matrix,solve_master,Generator
from src.bench_p1_4.common import OUT

class Tests(unittest.TestCase):
    def test_relay_count_cap_is_not_resource_capacity(self):
        gen=SimpleNamespace(ids=list('abcd'),index={a:i for i,a in enumerate('abcd')})
        cols=[dict(id=a,task_ids=[a],preparation_start_s=10*i,takeoff_s=10*i,uav_available_s=10*i+1,energy_ready_s=10*i+2,total_energy_kwh=1) for i,a in enumerate('abcd')]
        a,lo,hi,_=matrix(gen,cols,False)
        self.assertTrue(np.any(a@np.ones(4)>hi))
        self.assertEqual(hi[-1],3)

    def test_energy_phase_really_uses_energy_coefficients(self):
        gen=SimpleNamespace(ids=['a'],index={'a':0})
        cols=[dict(id='costly',task_ids=['a'],preparation_start_s=0,takeoff_s=0,uav_available_s=10,energy_ready_s=15,total_energy_kwh=2),
              dict(id='efficient',task_ids=['a'],preparation_start_s=0,takeoff_s=0,uav_available_s=10,energy_ready_s=15,total_energy_kwh=.7)]
        root=OUT/'tests/energy_objective';rec,selected,_=solve_master(gen,cols,root,'energy',5)
        self.assertEqual([c['id'] for c in selected],['efficient'])
        self.assertEqual(rec['incumbent']/rec['objective_scale'],.7)

    def test_return_beyond_epsilon_rejected(self):
        import src.bench_p1_4.fixed as f
        e=SimpleNamespace(pr=dict(hover_power_kw=1,comm_power_kw=.1,prep_time_s=1,setup_time_s=1,rho=.2,energy_kwh=10))
        g=Generator.__new__(Generator);g.e=e;g.tasks={'a':(20.,30.)};g.static={'s':dict(flight_energy_kwh=.1,setup_energy_kwh=.01,outbound_time_s=2,return_time_s=5)};g.full=100
        old=f.CAP
        try:
            f.CAP=34.;self.assertIsNone(g.build('s',['a']))
            f.CAP=35.;e.pr['turnaround_time_s']=1;self.assertIsNotNone(g.build('s',['a']))
        finally:f.CAP=old

if __name__=='__main__':unittest.main()
