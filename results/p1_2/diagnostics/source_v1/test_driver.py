import json, tempfile, unittest
from pathlib import Path
from src.bench_p1_2.driver import Anchor, AXES, run
from src.bench_p1.common import nondominated

def metrics(**kw):
    return dict(J_late=0.,J_norm=.5,joint_makespan_s=8000.,total_energy_kwh=70.,
                transport_sorties=25,relay_sorties=5,**kw) if not kw else {**metrics(),**kw}

class AnchorContract(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def test_five_anchor_keys_discriminate(self):
        for axis in AXES:
            p=Anchor(axis,self.root);a=metrics();b=metrics(**{axis:a[axis]*.9})
            self.assertLess(p.key(b),p.key(a))
            self.assertEqual(sum(p.weight),1)
    def test_zero_late_always_protected(self):
        for axis in AXES:
            p=Anchor(axis,self.root)
            soft=metrics(J_late=.001,**{axis:0})
            self.assertLess(p.key(metrics()),p.key(soft))
    def test_threshold_boundary(self):
        p=Anchor('total_energy_kwh',self.root)
        self.assertEqual(p.key(metrics(J_late=1e-4))[0],0)
        self.assertEqual(p.key(metrics(J_late=1.00001e-4))[0],1)
    def test_relay_feedback_reverses_transport_proxy(self):
        a=dict(id='A',pid='A',metrics=metrics(transport_sorties=19,relay_sorties=7))
        b=dict(id='B',pid='B',metrics=metrics(transport_sorties=25,relay_sorties=5))
        self.assertEqual(Anchor('relay_sorties',self.root).rank([a,b],'probe')[0]['id'],'B')
        self.assertEqual(Anchor('transport_sorties',self.root).rank([a,b],'probe')[0]['id'],'A')
    def test_sorties_not_merged_for_dominance(self):
        rows=[dict(metrics=metrics(transport_sorties=20,relay_sorties=8)),
              dict(metrics=metrics(transport_sorties=22,relay_sorties=5))]
        self.assertEqual(len(nondominated(rows,'Q3')),2)
    def test_no_cold_entry(self):
        with self.assertRaises(AssertionError):run(26092511,'FORMAL_COLD')
    def test_no_formal_seed(self):
        with self.assertRaises(AssertionError):run(12345,'DIAGNOSTIC_WARM')
    def test_trace_records_preselection(self):
        p=Anchor('relay_sorties',self.root)
        p.rank([dict(id='A',pid='A11',metrics=metrics())],'transport_selection')
        r=json.loads((self.root/'anchor_trace.jsonl').read_text())
        self.assertEqual(r['action'],'transport_selection')
        self.assertEqual(r['anchor'],'relay_sorties')
        self.assertIn('key',r['candidates'][0])

if __name__=='__main__':unittest.main()
