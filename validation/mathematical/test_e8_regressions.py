"""Regression checks against real frozen execution packages, including rejection."""
from pathlib import Path
import hashlib,json,shutil,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(Path(__file__).parent))
import e8_validate as audit
from src.q3.e8_search import load_engine

class RobustnessRegressions(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.dest=Path(self.tmp.name)/'execution'
        self.source=ROOT/'results/q3/e8/gamma_00/solutions/Q3E8_G00_001'
        shutil.copytree(self.source,self.dest);self.previous=audit.OUT;audit.OUT=self.dest
    def tearDown(self):audit.OUT=self.previous;self.tmp.cleanup()
    def test_positive_physical_margin_is_not_enough_at_gamma2(self):
        v=json.loads((self.source/'validation_P01_0.5.json').read_text())
        self.assertGreater(v['minimum_twohop_margin_db'],0)
        self.assertLess(v['minimum_twohop_margin_db'],2)
        (self.dest/'scenario.json').write_text(json.dumps(dict(Gamma_C_db=2)))
        p=self.dest/'joint_metrics_P01.json';m=json.loads(p.read_text());m['Gamma_C_db']=2;p.write_text(json.dumps(m))
        with self.assertRaisesRegex(ValueError,'below Gamma'):audit.validate_plan('P01',.5)
    def test_cross_type_battery_is_rejected(self):
        p=self.dest/'transport_sorties_P01.csv';f=audit.read(p);f.loc[f.sortie_id=='M001','battery_id']='BAT-B-01';f.to_csv(p,index=False)
        shifts=audit.read(self.dest/'transport_shifts_P01.csv').set_index('sortie_id').shift_s.to_dict()
        with self.assertRaisesRegex(ValueError,'Battery type mismatch'):audit.validate_transport('P01',shifts)
    def test_replay_loading_does_not_rewrite_demands_or_physics(self):
        files=[ROOT/'data/processed/communication_parameters.json',ROOT/'results/q3/e8/gamma_02/robust_tasks.csv',ROOT/'results/q3/e8/gamma_02/demand_summary.json']
        before=[hashlib.sha256(p.read_bytes()).hexdigest() for p in files]
        e=load_engine(2);self.assertTrue((e.atoms.Gamma_C_db==2).all())
        self.assertEqual(before,[hashlib.sha256(p.read_bytes()).hexdigest() for p in files])
    def test_new_direct_gap_on_previous_direct_only_flight(self):
        old=audit.read(self.source/'guarded_atomic_tasks.csv')
        new=audit.read(ROOT/'results/q3/e8/gamma_02/robust_tasks.csv')
        self.assertNotIn('M005',set(old.transport_sortie_id))
        self.assertIn('M005',set(new.transport_sortie_id))
        profile=audit.read(ROOT/'results/q3/e8/direct_profile_P01.csv')
        rows=profile[profile.transport_sortie_id=='M005']
        self.assertTrue(((rows.direct_margin_db>=0)&(rows.direct_margin_db<2)).any())

if __name__=='__main__':unittest.main(verbosity=2)
