"""Recheck frozen F13 from autonomous pattern membership to full-flight physics."""
import os
os.environ['PYTHONDONTWRITEBYTECODE']='1'
import sys,shutil,math
from collections import Counter,defaultdict
import numpy as np
import pandas as pd
from pyproj import Transformer
from src.p1_5a.common import *
def csv(p):return pd.read_csv(p,float_precision='round_trip')
def pool_chain():
    p=read(ROOT/'results/p1_3b/inputs/pattern_pool.json')
    manifest=read(ROOT/'results/p1_3b/pool_manifest.json')
    assert len(p['patterns'])==2903
    assert digest(ROOT/'results/p1_3b/inputs/pattern_pool.json')==manifest['sha256']==digest(ROOT/'results/reset/pattern_pool.json')
    for rel,h in manifest['source_inputs'].items():assert digest(ROOT/rel)==h,rel
    assert digest(ROOT/manifest['autonomous_generator'])==manifest['generator_sha256']
    from src.reset.geometry import tables
    from src.q2.evaluator import MissionEvaluator
    from src.common.charging import charge_time_s
    t=tables();ev=MissionEvaluator(t);classes=p['classes']
    boxclass={b:i for i,c in enumerate(classes) for b in c['boxes']}
    assert set(boxclass)==set(t['boxes'].box_id) and len(boxclass)==80
    for i,c in enumerate(classes):
        for bid in c['boxes']:
            b=t['boxes'].set_index('box_id').loc[bid]
            hd=ev.hard_deadline(bid)
            actual=[b.service_id,float(b.mass_kg),float(b.volume_m3),hd if hd is not None else -1.,float(b.expected_deadline_s),float(b.priority_weight)]
            assert actual==c['key']
    residual=0.
    lookup={}
    for i,r in enumerate(p['patterns']):
        by=defaultdict(list)
        for c,n in r['counts']:by[classes[c]['key'][0]]+=classes[c]['boxes'][:n]
        m=ev.evaluate_mission(r['type'],dict(by),r['sequence']);assert m
        vals=[abs(m.energy_kwh-r['energy']),abs(m.relative_return_time-r['duration']),abs(m.relative_takeoff_time-r['prep'])]
        vals += [abs(m.relative_delivery_times[classes[c]['key'][0]]-r['delivery'][str(c)]) for c,n in r['counts']]
        residual=max(residual,*vals)
        lookup[(r['type'],tuple(r['sequence']),tuple(map(tuple,r['counts'])))]=i
    assert residual<1e-7 and len(lookup)==2903
    source_missions=read(SOURCE/'q2/pareto_schedules/F13/missions.json')
    rep=read(ROOT/'results/p1_4/representatives/F13.json')
    remaining={i:list(c['boxes']) for i,c in enumerate(classes)}
    membership=[]
    for j,(m,tr) in enumerate(zip(source_missions,sorted(rep['trips'],key=lambda x:(x['pattern'],x['copy']))),1):
        key=(m['uav_type'],tuple(m['service_sequence']),tuple(sorted(Counter(boxclass[b] for b in m['box_ids']).items())))
        assert lookup[key]==tr['pattern']
        generated=[]
        for c,n in p['patterns'][tr['pattern']]['counts']:
            generated += [remaining[c].pop(0) for _ in range(n)]
        assert set(generated)==set(m['box_ids'])
        assert m['mission_id']==f'M{j:03d}'
        assert abs(m['preparation_start_s']-tr['start_units']/10)<1e-8
        membership.append(dict(sortie_id=m['mission_id'],pattern_index=tr['pattern'],box_ids=sorted(generated)))
    assert len(membership)==24 and not any(remaining.values())
    # Verify all structural warm starts also belong to this autonomous pool.
    hints={}
    for name,ms in [('A11',read(ROOT/'results/reset/q2/pareto_schedules/A11/missions.json'))]:
        indices=[]
        for m in ms:
            key=(m['uav_type'],tuple(m['service_sequence']),tuple(sorted(Counter(boxclass[b] for b in m['box_ids']).items())))
            indices.append(lookup[key])
        hints[name]=indices
    t01=read(ROOT/'results/p1_3b/transport_runs/makespan_v3/config.json')
    assert t01['no_external_threshold'] and t01['near_optimal_cap'] is None
    assert digest(ROOT/t01['hint']['source'])==t01['hint']['sha256']
    tr=read(ROOT/'results/p1_3b/representatives/T01.json')
    assert all(0<=r['pattern']<2903 for r in tr['trips'])
    cfg=read(ROOT/'results/p1_4/transport_runs/B6250_energy_N24/config.json')
    assert cfg['pool_sha256']==manifest['sha256'] and cfg['exact_transport_sorties']==24
    result=dict(status='VERIFIED',patterns=2903,physical_max_residual=residual,box_count=80,sorties=24,
        membership=membership,warm_start_pool_membership=hints,T01_config=t01,
        generation='Frozen autonomous pool, deterministic box consumption, saved CP incumbent',
        threshold_basis='P1.4 declared internal epsilon budget relative to already verified autonomous fast anchor; no external performance value used in this admission')
    write(OUT/'provenance/pattern_chain.json',result)

def incumbent_origin():
    rep=read(ROOT/'results/p1_4/representatives/F13.json')
    source=ROOT/'results/p1_4/transport_runs/B6250_energy_N24/candidate_structures.json'
    rows=read(source)
    matches=[r for r in rows if r['structure_signature']==rep['signature']]
    assert len(matches)==1 and matches[0]['trips']==rep['trips']
    write(OUT/'provenance/incumbent_origin.json',dict(status='PASSED',source=str(source.relative_to(ROOT)),
        sha256=digest(source),structure_signature=rep['signature'],exact_trip_and_start_match=True,
        source_config_sha256=digest(source.parent/'config.json'),
        scope='Saved autonomous CP incumbent; no search rerun'))

def site_chain():
    prov=read(ROOT/'results/p1_preflight/site_provenance.json')
    coords={};sources={}
    for rel,h in prov['sources'].items():
        assert digest(ROOT/rel)==h
        frame=csv(ROOT/rel);sources[rel]=h
        for r in frame.itertuples():
            coords.setdefault((round(r.x_m,5),round(r.y_m,5),round(r.agl_m,5)),[]).append(rel)
    shared=read(ROOT/'results/p1_preflight/inputs/common_sites.json')
    assert len(shared)==118
    for s in shared:assert (round(s['x_m'],5),round(s['y_m'],5),round(s['agl_m'],5)) in coords
    selected=csv(SOURCE/'q3/F13/solutions'/IDENT/'candidate_sites_F13.csv')
    rows=[]
    for s in selected.itertuples():
        key=(round(s.x_m,5),round(s.y_m,5),round(s.agl_m,5))
        assert key in coords
        assert any(max(abs(s.x_m-x['x_m']),abs(s.y_m-x['y_m']),abs(s.agl_m-x['agl_m']))<1e-5 for x in shared)
        rows.append(dict(site_id=s.site_id,x_m=s.x_m,y_m=s.y_m,agl_m=s.agl_m,autonomous_predecessors=coords[key]))
    write(OUT/'provenance/site_chain.json',dict(status='VERIFIED',frozen_sites=118,selected=rows,sources=sources,
        scope='Existing autonomous E5.2/E6/E8 coordinate lineage; no new station optimization or external structure admission'))

def geometry_check():
    sys.path.insert(0,str(ROOT/'validation/mathematical'))
    from reset_geometry_validate import independent_max
    from src.common.terrain import Dem
    dem=Dem();nodes=csv(GEOMETRY/'nodes.csv').set_index('node_id');geo=csv(GEOMETRY/'route_geometry.csv');cache={};rows=[]
    for r in geo.itertuples():
        key=tuple(sorted([r.from_id,r.to_id]))
        if key not in cache:
            a=nodes.loc[r.from_id];b=nodes.loc[r.to_id]
            cache[key]=independent_max(dem,(a.x_m,a.y_m),(b.x_m,b.y_m))
        z=cache[key];assert abs(z-r.max_dem_elevation_m)<1e-6
        rows.append(dict(from_id=r.from_id,to_id=r.to_id,independent_max_dem_m=z))
    pd.DataFrame(rows).to_csv(OUT/'provenance/independent_geometry.csv',index=False)
    write(OUT/'provenance/geometry_check.json',dict(status='PASSED',directed_legs=len(rows),method='Independent native DEM row-strip clipping; no prior comparison geometry read'))

def audit_f13():
    sys.path.insert(0,str(ROOT/'validation/mathematical'))
    import reset_q3_validate as q3
    from e52_validate_candidates import IndependentAudit,Dem,load_comm_params,pair_lmax,load_relay_params
    class F13Only(q3.Checker):
        def __init__(self):
            self.dem=Dem();self.radio,_=load_comm_params();self.budgets=pair_lmax();self.params=load_relay_params()
            self.tf=Transformer.from_crs(32649,4326,always_xy=True)
            node=csv(ROOT/'data/processed/nodes.csv').set_index('node_id').loc['O01']
            raw=read(ROOT/'data/processed/communication_parameters.json')
            hg=raw['endpoints']['固定网关 G01']['天线离地高度（m）']['value']
            self.origin=np.array([node.x_m,node.y_m,node.ground_elevation_m],float)
            self.gateway=self.origin+np.array([0,0,hg]);self.gateway_ll=(*self.tf.transform(*self.gateway[:2]),self.gateway[2])
            self.traces={};self.samples=0;self.refinements=0;self.geocache={}
            frame=csv(OUT/'execution/q2/pareto_schedules/F13/transport_trace.csv')
            for sid,r in frame.groupby('task_id'):
                assert not (r.groupby('time')[['x','y','z']].nunique()>1).any().any()
                r=r.sort_values('time').drop_duplicates('time')
                self.traces['F13',sid]=(r.time.to_numpy(float),r[['x','y','z']].to_numpy(float))
    q3.audit.IndependentAudit=F13Only;q3.audit.Q3=OUT/'execution/q3';q3.audit.DATA=GEOMETRY;q3.audit.OUT=PACKAGE
    v=q3.audit.validate_plan('F13',.5)
    assert v['hard_violations']==v['uncovered_sample_count']==v['J_late']==0
    v['status']='F13_INDEPENDENTLY_READMITTED'
    write(PACKAGE/'validation_0.5.json',v)
    m=read(PACKAGE/'joint_metrics_F13.json')
    assert m['transport_sorties']==24 and m['relay_sorties']==3
    assert abs(m['joint_makespan_s']-6245.793309522221)<1e-6 and abs(m['total_energy_kwh']-70.26433200872623)<1e-7
    assert m['Gamma_C_db']==0
    return v,m

def main():
    install_guard();OUT.mkdir(exist_ok=True);(OUT/'provenance').mkdir(exist_ok=True)
    try:
        pool_chain();incumbent_origin();print('PATTERN_CHAIN_PASSED',flush=True)
        site_chain();print('SITE_CHAIN_PASSED',flush=True)
        geometry_check();print('GEOMETRY_PASSED',flush=True)
        original=SOURCE/'q3/F13/solutions'/IDENT
        for rel,h in read(original/'input_manifest.json')['hashes'].items():assert digest(ROOT/rel)==h
        src=SOURCE/'q2/pareto_schedules/F13';dst=OUT/'execution/q2/pareto_schedules/F13'
        dst.mkdir(parents=True,exist_ok=True)
        for p in src.iterdir():
            if p.is_file() and p.name!='validation.json':shutil.copyfile(p,dst/p.name)
        PACKAGE.mkdir(parents=True,exist_ok=True)
        for p in original.iterdir():
            if p.is_file():shutil.copyfile(p,PACKAGE/p.name)
        safe_inputs=[p for p in dst.iterdir() if p.is_file()]+[p for p in GEOMETRY.iterdir() if p.suffix=='.csv' and p.name not in ['version_comparison.csv','independent_geometry.csv']]
        write(PACKAGE/'input_manifest.json',dict(hashes=hashes(safe_inputs),lineage='F13_FROZEN_AUTONOMOUS_EXECUTION'))
        v,m=audit_f13();print('FULL_FLIGHT_PASSED',v['full_flight_samples'],flush=True)
        write(PACKAGE/'plan_status_F13.json',dict(status='CURRENT_AUTONOMOUS_MAIN_CANDIDATE',validation_sha256=digest(PACKAGE/'validation_0.5.json')))
        write(OUT/'F13_readmission.json',dict(status='CURRENT_AUTONOMOUS_MAIN_CANDIDATE',base_commit=BASE,
            solution_id=IDENT,metrics={k:m[k] for k in ['J_late','J_norm','joint_makespan_s','total_energy_kwh','transport_energy_kwh','relay_energy_kwh','transport_sorties','relay_sorties','Gamma_C_db']},
            independent_validation=v,autonomous_structure_chain=True,external_structure_data_read=False,autonomous_warm_start_lineage_checked=True,
            global_optimum_proven=False,complete_pareto_front_proven=False,
            original_inputs=hashes([p for p in original.iterdir() if p.is_file()]+[src/'missions.json']),
            output_hashes=hashes([p for p in PACKAGE.iterdir() if p.is_file()]),
            validation_scope='Numerical whole-flight 0.5 s + boundaries and 0.1 s boundary refinement; no analytic continuous-time radio proof'))
    except Exception as exc:
        write(OUT/'F13_readmission.json',dict(status='P1_5A_F13_READMISSION_BLOCKED',error=repr(exc)))
        write(OUT/'gate.json',dict(status='P1_5A_F13_READMISSION_BLOCKED',error=repr(exc)))
        raise
    finally:
        write(OUT/'provenance/read_log.json',dict(files=sorted(READS),hashes=hashes([ROOT/p for p in sorted(READS) if (ROOT/p).is_file()]),guard='Exact allowed historical data paths; writes only results/p1_5a'))
if __name__=='__main__':main()
