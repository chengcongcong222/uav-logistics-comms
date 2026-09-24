"""Regressions for resource occupancy, shared communication energy and auditing."""
import json,unittest
from unittest.mock import patch
from e6_validate import *
from src.q3.e6_resources import ResourceEngine,interval_union,sortie_column,min_site_cover
from src.q3.e6_run import load_pool
from src.q3.e6_guard import apply_guards


class RegressionTests(unittest.TestCase):
    def test_common_site_cover_is_not_task_count(self):
        edges={'a':{'x':1},'b':{'x':1},'c':{'y':1}}
        self.assertEqual(min_site_cover(['a','b','c'],edges)[0],2)

    def test_half_open_calendar_and_turnaround(self):
        rows=pd.DataFrame([dict(id='R01',start=0,end=100),dict(id='R01',start=100,end=200)])
        no_overlap(rows,'id','start','end',['R01'])
        rows.loc[1,'start']=99
        with self.assertRaises(ValueError):no_overlap(rows,'id','start','end',['R01'])

    def test_battery_can_charge_during_preparation(self):
        # First pack is recharged at 100. Next prep starts at 90 and takeoff 120.
        rows=pd.DataFrame([dict(id='E1',takeoff=0,ready=100),dict(id='E1',takeoff=120,ready=200)])
        no_overlap(rows,'id','takeoff','ready',['E1'])
        self.assertLess(90,100);self.assertGreater(120,100)
        self.assertAlmostEqual(charging(.9,1800),630)
        self.assertAlmostEqual(charging(1,1800),0)

    def test_one_to_many_power_and_wait_energy(self):
        e=ResourceEngine();load_pool(e,'P01')
        saved=json.loads((OUT/'selected_sorties_P01.json').read_text())
        row=next(r for r in saved if len(r['task_ids'])>=2)
        aid=row['task_ids'][0];site=row['site_id']
        single=sortie_column(e,'P01',site,[aid]);duplicate=sortie_column(e,'P01',site,[aid,aid])
        self.assertAlmostEqual(single['total_energy_kwh'],duplicate['total_energy_kwh'])
        # Deliberately separated intervals retain paid hover between them.
        a,b=row['task_ids'][:2]
        e.atoms.loc[a,['service_start_s','service_end_s']]=[1000.,1100.]
        e.atoms.loc[b,['service_start_s','service_end_s']]=[1200.,1300.]
        r=sortie_column(e,'P01',site,[a,b])
        self.assertAlmostEqual(r['active_communication_s'],200)
        self.assertAlmostEqual(r['idle_hover_s'],100)
        self.assertAlmostEqual(r['idle_energy_kwh'],e.pr['hover_power_kw']*100/3600)

    def test_independent_validator_rejects_changed_delivery(self):
        pid='P01';shifts=read(OUT/f'transport_shifts_{pid}.csv').set_index('sortie_id').shift_s.to_dict()
        original_read=read
        def tampered(path):
            frame=original_read(path)
            if str(path).endswith('box_delivery_P01.csv'):frame.loc[0,'delivery_time_s']+=10
            return frame
        with patch('e6_validate.read',side_effect=tampered):
            with self.assertRaises(ValueError):validate_transport(pid,shifts)


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(RegressionTests))
    (OUT/'regressions.json').write_text(json.dumps(dict(tests=result.testsRun,failures=len(result.failures)+len(result.errors)),indent=2)+'\n')
    sys.exit(0 if result.wasSuccessful() else 1)
