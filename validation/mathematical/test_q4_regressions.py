"""Reject changes that would silently violate fixed-task independent Q4."""
from pathlib import Path
import json,shutil,tempfile,unittest
import q4_validate as audit
class Regressions(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.out=Path(self.tmp.name)/'q4';shutil.copytree(audit.ROOT/'results/q4',self.out)
        self.old=audit.OUT;audit.OUT=self.out;self.d=self.out/'solutions/Q4_K2_001'
    def tearDown(self):audit.OUT=self.old;self.tmp.cleanup()
    def test_changed_frozen_task_time_rejected(self):
        p=self.d/'transport_sorties.csv';f=audit.read(p);f.loc[0,'takeoff_s']+=1;f.to_csv(p,index=False)
        with self.assertRaisesRegex(ValueError,'Frozen task value'):audit.validate()
    def test_understated_minimum_pool_rejected(self):
        p=self.out/'all_partitions.json';rows=json.loads(p.read_text());rows[0]['groups'][0]['resources']['TUAV_B']-=1;p.write_text(json.dumps(rows))
        with self.assertRaisesRegex(ValueError,'Nonminimal resource allocation'):audit.validate()
    def test_split_relay_dependency_rejected(self):
        p=self.d/'service_partition.csv';f=audit.read(p);f.loc[f.service_id=='S014','group_id']='G2';f.to_csv(p,index=False)
        with self.assertRaisesRegex(ValueError,'Cross-group mission dependency'):audit.validate()
if __name__=='__main__':unittest.main(verbosity=2)
