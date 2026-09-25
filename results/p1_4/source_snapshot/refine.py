"""One follow-up energy run after a tighter budget reveals fewer trips."""
from src.bench_p1_4.search import *

def main():
    assert (OUT/'transport_search_complete.json').exists();install_input_guard()
    prior=read(OUT/'representatives/F13.json')
    rows=execute(6350,'energy',75,count=24,prior=prior['trips'])
    records=read(OUT/'candidate_index.json');known={r['signature'] for r in records}
    for row in rows[:2]:
        if row['structure_signature'] not in known:
            records.append(export_candidate(row,f'F{len(records)+1:02d}','B6350_energy_N24_repair_after_tighter_budget_discovery'))
            known.add(row['structure_signature'])
    write(OUT/'candidate_index.json',records)
    write(OUT/'refinement_reason.json',dict(reason='6250s run discovered 24 trips after the earlier 6350s run found only 25; carry the tighter-budget incumbent into the looser budget and refine energy at 24 trips.',models=1,complete=True))
if __name__=='__main__':main()
