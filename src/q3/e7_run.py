"""Rebuild the bounded E7 experiment from its frozen E6 input and validate it."""
import os,subprocess,sys
for name in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[name]='1'
from concurrent.futures import ThreadPoolExecutor
from src.q3.e7_pareto import *
from src.q3.e7_replay import check_all,choose


def command(script,*args):
    subprocess.run([sys.executable,str(ROOT/script),*args],check=True,cwd=ROOT)


def main():
    import hashlib
    for name,digest in json.loads((OUT/'input_manifest.json').read_text())['hashes'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    write_json(OUT/'validation.json',dict(gate='E7_VALIDATION_REQUIRED',reason='Experiment rebuild started'))
    e=engine_for();tick=time.monotonic();free=solve_seed(e,node_limit=160);assert free is not None
    free['search_runtime_s']=time.monotonic()-tick;write_json(OUT/'free_order_seed.json',free)
    export_solution(e,free,'L1_RESOURCE_ABLATION')
    best,archive,info=search(e,free,rounds=4,repairs_per_round=28,label='TIMELINESS')
    write_json(OUT/'best_timeliness.json',best);write_json(OUT/'timeliness_archive.json',archive);write_json(OUT/'timeliness_search.json',info)
    from src.q3.e7_pareto import main as pareto_main
    pareto_main()
    best,archive,info=search(e,baseline('P01'),rounds=7,repairs_per_round=28,label='FIXED_ORDER_CONTROL',fixed_transport_order=True)
    best['level']='FIXED_RESOURCE_ORDER_CONTROL'
    write_json(OUT/'fixed_order_control.json',best);write_json(OUT/'fixed_order_control_archive.json',archive);write_json(OUT/'fixed_order_control_search.json',info)
    export_solution(e,best,'FIXED_ORDER_CONTROL')
    check_all();command(Path('validation/mathematical/e7_test_regressions.py'))
    ids=list(read(OUT/'provisional_pareto.csv').solution_id)+['L1_RESOURCE_ABLATION','FIXED_ORDER_CONTROL']
    def audit(sid):command(Path('validation/mathematical/e7_validate.py'),'--directory',str(OUT/'solutions'/sid))
    with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(audit,ids))
    command(Path('validation/mathematical/e7_validate.py'),'--directory',str(OUT/'solutions'/ids[0]),'--step','.25')
    command(Path('validation/mathematical/e7_gate.py'))
    checks=[]
    for q in json.loads((OUT/'budget_catalog.json').read_text())['queries']:
        sid,_,_=choose(q['epsilon'],q['objective']);assert sid==q['solution_id']
        checks.append(dict(epsilon=q['epsilon'],objective=q['objective'],solution_id=sid,status='PASS'))
    write_json(OUT/'budget_query_checks.json',dict(status='ALL_15_BUDGET_QUERIES_REPRODUCIBLE',queries=checks))
    command(Path('validation/mathematical/e7_gate.py'))


if __name__=='__main__':
    for name in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[name]='1'
    main()
