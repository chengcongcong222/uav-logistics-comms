"""P1 isolated objective, accounting and provenance contract."""
import hashlib,json,math,os,time
from pathlib import Path
from src.bench_p1.preferences import OBJECTIVES,normalize,weighted_score
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'results/p1_preflight'
DEV_SEEDS=(26092511,26092512)
METHODS={'Q2':['UNIFORM_LNS','ALNS','POOL','POOL_CHALLENGE'],
         'Q3':['SEQUENTIAL','JOINT','JOINT_CHALLENGE']}
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    os.replace(tmp,path)
def append(path,value):
    with Path(path).open('a') as f:f.write(json.dumps(value,ensure_ascii=False,allow_nan=False)+'\n')
def canonical(metrics,scope):
    m=dict(metrics)
    if scope=='Q2':
        for new,old in [('makespan_s','makespan'),('energy_kwh','energy'),('transport_sorties','sorties')]:
            if new not in m:m[new]=m[old]
    if not all(math.isfinite(float(m[k])) for k in ['J_late']+OBJECTIVES[scope]):raise ValueError('Nonfinite metrics')
    return {k:float(m[k]) for k in ['J_late']+OBJECTIVES[scope]}
def production_vector(m,scope):
    m=canonical(m,scope)
    if scope=='Q2':return dict(J_late=m['J_late'],J_norm=m['J_norm'],joint_makespan_s=m['makespan_s'],total_energy_kwh=m['energy_kwh'],transport_sorties=m['transport_sorties'],relay_sorties=0)
    return m
def nondominated(rows,scope):
    from src.q3.e7_pareto import dominates
    # No rounded deduplication before dominance. Exact equal metric vectors only.
    unique={tuple(canonical(r['metrics'],scope).values()):r for r in rows}
    rr=list(unique.values())
    return [r for r in rr if not any(dominates(production_vector(q['metrics'],scope),production_vector(r['metrics'],scope)) for q in rr if q is not r)]
class Preference:
    def __init__(self,scope,runroot,scales=None,offsets=None):
        self.scope=scope;self.root=Path(runroot);self.index=0
        manifest=json.loads((OUT/'inputs'/f'search_{scope}.json').read_text())
        assert set(manifest)=={'scope','objectives','search_weights'}
        self.weights=manifest['search_weights'];d=len(OBJECTIVES[scope])
        self.scales=scales or ([1,12000,100,80] if scope=='Q2' else [1,16000,120,80,20])
        self.offsets=offsets or [0]*d
        # Exercise endpoint changes first; the entire search-only set follows.
        axes=[i for i,w in enumerate(self.weights) if sum(v>0 for v in w)==1]
        self.order=axes+[i for i in range(len(self.weights)) if i not in axes]
    @property
    def ident(self):return f'{self.scope}_SEARCH_{self.order[self.index%len(self.order)]:03d}'
    @property
    def weight(self):return self.weights[self.order[self.index%len(self.order)]]
    def next(self):self.index+=1
    def event(self,action,**kwargs):append(self.root/'preference_trace.jsonl',dict(cpu_s=time.process_time(),preference_id=self.ident,weights=self.weight,action=action,**kwargs))
    def key(self,metrics,action='objective'):
        m=canonical(metrics,self.scope);v=[m[k] for k in OBJECTIVES[self.scope]]
        score=weighted_score(normalize(v,self.offsets,self.scales),self.weight)
        # Separate late layer, never trade a hard deadline against this score.
        key=(0 if m['J_late']<=1e-4 else 1,max(0,m['J_late']) if m['J_late']>1e-4 else 0,score)
        self.event(action,metrics=m,score=score,key=key)
        return key
def signature(payload):return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
