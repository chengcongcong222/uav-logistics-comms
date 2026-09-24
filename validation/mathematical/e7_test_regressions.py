"""E7 regression tests for lexicographic Pareto filtering and freed resources."""
import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from src.q3.e7_pareto import dominates,nondominated,OUT
from src.q3.e7_core import engine_for,solve_seed,read
import e7_validate as validator
from unittest.mock import patch


class Tests(unittest.TestCase):
    def metric(self,late=10,norm=.5,makespan=100,energy=10,rs=2):
        return dict(J_late=late,J_norm=norm,joint_makespan_s=makespan,total_energy_kwh=energy,transport_sorties=28,relay_sorties=rs)
    def test_timeliness_is_lexicographic(self):
        self.assertTrue(dominates(self.metric(late=9,norm=.9),self.metric(late=10,norm=.1)))
        self.assertFalse(dominates(self.metric(late=10,norm=.9),self.metric(late=10,norm=.1)))
    def test_energy_delay_tradeoff_survives(self):
        a=dict(metrics=self.metric(late=9,energy=11));b=dict(metrics=self.metric(late=10,energy=10))
        self.assertEqual(len(nondominated([a,b])),2)
    def test_baseline_dominance(self):
        a=self.metric();b=self.metric(late=12,makespan=120,energy=12,rs=3)
        self.assertTrue(dominates(a,b));self.assertFalse(dominates(b,a))
    def test_new_resource_assignments_and_advances_validate(self):
        dest=OUT/'solutions/L1_RESOURCE_ABLATION';old=validator.OUT
        try:
            validator.OUT=dest
            shifts=read(dest/'transport_shifts_P01.csv').set_index('sortie_id').shift_s.to_dict()
            self.assertTrue(any(v<0 for v in shifts.values()))
            validator.validate_transport('P01',shifts)
        finally:validator.OUT=old
    def test_wrong_battery_type_rejected(self):
        dest=OUT/'solutions/L1_RESOURCE_ABLATION';old=validator.OUT;validator.OUT=dest
        shifts=read(dest/'transport_shifts_P01.csv').set_index('sortie_id').shift_s.to_dict();reader=validator.read
        def bad(path):
            frame=reader(path)
            if str(path).endswith('transport_sorties_P01.csv'):
                typ=frame.loc[0,'uav_type'];frame.loc[0,'battery_id']='BAT-'+('A' if typ!='A' else 'B')+'-01'
            return frame
        try:
            with patch('e7_validate.read',side_effect=bad):
                with self.assertRaises(ValueError):validator.validate_transport('P01',shifts)
        finally:validator.OUT=old


if __name__=='__main__':
    r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    (OUT/'regressions.json').write_text(json.dumps(dict(tests=r.testsRun,failures=len(r.failures)+len(r.errors)),indent=2)+'\n')
    sys.exit(0 if r.wasSuccessful() else 1)
