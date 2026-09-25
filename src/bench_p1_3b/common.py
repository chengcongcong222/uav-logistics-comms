"""P1.3-B: frozen autonomous pool and isolated evidence paths."""
import hashlib,json,math,sys,time
from fractions import Fraction
from pathlib import Path
from collections import Counter,defaultdict
from src.reset.geometry import ROOT,tables,VERSION
from src.bench_p1.common import write,digest,signature

OUT=ROOT/'results/p1_3b'
BASE='62e8d6b72fe9305c00d228d820a065ddefb22524'
AXES=('makespan','sorties','J_norm','energy')
UNITS=10
def read(p):return json.loads(p.read_text())
def ceil_units(v):return math.ceil(Fraction.from_float(float(v))*UNITS)
def floor_units(v):return math.floor(Fraction.from_float(float(v))*UNITS)
def pool():return read(OUT/'inputs/pattern_pool.json')
def pattern_key(p):return (p['type'],tuple(p['sequence']),tuple(tuple(v) for v in p['counts']))
def multiplicity(p,classes):return min(len(classes[c]['boxes'])//n for c,n in p['counts'])
def latest(p,classes,epsilon=1e-4):
    return min(p['hard_latest'],*(classes[c]['key'][4]-p['delivery'][str(c)]+epsilon/(n*classes[c]['key'][5]) for c,n in p['counts']))
def install_input_guard():
    def hook(event,args):
        if event=='open' and args and isinstance(args[0],(str,bytes)):
            name=str(args[0])
            if '/results/xb1/' in name or '/results/quality_reset/' in name:
                raise RuntimeError('External structure read forbidden: '+name)
    sys.addaudithook(hook)

def admit():
    import shutil,subprocess
    from src.q2.evaluator import MissionEvaluator
    from src.common.charging import charge_time_s
    src=ROOT/'results/reset/pattern_pool.json';raw=src.read_bytes()
    assert raw==subprocess.check_output(['git','show',BASE+':results/reset/pattern_pool.json'],cwd=ROOT)
    (OUT/'inputs').mkdir(parents=True,exist_ok=True);shutil.copy2(src,OUT/'inputs/pattern_pool.json')
    p=pool();t=tables();ev=MissionEvaluator(t);classes=p['classes'];maximum={k:0. for k in ('energy','duration','prep','delivery','charge')}
    keys=[];tick=time.process_time()
    for row in p['patterns']:
        by=defaultdict(list)
        for c,n in row['counts']:by[classes[c]['key'][0]]+=classes[c]['boxes'][:n]
        m=ev.evaluate_mission(row['type'],dict(by),row['sequence']);assert m
        for name,val in [('energy',m.energy_kwh),('duration',m.relative_return_time),('prep',m.relative_takeoff_time)]:
            maximum[name]=max(maximum[name],abs(row[name]-val))
        for c,n in row['counts']:maximum['delivery']=max(maximum['delivery'],abs(row['delivery'][str(c)]-m.relative_delivery_times[classes[c]['key'][0]]))
        full=t['batteries'].set_index('uav_type').loc[row['type']].full_charge_time_s
        charge=charge_time_s(1-m.energy_kwh/t['types'].loc[row['type']].battery_energy_kwh,full)
        maximum['charge']=max(maximum['charge'],abs(charge-row['charge']));keys.append(pattern_key(row))
    assert len(set(keys))==len(keys) and max(maximum.values())<1e-7
    manifest=dict(base_commit=BASE,source=str(src.relative_to(ROOT)),sha256=digest(src),geometry=VERSION,
        actual_patterns=len(keys),single_stop=sum(len(x['sequence'])==1 for x in p['patterns']),two_stop=sum(len(x['sequence'])==2 for x in p['patterns']),other=0,
        class_count=len(classes),box_count=sum(len(c['boxes']) for c in classes),max_multiplicity_counts=dict(Counter(multiplicity(x,classes) for x in p['patterns'])),
        full_existing_pool=True,all_possible_transport_patterns=False,single_stop_enumerated_before_selection=p['single_stop_full_count'],
        generation_scope='296 retained of 1074 feasible single-stop patterns; neighbor/load-filtered 2607 two-stop patterns; no longer routes',
        autonomous_generator='src/reset/patterns.py',generator_sha256=digest(ROOT/'src/reset/patterns.py'),
        source_inputs={str(Path(f).relative_to(ROOT)):digest(Path(f)) for f in p['inputs_read']},
        all_pattern_physics_crosscheck=dict(evaluator='Original MissionEvaluator, not an independent solver/geometry proof',max_absolute_residuals=maximum,cpu_s=time.process_time()-tick),
        external_structures_read=False,external_targets_in_solver=False)
    write(OUT/'pool_manifest.json',manifest);print('POOL_ADMITTED',len(keys),manifest['single_stop'],manifest['two_stop'],flush=True)

if __name__=='__main__':install_input_guard();admit()
