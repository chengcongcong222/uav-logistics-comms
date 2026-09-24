"""Reject over-budget, unexpected-limit and late-checkpoint accounting errors."""
import unittest
from ablation_gate import check_budget
class Accounting(unittest.TestCase):
    def setUp(self):
        self.p=dict(cpu_budget_s=180,maximum_observed_cpu_overshoot_tolerance_s=.2)
        self.r=dict(termination='CPU_BUDGET',exit_code=-9,observed_process_cpu_s=180.015,accepted_checkpoints=['P1'])
        self.c=[dict(pid='P1',cpu_ready_s=179),dict(pid='P2',cpu_ready_s=180.5)]
    def test_hard_cutoff_keeps_only_complete_in_budget_checkpoint(self):check_budget(self.r,self.c,self.p)
    def test_late_checkpoint_rejected(self):
        self.r['accepted_checkpoints'].append('P2')
        with self.assertRaisesRegex(ValueError,'checkpoint set'):check_budget(self.r,self.c,self.p)
    def test_excess_cpu_rejected(self):
        self.r['observed_process_cpu_s']=181
        with self.assertRaisesRegex(ValueError,'CPU cap'):check_budget(self.r,self.c,self.p)
    def test_old_sigxcpu_mismatch_rejected(self):
        self.r.update(termination='WORKER_FINISHED',exit_code=-24,observed_process_cpu_s=168)
        with self.assertRaisesRegex(ValueError,'Unexpected termination'):check_budget(self.r,self.c,self.p)
    def test_duplicate_checkpoint_rejected(self):
        self.c.append(dict(pid='P1',cpu_ready_s=179.1))
        with self.assertRaisesRegex(ValueError,'Duplicate'):check_budget(self.r,self.c,self.p)
if __name__=='__main__':unittest.main(verbosity=2)
