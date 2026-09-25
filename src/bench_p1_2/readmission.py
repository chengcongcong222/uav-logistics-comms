"""Re-admit autonomous A11 in a private copy; stop on any validation failure."""
import json, shutil, sys, time
from pathlib import Path
from src.bench_p1.common import ROOT, write, digest

OUT = ROOT / 'results/p1_2'

def main():
    root = OUT / 'warm_readmission'
    if root.exists():
        raise RuntimeError('Refuse to overwrite readmission evidence')
    pid = 'A11'
    source = ROOT / 'results/reset'
    base = root / 'q2/pareto_schedules' / pid
    package = root / 'q3/A11/solutions/A11_Q3_001'
    original = source / 'q3/A11/solutions/A11_Q3_001'
    manifest = {str(p.relative_to(ROOT)): digest(p) for folder in [original, source / 'q2/pareto_schedules/A11'] for p in folder.iterdir() if p.is_file()}
    shutil.copytree(source / 'q2/pareto_schedules/A11', base)
    shutil.copytree(original, package)
    record = dict(mode='DIAGNOSTIC_WARM', source='AUTONOMOUS_INTERNAL_G2_A11', source_hashes=manifest,
                  formal_cold_start_eligible=False, physical_model='G2', Gamma_C_db=0,
                  validator='P1 unchanged reset_q3_validate/e8_validate', step_s=0.5)
    sys.path.insert(0, str(ROOT / 'validation/mathematical'))
    import reset_q3_validate as q3
    q3.OUT = root
    q3.audit.IndependentAudit = q3.Checker
    q3.audit.Q3 = root / 'q3'
    q3.audit.DATA = source / 'geometry'
    q3.audit.OUT = package
    tick = time.process_time()
    try:
        result = q3.audit.validate_plan(pid, .5)
        write(package / 'validation_0.5.json', dict(result, status='P1_Q3_INDEPENDENTLY_VALIDATED'))
        record.update(status='READMITTED', audit=result,
                      metrics=json.loads((package / 'joint_metrics_A11.json').read_text()))
    except Exception as exc:
        record.update(status='REJECTED', error=repr(exc))
    record['audit_cpu_s'] = time.process_time() - tick
    write(OUT / 'warm_seed_readmission.json', record)
    print(record['status'], record.get('error', ''), flush=True)
    if record['status'] != 'READMITTED':
        raise SystemExit(1)

if __name__ == '__main__':
    main()
