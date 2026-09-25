"""Security properties needed by the publication admission boundary."""
import hashlib,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from src.p1_5a.common import ROOT,OUT
from src.p1_5a.source_guard import SourceGuard
class SourceGuardTests(unittest.TestCase):
    def setUp(self):
        (OUT/'tests').mkdir(exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=OUT/'tests')
        self.root=Path(self.tmp.name)
        self.allowed=self.root/'allowed.json';self.allowed.write_text('{"value":1}')
        self.hidden=self.root/'unlisted.json';self.hidden.write_text('{"value":2}')
        self.policy=self.root/'policy.json'
        self.policy.write_text(json.dumps(dict(sources=[dict(path=self.allowed.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(self.allowed.read_bytes()).hexdigest())])))
    def tearDown(self):self.tmp.cleanup()
    def test_allowed_hash_bound_read(self):
        g=SourceGuard(self.policy);self.assertEqual(g.json(self.allowed),{'value':1})
    def test_unlisted_denied(self):
        with self.assertRaises(PermissionError):SourceGuard(self.policy).json(self.hidden)
    def test_hash_tampering_denied(self):
        g=SourceGuard(self.policy);self.allowed.write_text('{"value":9}')
        with self.assertRaises(PermissionError):g.json(self.allowed)
    def test_symlink_cannot_bypass(self):
        link=self.root/'link.json';link.symlink_to(self.hidden)
        with self.assertRaises(PermissionError):SourceGuard(self.policy).json(link)
    def probe(self,path):
        code="""import sys
from pathlib import Path
from src.p1_5a.source_guard import SourceGuard
g=SourceGuard(sys.argv[1]);g.install()
try:
    Path(sys.argv[2]).read_bytes()
except PermissionError:
    print('DENIED_BEFORE_READ')
else:
    print('READ')
"""
        r=subprocess.run([sys.executable,'-c',code,str(self.policy),str(path)],cwd=ROOT,text=True,capture_output=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
        self.assertEqual(r.returncode,0,r.stderr);return r.stdout.strip()
    def test_direct_open_cannot_bypass(self):self.assertEqual(self.probe(self.hidden),'DENIED_BEFORE_READ')
    def test_direct_open_checks_hash(self):
        self.allowed.write_text('{"value":10}')
        self.assertEqual(self.probe(self.allowed),'DENIED_BEFORE_READ')
    def test_direct_open_allowed(self):self.assertEqual(self.probe(self.allowed),'READ')
if __name__=='__main__':unittest.main()
