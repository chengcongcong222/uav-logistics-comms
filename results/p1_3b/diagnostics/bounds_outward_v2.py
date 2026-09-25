"""Outer continuous-time relaxation of the entire pool; rational LP bounds."""
import math,time,warnings
from fractions import Fraction
import numpy as np
from scipy.optimize import linprog,milp,Bounds,LinearConstraint
from src.bench_p1_3a.model import LinearModel,lp_form,rational_lagrangian_bound
from src.bench_p1_3b.common import *

F=lambda v:Fraction.from_float(float(v))
def down(v):return math.nextafter(float(v),-math.inf)
def up(v):return math.nextafter(float(v),math.inf)
def safe_latest(r,classes):
    return up(min([F(r['hard_latest'])]+[F(classes[c]['key'][4])-F(r['delivery'][str(c)])+F(1e-4)/(n*F(classes[c]['key'][5])) for c,n in r['counts']]))

def build(p,t):
    patterns=p['patterns'];classes=p['classes'];m=LinearModel();xs=[];starts=[];lateness=[]
    horizon=max(max(0,safe_latest(r,classes))+r['duration'] for r in patterns)+1.
    T=m.var('makespan',0,horizon);den=sum(len(c['boxes'])*c['key'][5] for c in classes)
    objectives={axis:{} for axis in AXES};objectives['makespan'][T]=1
    for i,r in enumerate(patterns):
        cap=safe_latest(r,classes);ub=multiplicity(r,classes) if cap>=0 else 0
        x=m.var(f'pattern_count_{i}',0,ub,integer=True);s=m.var(f'sum_preparation_starts_{i}',0,max(0,cap)*ub)
        xs.append(x);starts.append(s);m.row({s:1,x:-max(0,cap)},hi=0,label='aggregate_latest_start')
        m.row({s:1,x:r['duration'],T:-max(1,ub)},hi=0,label='sum_completion_bounded_by_max_multiplicity_T')
        objectives['sorties'][x]=1;objectives['energy'][x]=r['energy']
        objectives['J_norm'][x]=down(sum(n*F(classes[c]['key'][5])*F(r['delivery'][str(c)])/F(classes[c]['key'][4]) for c,n in r['counts'])/F(den))
        objectives['J_norm'][s]=down(sum(n*F(classes[c]['key'][5])/F(classes[c]['key'][4]) for c,n in r['counts'])/F(den))
        for c,n in r['counts']:
            w=classes[c]['key'][5]*n;ell=m.var(f'aggregate_late_{i}_{c}',0,1e-4/w);lateness.append((ell,w))
            m.row({s:1,x:r['delivery'][str(c)]-classes[c]['key'][4],ell:-1},hi=0,label='Jensen_lower_bound_on_total_lateness')
    m.row(dict(lateness),hi=1e-4,label='ORIGINAL_ZERO_LATENESS_LAYER')
    for c,cl in enumerate(classes):m.eq({xs[i]:dict(r['counts']).get(c,0) for i,r in enumerate(patterns)},len(cl['boxes']),'EXACT_CLASS_COVER')
    for typ in 'ABC':
        ids=[i for i,r in enumerate(patterns) if r['type']==typ];n=int((t['uavs'].uav_type==typ).sum());b=int(t['batteries'].set_index('uav_type').loc[typ].battery_pool_count)
        charge=max(patterns[i]['charge'] for i in ids)
        m.row({**{xs[i]:patterns[i]['duration'] for i in ids},T:-n},hi=0,label='UAV_WORKLOAD')
        m.row({**{xs[i]:down(F(patterns[i]['duration'])+F(patterns[i]['charge'])-F(patterns[i]['prep'])) for i in ids},T:-b},hi=up(b*F(charge)),label='BATTERY_WORKLOAD_WITH_TAIL')
        # Necessary parallel-machine completion inequalities. Tangents to W^2
        # yield globally valid linear inequalities, not a schedule proxy.
        for q in range(1,33):
            w0=q*n*horizon/32;scale=max(r['duration'] for r in patterns)
            row={starts[i]:down(-F(patterns[i]['duration'])/F(scale)) for i in ids}
            row.update({xs[i]:down((F(w0)/n*F(patterns[i]['duration'])-F(patterns[i]['duration'])**2/2)/F(scale)) for i in ids})
            m.row(row,hi=up(F(w0)**2/(2*n*F(scale))),label='PARALLEL_MACHINE_WORKLOAD_SQUARE_TANGENT')
        deadlines=sorted({float(c['key'][4]) for c in classes})
        for h in deadlines:
            for resource,count in [('uav',n),('battery',b)]:
                row={}
                for i in ids:
                    r=patterns[i];offset=0 if resource=='uav' else r['prep'];length=r['duration'] if resource=='uav' else r['duration']+r['charge']-r['prep']
                    exact_length=F(r['duration']) if resource=='uav' else F(r['duration'])+F(r['charge'])-F(r['prep'])
                    forced=max(F(0),min(exact_length,F(h)-F(safe_latest(r,classes))-F(offset)));row[xs[i]]=down(forced) if forced>0 else 0
                m.row(row,hi=count*h,label='LATEST_START_FORCED_PREFIX_WORKLOAD')
    costs={}
    for axis,terms in objectives.items():
        c=np.zeros(len(m.names))
        for j,v in terms.items():c[j]=v
        costs[axis]=c
    return m,costs

def main():
    install_input_guard();warnings.filterwarnings('ignore',message='Unrecognized options detected')
    dest=OUT/'bounds';dest.mkdir(exist_ok=True);tick=time.process_time();m,costs=build(pool(),tables());a,lo,hi=m.arrays();au,bu,ae,be,um,em=lp_form(a,lo,hi);rows=[]
    write(dest/'domain.json',dict(scope='OUTER_RELAXATION_OF_ALL_CONTINUOUS_SCHEDULES_IN_ENTIRE_2903_PATTERN_POOL',
        variables=len(m.names),constraints=a.shape[0],integer_pattern_counts_relaxed_for_LP=True,
        preserves=['All pool patterns with full class-bounded multiplicities','Exact class cover','Original hard and 1e-4 aggregate soft deadline necessities','Typed UAV/battery workload necessities','Aggregate continuous starts','Parallel machine completion-time tangent inequalities'],
        relaxed=['Individual starts replaced by pattern aggregate start sum','Explicit machine assignment/order and all interval conflicts relaxed','Individual lateness replaced by Jensen lower bound'],
        no_time_grid_restriction=True,no_external_targets=True))
    for axis in AXES:
        d=dest/axis;d.mkdir(exist_ok=True);c=costs[axis]
        np.savez_compressed(d/'model.npz',data=a.data,indices=a.indices,indptr=a.indptr,shape=a.shape,lower=lo,upper=hi,lb=m.lb,ub=m.ub,integrality=m.integer,objective=c)
        start=time.process_time();lp=linprog(c,A_ub=au,b_ub=bu,A_eq=ae,b_eq=be,bounds=list(zip(m.lb,m.ub)),method='highs',options=dict(threads=1,time_limit=90,primal_feasibility_tolerance=1e-8,dual_feasibility_tolerance=1e-8));cpu=time.process_time()-start
        row=dict(anchor=axis,status=int(lp.status),message=str(lp.message),cpu_s=cpu,iterations=int(lp.nit),nodes=None,scope='FULL_POOL_CONTINUOUS_OUTER_RELAXATION',full_pool_optimality_proven=False)
        if lp.success:
            cert=rational_lagrangian_bound(c,a,lo,hi,m.lb,m.ub,um,em,lp.ineqlin.marginals,lp.eqlin.marginals);cert['matrix_sha256']=digest(d/'model.npz');write(d/'certificate.json',cert)
            row.update(lower_bound=math.ceil(Fraction(int(cert['numerator']),int(cert['denominator']))) if axis=='sorties' else cert['lower_bound'],raw_lp_value=float(lp.fun),bound_status='VALID_FULL_POOL_CONTINUOUS_RELAXATION',certificate=str((d/'certificate.json').relative_to(ROOT)))
        else:row.update(lower_bound=None,bound_status='BOUND_NOT_VALID')
        rows.append(row);write(dest/'summary.json',rows);print('CERTIFIED_FULL_POOL_BOUND',axis,row.get('lower_bound'),flush=True)
    write(dest/'timing.json',dict(total_cpu_s=time.process_time()-tick))

if __name__=='__main__':main()
