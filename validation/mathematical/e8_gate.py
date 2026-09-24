"""Artifact-bound E8 review. Missing scenarios never receive a READY gate."""
from pathlib import Path
import hashlib,json
import pandas as pd

ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'results/q3/e8'
def read(p):return pd.read_csv(p,float_precision='round_trip')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def cmp(a,b,tol):return -1 if a<b-tol else 1 if a>b+tol else 0
def dominates(a,b):
    c=cmp(a['J_late'],b['J_late'],1e-4)
    if c==0:c=cmp(a['J_norm'],b['J_norm'],1e-9)
    rest=[cmp(a[k],b[k],1e-8 if k=='total_energy_kwh' else 1e-6) for k in ['joint_makespan_s','total_energy_kwh','transport_sorties','relay_sorties']]
    return c<=0 and all(v<=0 for v in rest) and (c<0 or any(v<0 for v in rest))

def main():
    frozen=json.loads((OUT/'frozen_input_manifest.json').read_text())
    for f,h in frozen['hashes'].items():assert digest(ROOT/f)==h,f'Frozen input changed: {f}'
    combined=[];scenarios=[];queries=[];artifacts=[]
    for gamma in [0,2,4,6]:
        d=OUT/f'gamma_{gamma:02d}';table=d/'provisional_pareto.csv'
        if not table.exists():
            status=dict(Gamma_C_db=gamma,status='GAMMA6_NO_WITNESS_FOUND',known_pareto_points=0,physical_infeasibility_proven=False)
            write(d/'scenario_status.json',status);scenarios.append(status);continue
        frame=read(table);records=[];catalog=json.loads((d/'budget_catalog.json').read_text())
        archive=json.loads((d/'search_archive.json').read_text()) if gamma else []
        for row in frame.to_dict('records'):
            sid=row['solution_id'];p=d/'solutions'/sid;v=json.loads((p/'validation_P01_0.5.json').read_text());m=json.loads((p/'joint_metrics_P01.json').read_text())
            assert v['status']=='E8_PLAN_INDEPENDENTLY_VALIDATED' and v['Gamma_C_db']==gamma
            assert v['hard_violations']==v['uncovered_sample_count']==0
            assert v['minimum_twohop_margin_db']>=gamma
            for f,h in v['artifact_sha256'].items():assert digest(ROOT/f)==h,f;artifacts.append(ROOT/f)
            for key in ['J_late','J_norm','joint_makespan_s','total_energy_kwh','transport_sorties','relay_sorties']:assert abs(row[key]-m[key])<1e-7,(sid,key)
            if gamma==0:
                original=json.loads((ROOT/'results/q3/e7/solutions'/sid.replace('Q3E8_G00_','Q3E7_')/'joint_metrics_P01.json').read_text())
                for key in ['J_late','J_norm','joint_makespan_s','total_energy_kwh','transport_sorties','relay_sorties']:assert m[key]==original[key],(sid,key)
            assert not any(dominates(other['metrics'],m) for other in archive),f'Archive dominates {sid}'
            relays=read(p/'relay_sorties_P01.csv')
            m.update(Gamma_C_db=gamma,solution_id=sid,minimum_twohop_margin_db=v['minimum_twohop_margin_db'],
                minimum_twohop_robust_slack_db=v['minimum_twohop_margin_db']-gamma,
                used_relay_uavs=len(relays.relay_id.unique()),used_energy_components=len(relays.energy_component_id.unique()),
                relay_active_s=float(relays.active_communication_s.sum()),relay_idle_s=float(relays.idle_hover_s.sum()),
                relay_flight_s=float(((relays.arrival_s-relays.takeoff_s)+(relays.return_s-relays.service_end_s)).sum()),
                relay_occupied_s=float((relays.uav_available_s-relays.preparation_start_s).sum()))
            records.append(m);combined.append(m)
        assert not any(i!=j and dominates(a,b) for i,a in enumerate(records) for j,b in enumerate(records))
        fine=json.loads((d/'solutions'/frame.iloc[0].solution_id/'validation_P01_0.25.json').read_text())
        assert fine['status']=='E8_PLAN_INDEPENDENTLY_VALIDATED' and fine['Gamma_C_db']==gamma
        for f,h in fine['artifact_sha256'].items():assert digest(ROOT/f)==h,f
        assert len(catalog['queries'])==15
        anchor=min(r['J_late'] for r in records)
        for q in catalog['queries']:
            assert abs(q['budget']-(1+q['epsilon'])*anchor)<1e-3
            chosen=next(r for r in records if r['solution_id']==q['solution_id']);assert chosen['J_late']<=q['budget']+1e-4
            key={'makespan':'joint_makespan_s','energy':'total_energy_kwh','relay_sorties':'relay_sorties'}[q['objective']]
            eligible=[r for r in records if r['J_late']<=q['budget']+1e-4]
            assert chosen[key]<=min(r[key] for r in eligible)+1e-6
            queries.append(dict(Gamma_C_db=gamma,**q,passed=True))
        pd.DataFrame(records).to_csv(d/'pareto_solutions.csv',index=False)
        status=dict(Gamma_C_db=gamma,status='SCENARIO_INDEPENDENTLY_VALIDATED',known_pareto_points=len(records),fine_step_s=.25,complete_global_pareto_frontier=False)
        write(d/'scenario_status.json',status);scenarios.append(status)
    common=read(OUT/'common_absolute_budget_comparison.csv')
    assert len(common)==36
    for q in common.to_dict('records'):
        eligible=[r for r in combined if r['Gamma_C_db']==q['Gamma_C_db'] and r['J_late']<=q['J_late_budget']+1e-4]
        key={'makespan':'joint_makespan_s','energy':'total_energy_kwh','relay_sorties':'relay_sorties'}[q['objective']]
        if eligible:
            assert q['status']=='VALIDATED_WITNESS'
            assert abs(q['value']-min(r[key] for r in eligible))<1e-6
            base=min(r[key] for r in combined if r['Gamma_C_db']==0 and r['J_late']<=q['J_late_budget']+1e-4)
            assert abs(q['delta']-(q['value']-base))<1e-6
        else:assert q['status']=='NO_KNOWN_WITNESS_NOT_INFEASIBILITY'
    replay=json.loads((OUT/'replay_checks.json').read_text());assert len(replay)==len(combined) and all(r['byte_identical'] for r in replay)
    assert {r['solution_id'] for r in replay}=={r['solution_id'] for r in combined}
    # The split representation must preserve the original guarded union exactly.
    d=OUT/'gamma_06';whole=read(d/'whole_gap_diagnostics/robust_tasks.csv').set_index('atomic_task_id');split=read(d/'robust_tasks.csv')
    for parent,rows in split.groupby('parent_gap_id'):
        rows=rows.sort_values('service_start_s');old=whole.loc[parent]
        assert rows.iloc[0].service_start_s==old.service_start_s and rows.iloc[-1].service_end_s==old.service_end_s
        assert all(abs(a-b)<1e-8 for a,b in zip(rows.service_end_s.iloc[:-1],rows.service_start_s.iloc[1:]))
    profile=read(OUT/'direct_profile_P01.csv');assert ((profile.direct_margin_db>=0)&(profile.direct_margin_db<2)).any()
    # Explicitly check the newly sub-threshold direct samples are assigned.
    for gamma in [2,4,6]:
        tasks=read(OUT/f'gamma_{gamma:02d}/robust_tasks.csv')
        for sid,part in profile[profile.direct_margin_db<gamma].groupby('transport_sortie_id'):
            windows=tasks[tasks.transport_sortie_id==sid];covered=pd.Series(False,index=part.index)
            for row in windows.itertuples():covered|=(part.time_s>=row.service_start_s-1e-7)&(part.time_s<=row.service_end_s+1e-7)
            assert covered.all(),(gamma,sid)
    pd.DataFrame(combined).to_csv(OUT/'pareto_family.csv',index=False);write(OUT/'budget_query_checks.json',queries)
    ready=all(s['status']=='SCENARIO_INDEPENDENTLY_VALIDATED' for s in scenarios)
    # Bind the review to all scientific outputs and code, excluding transient logs
    # and this self-referential gate file.
    files=[p for p in OUT.rglob('*') if p.is_file() and p.name!='validation.json' and p.suffix not in ['.log']]
    files+=list((ROOT/'src/q3').glob('e8_*.py'))+[Path(__file__),ROOT/'validation/mathematical/e8_validate.py']
    files += [ROOT/'results/q4/validation.json',ROOT/'results/project_status.json',ROOT/'docs/paper/MAIN_RESULTS_FREEZE_20260925.md',ROOT/'results/q3/e81/validation.json',ROOT/'results/q3/E81_CRITICAL_WINDOW_REPORT.md',ROOT/'validation/mathematical/test_e8_regressions.py',ROOT/'README.md',ROOT/'docs/model/Q3_ROBUSTNESS_E8_SEMANTICS.md',ROOT/'results/q3/E8_ROBUSTNESS_REPORT.md',ROOT/'results/q3/E8_GPT_SYNC.md']
    indices=json.loads((OUT/'robustness_indices.json').read_text())
    assert indices['Gamma_C_cert_db']==4 and indices['J_late_budget']==1000000
    for item in indices['costs']:
        selected=common[(common.Gamma_C_db==item['Gamma_C_db'])&(common.J_late_budget==1000000)]
        for objective,key in [('makespan','C_T_s'),('energy','C_E_kwh')]:
            assert abs(float(selected[selected.objective==objective].iloc[0].delta)-item[key])<1e-8
    ready_a=all(any(s['Gamma_C_db']==gamma and s['status']=='SCENARIO_INDEPENDENTLY_VALIDATED' for s in scenarios) for gamma in [0,2,4])
    rescue=json.loads((ROOT/'results/q3/e81/validation.json').read_text())
    assert rescue['status']=='GAMMA6_NO_WITNESS_FOUND' and rescue['one_diagnosis_one_expansion_one_search']
    result=dict(gate='E8_A_ROBUSTNESS_COST_READY' if ready_a else 'E8_A_VALIDATION_REQUIRED',
        gate_policy='USER_AUTHORIZED_SPLIT_E8A_REQUIRED_E8B_OPTIONAL',
        previous_gate_policy='ALL_FOUR_SCANNED_THRESHOLDS_REQUIRED',
        E8_A='DONE' if ready_a else 'NOT_READY',E8_B=rescue['status'],
        Gamma_C_cert_db=max(s['Gamma_C_db'] for s in scenarios if s['status']=='SCENARIO_INDEPENDENTLY_VALIDATED'),
        complete_scanned_family_ready=ready,Q4_blocked_by_E8B=False,
        validated_scenarios=[s['Gamma_C_db'] for s in scenarios if s['status']=='SCENARIO_INDEPENDENTLY_VALIDATED'],
        independently_validated_points=len(combined),scenarios=scenarios,budget_queries_checked=len(queries),
        replay_points=len(replay),common_absolute_budget_queries_checked=len(common),frozen_inputs_unchanged=True,whole_gap_split_union_preserved=True,
        new_subthreshold_direct_samples_covered=True,physical_infeasibility_proven=False,
        ns3_formal='OPTIONAL_LATE_NOT_STARTED',Q4=json.loads((ROOT/'results/q4/validation.json').read_text())['gate'],
        output_sha256={str(p.relative_to(ROOT)):digest(p) for p in sorted(set(files))})
    write(OUT/'validation.json',result);print(json.dumps({k:v for k,v in result.items() if k!='output_sha256'},indent=2))

if __name__=='__main__':main()
