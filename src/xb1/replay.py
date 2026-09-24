"""Re-export stored witnesses in temporary result directories; compare all CSVs."""
import hashlib,json,tempfile
from pathlib import Path
from src.xb1.audit import ROOT,OUT,load_tables,export as q2export,write
from src.q2.mission import Mission
from src.xb1.q3 import XBEngine,export as q3export

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    checks=[];parent=OUT/'replay_work';parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=parent) as tmp:
        temp=Path(tmp)
        for name,pid in [('run01','XB01'),('run02','XB02')]:
            original=ROOT/'results/q2/pareto_schedules'/pid;dest=temp/pid
            mm=[Mission(**x) for x in json.loads((original/'missions.json').read_text())]
            q2export(mm,load_tables(),dest,name)
            files=[p.name for p in dest.glob('*.csv')]
            equal={f:digest(dest/f)==digest(original/f) for f in files};assert all(equal.values()),equal
            checks.append(dict(solution_id=pid,byte_identical=True,files=equal))
            e=XBEngine(pid);canonical=e.dest;e.dest=temp/'q3'/pid
            for p in sorted((canonical/'solutions').iterdir()):
                result=json.loads((p/'witness.json').read_text());q3export(e,result,p.name);replayed=e.dest/'solutions'/p.name
                files=[f.name for f in replayed.glob('*.csv')]
                equal={f:digest(replayed/f)==digest(p/f) for f in files};assert all(equal.values()),(p.name,equal)
                checks.append(dict(solution_id=p.name,byte_identical=True,files=equal));print('REPLAY_PASS',p.name,flush=True)
    write(OUT/'replay_checks.json',checks)
if __name__=='__main__':main()
