"""Contained continuous Q3 challenges with exact energy in a fixed event-order cell.

Keep the incumbent's communication endpoint order. In this declared cell,
the union duration is affine, so idle hover is not overcharged as transmission.
Resource repair is bounded; this still does not certify nondominance.
"""
import json,time
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix,csr_matrix,vstack
from src.reset.geometry import OUT,write
from src.reset.q3 import configure,ResetEngine,export_new
from src.q3.e7_core import Timing
from src.q3.e7_pareto import dominates

def addto(row,key,value):row[key]=row.get(key,0.)+value
class Cell(Timing):
    def __init__(self,e,pid,seed,objective,strict=False):
        super().__init__(e,pid,seed['groups'],objective=objective,late_budget=None)
        self.exact_c=np.zeros(self.dim);self.exact_constant=self.energy_constant
        old=list(zip(self.rows,self.upper));self.rows=[];self.upper=[]
        # Replace the inherited all-active-power span cap by the exact cell cap.
        for row,rhs in old:
            if any(row=={self.n+2*j+1:1,self.n+2*j:-1} for j in range(self.k)):continue
            self.rows.append(row);self.upper.append(rhs)
        def add(row,cap):self.rows.append({k:v for k,v in row.items() if v});self.upper.append(cap)
        for j,g in enumerate(seed['groups']):
            events=[]
            for aid in g['task_ids']:
                a=e.atoms.loc[aid];i=self.idx[a.transport_sortie_id];shift=seed['shifts'][a.transport_sortie_id]
                events += [(float(a.service_start_s)+shift,0,i,float(a.service_start_s)),(float(a.service_end_s)+shift,1,i,float(a.service_end_s))]
            events.sort()
            for a,b in zip(events[:-1],events[1:]):
                row={};addto(row,a[2],1);addto(row,b[2],-1);add(row,b[3]-a[3])
            for var,event in [(self.n+2*j,events[0]),(self.n+2*j+1,events[-1])]:
                row={var:1};addto(row,event[2],-1);add(row,event[3]);add({k:-v for k,v in row.items()},-event[3])
            active={};active_constant=0.;depth=0
            for event in events:
                if event[1]==0:
                    if depth==0:left=event
                    depth+=1
                else:
                    depth-=1
                    if depth==0:
                        addto(active,event[2],1);addto(active,left[2],-1);active_constant+=event[3]-left[3]
            assert depth==0
            hover=e.pr['hover_power_kw']/3600;comm=e.pr['comm_power_kw']/3600
            energy={self.n+2*j:-hover,self.n+2*j+1:hover}
            for i,v in active.items():addto(energy,i,v*comm)
            c=active_constant*comm;static=e.energy(e.sites[g['site_id']],0)['total_energy_kwh']
            add(energy,(1-e.pr['rho'])*e.pr['energy_kwh']-static-c)
            for i,v in energy.items():self.exact_c[i]+=v
            self.exact_constant+=c
        m=seed['metrics'];self.bounds[self.makespan]=(0,m['joint_makespan_s']+1e-7)
        add({i:float(v) for i,v in enumerate(self.exact_c) if v},m['total_energy_kwh']-m['transport_energy_kwh']-self.exact_constant+1e-9)
        if not strict:
            normconst=np.sum(self.weights*self.original_delivery/self.deadlines)/sum(self.weights)
            add({i:float(v) for i,v in enumerate(self.norm_c) if v},m['J_norm']-normconst+1e-10)
        add({i:float(v) for i,v in enumerate(self.late_c) if v},max(0,m['J_late']-(1e-3 if strict else 0))+1e-7)
        self.budget=max(0,m['J_late']-(1e-3 if strict else 0))+1e-7
    def lp(self,sequences,cuts):
        rows=list(self.rows);caps=list(self.upper)
        for seq in sequences:
            for a,b in zip(seq[:-1],seq[1:]):rows.append({self.n+2*a+1:1,self.n+2*b:-1});caps.append(-self.tails[a]-self.leads[b])
        for i,j,gap in cuts:rows.append({i:1,j:-1});caps.append(-gap)
        rr=[];cc=[];vv=[]
        for i,row in enumerate(rows):
            for j,v in row.items():rr.append(i);cc.append(j);vv.append(v)
        a=coo_matrix((vv,(rr,cc)),shape=(len(rows),self.dim)).tocsr();b=np.array(caps)
        c=self.late_c.copy()
        if self.objective=='energy':c=self.exact_c.copy()
        elif self.objective=='makespan':c*=0;c[self.makespan]=1
        r=linprog(c,A_ub=a,b_ub=b,bounds=self.bounds,method='highs');self.lp_solves+=1
        if not r.success:return None
        if self.objective=='timeliness':
            v=linprog(self.norm_c,A_ub=vstack([a,csr_matrix(c)]),b_ub=np.r_[b,c@r.x+1e-7],bounds=self.bounds,method='highs');self.lp_solves+=1
            if v.success:r=v
        return r.x,float(c@r.x)+(self.exact_constant if self.objective=='energy' else 0)
    def seed_vector(self,seed):
        x=np.zeros(self.dim)
        for sid,v in seed['shifts'].items():x[self.idx[sid]]=v
        for j,r in enumerate(seed['selected']):x[self.n+2*j]=r['service_start_s'];x[self.n+2*j+1]=r['service_end_s']
        times=self.original_delivery+np.array([seed['shifts'][s] for s in self.delivery.sortie_id]);x[self.late_offset:self.makespan]=np.maximum(0,times-self.deadlines);x[self.makespan]=seed['metrics']['joint_makespan_s']
        return x
def main():
    configure();records=[]
    for pid in ['A03','A11','B01','B02','AN01']:
        e=ResetEngine(pid)
        for path in sorted((OUT/'q3'/pid/'solutions').glob('*/witness.json')):
            if '_CC' in path.parent.name:continue
            seed=json.loads(path.read_text());attempts=[];winner=None
            for strict in [False]+([True] if seed['metrics']['J_late']>1e-4 else []):
                for objective in ['timeliness','makespan','energy']:
                    model=Cell(e,pid,seed,objective,strict);x=model.seed_vector(seed)
                    residual=float(max(sum(x[i]*v for i,v in row.items())-cap for row,cap in zip(model.rows,model.upper)))
                    energy=float(model.exact_c@x+model.exact_constant);assert abs(energy-seed['metrics']['relay_energy_kwh'])<1e-7
                    if not strict:assert residual<1e-5,(path.parent.name,residual)
                    tick=time.monotonic();ans=model.solve(seed['sequences'],node_limit=5)
                    improved=ans is not None and dominates(ans['metrics'],seed['metrics'])
                    attempts.append(dict(branch='strictly_lower_lateness' if strict else 'equal_lateness',objective=objective,original_in_linear_domain=residual<1e-5,original_max_constraint_residual=residual,exact_energy_at_original_kwh=energy,wall_s=time.monotonic()-tick,lp_solves=model.lp_solves,node_limit=5,found_feasible=ans is not None,dominates=improved))
                    if improved:winner=ans;break
                if winner:break
            r=dict(source=path.parent.name,domain='fixed transport structure, sites, relay sequences and communication endpoint order; affine exact active/idle energy; original included in equal-lateness cell; free transport resources',attempts=attempts,certificate='NO_PROOF: bounded clique repair; endpoint-order cell only')
            if winner:
                ident=path.parent.name+'_CC';export_new(e,winner,ident);r.update(challenger=ident,status='DOMINATING_CANDIDATE_PENDING_INDEPENDENT_VALIDATION')
            else:r['status']='NO_DOMINATOR_FOUND_IN_CONTAINED_CELL'
            records.append(r);write(OUT/'contained_cell_challenges.json',records);print(r['source'],r['status'],flush=True)
if __name__=='__main__':main()
