"""Isolated F13 readmission and publication data boundary."""
import hashlib,json,sys,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'results/p1_5a'
BASE='1af5aeebf6f30bc447bc8e45ee77fead38317c3e'
PID='F13'
IDENT='F13_C2_SITE_B6500_RELAY_00_Q3'
SOURCE=ROOT/'results/p1_4/screening/F13'
PACKAGE=OUT/'execution/q3/F13/solutions'/IDENT
GEOMETRY=ROOT/'results/reset/geometry'
def read(p):return json.loads(Path(p).read_text())
def write(p,v):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def hashes(paths):return {str(p.relative_to(ROOT)):digest(p) for p in sorted(paths) if p.is_file()}
def require_admitted():
    assert read(OUT/'F13_readmission.json')['status']=='CURRENT_AUTONOMOUS_MAIN_CANDIDATE'
READS=set()
def install_guard():
    """No historical writes or unlisted result reads, including imported code."""
    allowed=[
      'results/p1_5a/','results/p1_4/screening/F13/','results/p1_4/q2/pareto_schedules/F13/',
      'results/p1_4/representatives/F13.json','results/p1_4/transport_runs/B6250_energy_N24/',
      'results/p1_4/transport_runs/B6250_sorties/',
      'results/p1_3b/inputs/pattern_pool.json','results/p1_3b/pool_manifest.json',
      'results/p1_3b/representatives/T01.json','results/p1_3b/transport_runs/makespan_v3/config.json',
      'results/reset/pattern_pool.json','results/reset/q2/pareto_schedules/A11/missions.json',
      'results/reset/geometry/','results/reset/q1/',
      'results/p1_preflight/inputs/common_sites.json','results/p1_preflight/site_provenance.json',
      'results/q3/relay_sites_e52.csv','results/q3/e8/gamma_02/candidate_sites.csv',
      'results/q3/e8/gamma_04/candidate_sites.csv','results/q3/e8/gamma_06/candidate_sites.csv',
      'results/q3/e6/candidate_sites_P01.csv','results/q3/e6/candidate_sites_P02.csv',
      'results/q3/e6/candidate_sites_P03.csv']
    def hook(event,args):
        if event!='open' or not args or not isinstance(args[0],(str,bytes,os.PathLike)):return
        p=Path(os.fsdecode(args[0])).resolve()
        try:r=p.relative_to(ROOT).as_posix()
        except ValueError:return
        mode=args[1] if len(args)>1 else None;flags=args[2] if len(args)>2 else 0
        writing=(isinstance(mode,str) and any(x in mode for x in 'wax+')) or (isinstance(flags,int) and flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC))
        if writing:
            if not r.startswith('results/p1_5a/'):raise PermissionError('Historical write denied: '+r)
        else:
            if r.startswith('results/') and not any(r==a or (a.endswith('/') and r.startswith(a)) for a in allowed):
                raise PermissionError('Unapproved historical result read: '+r)
            if r.startswith(('data/','results/')):READS.add(r)
    sys.addaudithook(hook)
