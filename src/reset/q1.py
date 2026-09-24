"""Q1 recomputation in G2; existing exact per-service subset DP is retained."""
import json
import pandas as pd
from src.reset.geometry import OUT,tables,write
from src.q1.solve_q1 import solve_q1,max_safe_payload
def main():
    t=tables();dest=OUT/'q1';dest.mkdir(exist_ok=True)
    limits=[max_safe_payload(t['types'],t['geom'],g,s,.2) for g in t['types'].index for s in sorted(t['boxes'].service_id.unique())]
    pd.DataFrame(limits).to_csv(dest/'max_safe_payload.csv',index=False)
    flights=solve_q1(t['types'],t['geom'],t['boxes'],.2);flights.to_csv(dest/'q1_packings_rho20.csv',index=False)
    write(dest/'summary.json',dict(geometry='G2',sorties=len(flights),energy_kwh=float(flights.energy_kwh.sum()),sum_sortie_duration_s=float(flights.time_s.sum()),objective='per-service lexicographic minimum sorties, then energy, then summed duration',method='complete subset partition DP at each service; no fleet schedule in Q1'))
    print((dest/'summary.json').read_text(),flush=True)
if __name__=='__main__':main()
