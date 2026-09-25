import unittest
from types import SimpleNamespace
import numpy as np
from src.bench_p1_3c.fixed import Generator,nondominated_columns,matrix,FIELDS
from src.bench_p1_3c.common import *
from src.bench_p1_3c.coupling import coverable

class Models(unittest.TestCase):
    def test_two_site_cover_requires_consistency(self):
        tasks={'a':{'sites':['x']},'b':{'sites':['y']},'c':{'sites':['z']}}
        self.assertFalse(coverable(list(tasks),tasks))
        tasks['c']['sites']=['x','z'];self.assertTrue(coverable(list(tasks),tasks))

    def test_two_site_nontriple_obstruction(self):
        import itertools
        tasks={'a':{'sites':['x','y']},'b':{'sites':['x','z']},'c':{'sites':['y','z']},'d':{'sites':['w']}}
        self.assertFalse(coverable(list(tasks),tasks))
        self.assertTrue(all(coverable(list(c),tasks) for c in itertools.combinations(tasks,3)))

    def test_resource_end_is_reusable(self):
        gen=SimpleNamespace(ids=['a','b','c'],index=dict(a=0,b=1,c=2))
        cols=[dict(task_ids=[a],preparation_start_s=s,uav_available_s=t,takeoff_s=s,energy_ready_s=t) for a,s,t in [('a',0,5),('b',0,5),('c',5,10)]]
        a,lo,hi,_=matrix(gen,cols,False);self.assertTrue(np.all(a@np.ones(3)<=hi))
        cols[-1]['preparation_start_s']=4
        a,lo,hi,_=matrix(gen,cols,False);self.assertFalse(np.all(a@np.ones(3)<=hi))

    def test_dominance_retains_resource_tradeoff(self):
        base=dict(task_ids=['a'],preparation_start_s=2,takeoff_s=3,uav_available_s=8,energy_ready_s=10,return_s=7,total_energy_kwh=1)
        rows=[dict(base,id='a'),dict(base,id='b',preparation_start_s=1),dict(base,id='c',preparation_start_s=3,energy_ready_s=11)]
        self.assertEqual({r['id'] for r in nondominated_columns(rows)},{'a','c'})

    def test_generated_exact_energy_against_original(self):
        e=engine('T01');p=OUT/'T01/C1_FIXED';shifts=read(p/'timings.json');gen=Generator(e,shifts)
        rows=read(p/'columns.json');sample=rows[::max(1,len(rows)//120)]
        for c in sample:
            regenerated=gen.build(c['site_id'],c['task_ids']);physical=sortie_column(e,e.pid,c['site_id'],c['task_ids'],shifts)
            self.assertIsNotNone(physical)
            for f in FIELDS:self.assertAlmostEqual(regenerated[f],physical[f],places=7)

if __name__=='__main__':unittest.main()
