"""Independent audits of every completed development checkpoint; no rankings."""
import argparse,json,sys
from pathlib import Path
import pandas as pd
from src.bench_p1.common import ROOT,OUT,write,digest,canonical
sys.path.insert(0,str(ROOT/'validation/mathematical'))
from xb1_validate import check_package
def main():
    p=argparse.ArgumentParser();p.add_argument('--batch');a=p.parse_args();records=[];failures=[];runs=[]
    geometry=pd.read_csv(ROOT/'results/reset/geometry/route_geometry.csv',float_precision='round_trip')
    paths=[OUT/'runs'/a.batch/'run_status.json'] if a.batch else sorted((OUT/'runs').glob('*/run_status.json'))
    for path in paths:
        status=json.loads(path.read_text())
        for run in status:
            root=ROOT/run['root'];rows=json.loads((root/'checkpoints.json').read_text()) if (root/'checkpoints.json').exists() else []
            rr=[]
            for row in rows:
                if row['pid'] not in run['accepted']:continue
                dest=Path(row['package'])
                try:
                    if row['scope']=='Q2':
                        if (dest/'validation.json').exists():
                            result=json.loads((dest/'validation.json').read_text())
                            for name,h in result['artifact_sha256'].items():assert digest(dest/name)==h
                        else:result=check_package(dest,row['pid'],geometry)
                    else:
                        if (dest/'validation_0.5.json').exists():
                            result=json.loads((dest/'validation_0.5.json').read_text())
                            assert result['status']=='P1_Q3_INDEPENDENTLY_VALIDATED'
                            for name,h in result['artifact_sha256'].items():assert digest(ROOT/name)==h
                        else:
                            import reset_q3_validate as q3
                            q3.OUT=root;q3.audit.IndependentAudit=q3.Checker;q3.audit.Q3=root/'q3';q3.audit.DATA=ROOT/'results/reset/geometry';q3.audit.OUT=dest
                            result=q3.audit.validate_plan(row['transport_pid'],.5)
                            write(dest/'validation_0.5.json',dict(result,status='P1_Q3_INDEPENDENTLY_VALIDATED'))
                    r=dict(run=run['root'],pid=row['pid'],scope=row['scope'],method=run['method'],seed=run['seed'],cpu_ready_s=row['cpu_ready_s'],metrics=canonical(row['metrics'],row['scope']),package=str(dest.relative_to(ROOT)))
                    records.append(r);rr.append(r)
                except Exception as exc:failures.append(dict(run=run['root'],pid=row['pid'],error=repr(exc)))
            events=[json.loads(l) for l in (root/'preference_trace.jsonl').read_text().splitlines()] if (root/'preference_trace.jsonl').exists() else []
            opens=[json.loads(l)['path'] for l in (root/'input_opens.jsonl').read_text().splitlines()] if (root/'input_opens.jsonl').exists() else json.loads((root/'input_access.json').read_text()) if (root/'input_access.json').exists() else []
            own=[r for r in rr if r['scope']==run['scope']]
            runs.append(dict(**run,verified_complete_scope_packages=len(own),verified_transport_packages=sum(r['scope']=='Q2' for r in rr),zero_late_found=any(r['metrics']['J_late']<=1e-4 for r in own),phase=json.loads((root/'phase.json').read_text()),preference_ids=sorted({e['preference_id'] for e in events}),adaptive_updates=sum(e['action']=='acceptance' for e in events),adaptive_selections=sum(e['action']=='operator_selection' and e.get('adaptive',False) for e in events),evaluation_preferences_opened=any('evaluation_only_' in x for x in opens),input_trace_available=bool(opens)))
    name=a.batch or 'all'
    write(OUT/f'audit_{name}.json',dict(records=records,failures=failures,runs=runs))
    print('INDEPENDENT_AUDIT',name,'PACKAGES',len(records),'FAILURES',len(failures),flush=True)
    if failures:print(json.dumps(failures,indent=2));raise SystemExit(1)
if __name__=='__main__':main()
