#!/usr/bin/env python3
"""Additional 0.25 s audit of ALL E52 pairs, motivated by small margin cases."""
import hashlib
import json
import time
import pandas as pd

from e52_validate_candidates import IndependentAudit, Q3


def main():
    begin=time.monotonic()
    checker=IndependentAudit()
    pairs=pd.read_csv(Q3/'relay_task_candidates_e52.csv')
    sites=pd.read_csv(Q3/'relay_sites_e52.csv').set_index('site_id')
    records=[]
    for i,row in enumerate(pairs.itertuples(),1):
        margin=checker.interval((row.pareto_id,row.transport_sortie_id),sites.loc[row.site_id],
                                row.service_start_s,row.service_end_s,step=0.25)
        records.append(dict(atomic_task_id=row.atomic_task_id,site_id=row.site_id,
                            min_access_margin_025s_db=margin,
                            delta_from_05s_db=margin-row.min_access_margin_db,valid=bool(margin>=0)))
        if i%20==0: print(f'0.25s audit {i}/{len(pairs)}',flush=True)
    frame=pd.DataFrame(records)
    frame.to_csv(Q3/'e52_rescue/sampling_sensitivity.csv',index=False)
    report=dict(step_s=0.25,all_pairs_checked=len(frame),violations=int((~frame.valid).sum()),
                minimum_access_margin_db=float(frame.min_access_margin_025s_db.min()),
                maximum_absolute_margin_difference_db=float(frame.delta_from_05s_db.abs().max()),
                samples=checker.samples,runtime_s=time.monotonic()-begin,
                candidate_sha256=hashlib.sha256((Q3/'relay_task_candidates_e52.csv').read_bytes()).hexdigest(),
                status='E52_QUARTER_SECOND_CHECK_VALID' if frame.valid.all() else 'E52_QUARTER_SECOND_CHECK_FAILED')
    (Q3/'e52_rescue/sampling_sensitivity.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2),flush=True)
    if not frame.valid.all(): raise SystemExit(1)


if __name__=='__main__':main()
