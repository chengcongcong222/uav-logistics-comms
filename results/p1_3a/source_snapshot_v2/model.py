"""Exact MILP over a declared finite catalogue of relay endpoint-order modes.

No inherited machine orders. Energy is the exact interval union in each
selected mode; charging is its original two-piece graph, not an epigraph.
"""
import itertools, json, math
from fractions import Fraction
import numpy as np
from scipy.sparse import coo_matrix, csr_matrix, vstack
from src.bench_p1.common import signature
from src.bench_p1 import q3_adapter as adapter
from src.common.charging import charge_time_s

AXES=('J_norm','joint_makespan_s','total_energy_kwh','relay_sorties')
HORIZON=40000.

def combine(*terms):
    out={}
    for scale,row in terms:
        for j,v in row.items():out[j]=out.get(j,0.)+scale*v
    return {j:v for j,v in out.items() if v}

def expr_value(expr,x):return expr[1]+sum(v*x[j] for j,v in expr[0].items())

def union_affine(endpoints):
    union={};constant=0.;depth=0
    for event in endpoints:
        if event[2]==0:
            if depth==0:left=event
            depth+=1
        else:
            depth-=1
            if depth==0:
                union=combine((1,union),(1,{event[0]:1}),(-1,{left[0]:1}));constant+=event[1]-left[1]
    assert depth==0
    return union,constant

def charging_graph(model,energy,charge,z,capacity,full,prefix):
    high=model.var(prefix+'charge_high_energy_branch',integer=True)
    model.row({high:1,z:-1},hi=0,label='inactive_charge_branch')
    model.conditional({energy:-1},-.1*capacity,[(high,1)],'charge_high_region')
    model.conditional({energy:1},.1*capacity,[(high,0)],'charge_low_region')
    low_slope=3.5*full/capacity;high_slope=.65/.9*full/capacity;intercept=(.35-.65*.1/.9)*full
    model.conditional_eq({charge:1,energy:-low_slope},0,[(high,0)],'EXACT_CHARGE_LOW')
    model.conditional_eq({charge:1,energy:-high_slope,z:-intercept},0,[(high,1)],'EXACT_CHARGE_HIGH')
    return high

def endpoint_mode(e,tasks,witness,origin):
    events=[]
    for aid in tasks:
        t=e.atoms.loc[aid];delta=witness['shifts'][t.transport_sortie_id]
        events.extend([(float(t.service_start_s)+delta,0,aid),(float(t.service_end_s)+delta,1,aid)])
    events.sort()
    return dict(task_ids=sorted(tasks),events=[[aid,typ] for _,typ,aid in events],origin=origin)

def catalogue(e,witnesses):
    modes={};observed=set()
    def add(mode):
        key=signature({k:mode[k] for k in ('task_ids','events')})
        if key in modes:return
        sites=sorted(e.common(mode['task_ids']))
        duration=max(float(e.atoms.loc[t].service_duration_s) for t in mode['task_ids'])
        # Necessary single-flight energy bound, independent of all timing.
        sites=[s for s in sites if e.energy(e.sites[s],0)['total_energy_kwh']+
               (e.pr['hover_power_kw']+e.pr['comm_power_kw'])*duration/3600 <= (1-e.pr['rho'])*e.pr['energy_kwh']+1e-10]
        if sites:modes[key]=dict(mode,id=key,sites=sites,minimum_duration_s=duration)
    for w in witnesses:
        for g in w['groups']:
            observed.add(tuple(sorted(g['task_ids'])))
            add(endpoint_mode(e,g['task_ids'],w,'OBSERVED_VERIFIED_MODE'))
    reference=min(witnesses,key=lambda w:(w['metrics']['J_late']>1e-4,w['metrics']['J_late'],w['metrics']['J_norm']))
    for aid in e.atoms.index:add(endpoint_mode(e,[aid],reference,'ATOMIC_SINGLETON'))
    for a,b in itertools.combinations(sorted(observed),2):
        if set(a).isdisjoint(b):add(endpoint_mode(e,sorted(set(a)|set(b)),reference,'ONE_STEP_DISJOINT_OBSERVED_GROUP_UNION'))
    return [modes[k] for k in sorted(modes)]

class LinearModel:
    def __init__(self):
        self.names=[];self.lb=[];self.ub=[];self.integer=[];self.rows=[];self.lower=[];self.upper=[];self.labels=[]
    def var(self,name,lo=0.,hi=1.,integer=False):
        assert math.isfinite(lo) and math.isfinite(hi) and lo<=hi,(name,lo,hi)
        j=len(self.names);self.names.append(name);self.lb.append(float(lo));self.ub.append(float(hi));self.integer.append(int(integer));return j
    def row(self,row,lo=-np.inf,hi=np.inf,label=''):
        self.rows.append({j:float(v) for j,v in row.items() if v});self.lower.append(float(lo));self.upper.append(float(hi));self.labels.append(label)
    def eq(self,row,rhs=0.,label=''):self.row(row,rhs,rhs,label)
    def conditional(self,row,rhs,triggers,label=''):
        # All finite variable bounds are explicit. M is derived, not guessed.
        top=sum(v*(self.ub[j] if v>=0 else self.lb[j]) for j,v in row.items())
        big=max(0.,top-rhs)+1e-8
        result=dict(row);cap=rhs
        for j,value in triggers:
            result[j]=result.get(j,0.)+(big if value else -big)
            if value:cap+=big
        self.row(result,hi=cap,label=label)
    def conditional_eq(self,row,rhs,triggers,label=''):
        self.conditional(row,rhs,triggers,label)
        self.conditional({j:-v for j,v in row.items()},-rhs,triggers,label)
    def arrays(self):
        rr=[];cc=[];vv=[]
        for i,row in enumerate(self.rows):
            for j,v in row.items():rr.append(i);cc.append(j);vv.append(v)
        a=coo_matrix((vv,(rr,cc)),shape=(len(self.rows),len(self.names))).tocsr()
        return a,np.array(self.lower),np.array(self.upper)
    def violation(self,x):
        a,lo,hi=self.arrays();v=a@x
        return dict(rows=float(max(0.,np.max(lo-v),np.max(v-hi))),
                    bounds=float(max(0.,np.max(np.array(self.lb)-x),np.max(x-np.array(self.ub)))),
                    integrality=float(max([0.]+[abs(x[i]-round(x[i])) for i,b in enumerate(self.integer) if b])))

class AuditModel(LinearModel):
    def __init__(self,e,modes,reference):
        super().__init__();self.e=e;self.pid=e.pid;self.modes=modes
        core=adapter.core.Timing(e,e.pid,reference['groups'])
        self.core=core;self.n=core.n;self.ids=core.ids;self.idx=core.idx
        self.one=self.var('constant_one',1,1)
        self.delta=[]
        for i,sid in enumerate(core.ids):
            lo,hi=core.bounds[i]
            self.delta.append(self.var('transport_shift_'+sid,lo,hi))
        self.late=[]
        for j,row in enumerate(core.delivery.itertuples()):
            ell=self.var('late_'+row.box_id,0,1e-4/core.weights[j]);self.late.append(ell)
            self.row({self.delta[core.idx[row.sortie_id]]:1,ell:-1},hi=core.deadlines[j]-row.delivery_time_s,label='soft_deadline_epigraph')
        self.row({v:float(w) for v,w in zip(self.late,core.weights)},hi=1e-4,label='ZERO_LATENESS_HARD_LAYER')
        static={s:e.energy(e.sites[s],0) for m in modes for s in m['sites']}
        maximum_return=max(s['return_time_s'] for s in static.values())
        self.T=self.var('joint_makespan',0,HORIZON+maximum_return)
        for i,sid in enumerate(core.ids):self.row({self.delta[i]:1,self.T:-1},hi=-float(core.transport.loc[sid].return_s),label='transport_completion')
        self.transport_energy=float(core.transport.energy_kwh.sum())
        p=e.pr;cap=(1-p['rho'])*p['energy_kwh']
        full=float(adapter.read(adapter.resources.PROCESSED_DIR/'relay_energy_components.csv').iloc[0].full_charge_time_s)
        self.full_charge=full;self.jobs=[];self.families=[]
        for index,mode in enumerate(modes):
            prefix=f'G{index:03d}_';z=self.var(prefix+'selected',integer=True)
            ys={s:self.var(prefix+'site_'+s,integer=True) for s in mode['sites']}
            self.eq(combine((1,{j:1 for j in ys.values()}),(-1,{z:1})),label='one_site_if_selected')
            vars_={name:self.var(prefix+name,0,upper) for name,upper in
                [('start',HORIZON),('end',HORIZON),('active',HORIZON),('energy',cap),
                 ('prep',HORIZON),('takeoff',HORIZON),('return',HORIZON+maximum_return),
                 ('uav_ready',HORIZON+maximum_return+p['turnaround_time_s']),
                 ('charge',full),('energy_ready',HORIZON+maximum_return+full)]}
            a,b,active,energy=[vars_[k] for k in ('start','end','active','energy')]
            for key,j in vars_.items():self.row({j:1,z:-self.ub[j]},hi=0,label='inactive_zero')
            endpoints=[]
            for aid,is_end in mode['events']:
                task=e.atoms.loc[aid];i=self.delta[core.idx[task.transport_sortie_id]]
                t=float(task.service_end_s if is_end else task.service_start_s)
                endpoints.append((i,t,is_end))
            for left,right in zip(endpoints[:-1],endpoints[1:]):
                self.conditional(combine((1,{left[0]:1}),(-1,{right[0]:1})),right[1]-left[1],[(z,1)],'SELECTED_ENDPOINT_ORDER')
            for var,event in [(a,endpoints[0]),(b,endpoints[-1])]:
                self.conditional_eq({var:1,event[0]:-1},event[1],[(z,1)],'service_endpoint_identity')
                self.row({var:1,z:-(event[1]+self.lb[event[0]])},lo=0,label='endpoint_lower_perspective')
                self.row({var:1,z:-(event[1]+self.ub[event[0]])},hi=0,label='endpoint_upper_perspective')
            union,constant=union_affine(endpoints)
            self.conditional_eq(combine((1,{active:1}),(-1,union)),constant,[(z,1)],'EXACT_ACTIVE_UNION')
            self.row({active:1,z:-mode['minimum_duration_s']},lo=0,label='single_task_union_lower_bound')
            self.row({b:1,a:-1,active:-1},lo=0,label='active_within_span')
            self.eq(combine((1,{energy:1,b:-p['hover_power_kw']/3600,a:p['hover_power_kw']/3600,active:-p['comm_power_kw']/3600}),
                           (-1,{j:static[s]['total_energy_kwh'] for s,j in ys.items()})),label='EXACT_ENERGY')
            self.row(combine((1,{energy:1}),(-1,{j:static[s]['total_energy_kwh']+(p['hover_power_kw']+p['comm_power_kw'])*mode['minimum_duration_s']/3600 for s,j in ys.items()})),lo=0,label='energy_perspective_lower_bound')
            for name,origin,factor in [('prep',a,-1),('takeoff',a,-1),('return',b,1)]:
                if name=='prep':offsets={j:p['prep_time_s']+p['setup_time_s']+static[s]['outbound_time_s'] for s,j in ys.items()}
                elif name=='takeoff':offsets={j:p['setup_time_s']+static[s]['outbound_time_s'] for s,j in ys.items()}
                else:offsets={j:static[s]['return_time_s'] for s,j in ys.items()}
                self.eq(combine((1,{vars_[name]:1,origin:-1}),(-factor,offsets)),label='relay_flight_times')
            self.eq({vars_['uav_ready']:1,vars_['return']:-1,z:-p['turnaround_time_s']},label='relay_turnaround')
            high=charging_graph(self,energy,vars_['charge'],z,p['energy_kwh'],full,prefix)
            self.eq({vars_['energy_ready']:1,vars_['return']:-1,vars_['charge']:-1},label='energy_ready')
            self.row({vars_['return']:1,self.T:-1},hi=0,label='relay_completion')
            self.jobs.append(dict(index=index,z=z,sites=ys,vars=vars_,high=high,mode=mode,union=union,union_constant=constant))
        for aid in e.atoms.index:self.eq({j['z']:1 for j in self.jobs if aid in j['mode']['task_ids']},1,'EXACT_TASK_COVER')
        for kind,typ,specs,allowed in core.resource_specs:
            jobs=[dict(name=core.ids[i],active=self.one,start=({self.delta[i]:1},a),end=({self.delta[i]:1},b),tasks=set()) for i,a,b in specs]
            extra=0 if kind=='UAV' else max(b-float(core.transport.loc[core.ids[i]].return_s) for i,a,b in specs)
            self.resources(kind+'_'+typ,jobs,allowed,extra)
        jobs=[dict(name=j['index'],active=j['z'],start=({j['vars']['prep']:1},0.),end=({j['vars']['uav_ready']:1},0.),tasks=set(j['mode']['task_ids'])) for j in self.jobs]
        self.resources('RELAY_UAV',jobs,['R01','R02'],p['turnaround_time_s'])
        jobs=[dict(name=j['index'],active=j['z'],start=({j['vars']['takeoff']:1},0.),end=({j['vars']['energy_ready']:1},0.),tasks=set(j['mode']['task_ids'])) for j in self.jobs]
        self.resources('RELAY_ENERGY',jobs,[f'REC-{i:02d}' for i in range(1,7)],full)

    def resources(self,name,jobs,allowed,tail):
        assigns=[];orders=[]
        for i,job in enumerate(jobs):
            row=[self.var(f'{name}_{i}_{r}',integer=True) for r in allowed];assigns.append(row)
            self.eq(combine((1,{j:1 for j in row}),(-1,{job['active']:1})),label='resource_assignment')
        for i,j in itertools.combinations(range(len(jobs)),2):
            if jobs[i]['tasks'] & jobs[j]['tasks']:continue # exact cover makes co-selection impossible
            order=self.var(f'{name}_order_{i}_{j}',integer=True);orders.append((i,j,order))
            left,right=jobs[i],jobs[j]
            row=combine((1,left['end'][0]),(-1,right['start'][0]));rhs=right['start'][1]-left['end'][1]
            reverse=combine((1,right['end'][0]),(-1,left['start'][0]));cap=left['start'][1]-right['end'][1]
            for r in range(len(allowed)):
                self.conditional(row,rhs,[(assigns[i][r],1),(assigns[j][r],1),(order,1)],'FREE_RESOURCE_ORDER')
                self.conditional(reverse,cap,[(assigns[i][r],1),(assigns[j][r],1),(order,0)],'FREE_RESOURCE_ORDER')
        workload={};constant=0.
        for job in jobs:
            workload=combine((1,workload),(1,job['end'][0]),(-1,job['start'][0]));constant+=job['end'][1]-job['start'][1]
        workload[self.T]=workload.get(self.T,0)-len(allowed)
        self.row(workload,hi=len(allowed)*tail-constant,label='VALID_RESOURCE_WORKLOAD_CUT')
        self.families.append(dict(name=name,jobs=jobs,allowed=allowed,assigns=assigns,orders=orders))

    def objective(self,axis):
        c=np.zeros(len(self.names))
        if axis=='joint_makespan_s':c[self.T]=1
        elif axis=='total_energy_kwh':
            c[self.one]=self.transport_energy
            for j in self.jobs:c[j['vars']['energy']]=1
        elif axis=='relay_sorties':
            for j in self.jobs:c[j['z']]=1
        elif axis=='J_norm':
            core=self.core;c[self.one]=float(np.sum(core.weights*core.original_delivery/core.deadlines)/sum(core.weights))
            for i in range(core.n):c[self.delta[i]]=core.norm_c[i]
        else:raise ValueError(axis)
        return c

    def embed(self,witness):
        x=np.zeros(len(self.names));x[self.one]=1;x[self.T]=witness['metrics']['joint_makespan_s']
        for sid,value in witness['shifts'].items():x[self.delta[self.idx[sid]]]=value
        core=self.core
        for j,row in enumerate(core.delivery.itertuples()):x[self.late[j]]=max(0.,row.delivery_time_s+witness['shifts'][row.sortie_id]-core.deadlines[j])
        chosen={}
        for group,selected in zip(witness['groups'],witness['selected']):
            mode=endpoint_mode(self.e,group['task_ids'],witness,'')
            key=signature({k:mode[k] for k in ('task_ids','events')})
            job=next(j for j in self.jobs if j['mode']['id']==key)
            chosen[job['index']]=selected;x[job['z']]=1;x[job['sites'][group['site_id']]]=1
            names=dict(start='service_start_s',end='service_end_s',active='active_communication_s',energy='total_energy_kwh',prep='preparation_start_s',takeoff='takeoff_s',return_='return_s',uav_ready='uav_available_s',charge='charge_duration_s',energy_ready='energy_ready_s')
            for name,field in names.items():x[job['vars']['return' if name=='return_' else name]]=selected[field]
            x[job['high']]=float(selected['total_energy_kwh']>=.1*self.e.pr['energy_kwh'])
        for fam in self.families:
            for i,job in enumerate(fam['jobs']):
                if x[job['active']]<.5:continue
                if fam['name']=='RELAY_UAV':resource=chosen[job['name']]['relay_id']
                elif fam['name']=='RELAY_ENERGY':resource=chosen[job['name']]['energy_component_id']
                else:resource=witness['assignments'][job['name']]['uav_id' if fam['name'].startswith('UAV_') else 'battery_id']
                x[fam['assigns'][i][fam['allowed'].index(resource)]]=1
            for i,j,order in fam['orders']:
                x[order]=float(expr_value(fam['jobs'][i]['end'],x)<=expr_value(fam['jobs'][j]['start'],x)+1e-7)
        return x

    def materialize(self,x,axis):
        from src.q3.e6_resources import sortie_column,color_intervals
        shifts={s:float(x[self.delta[i]]) for i,s in enumerate(self.ids)};groups=[];selected=[]
        for job in self.jobs:
            if x[job['z']]<.5:continue
            site=max(job['sites'],key=lambda s:x[job['sites'][s]])
            group=dict(site_id=site,task_ids=job['mode']['task_ids']);groups.append(group)
            row=sortie_column(self.e,self.pid,site,group['task_ids'],shifts)
            if row is None:raise ValueError('Exact model solution failed physical relay materialization')
            selected.append(row)
        color_intervals(selected,'preparation_start_s','uav_available_s',['R01','R02'],'relay_id')
        color_intervals(selected,'takeoff_s','energy_ready_s',[f'REC-{i:02d}' for i in range(1,7)],'energy_component_id')
        assignments={s:{} for s in self.ids}
        for kind,typ,specs,allowed in self.core.resource_specs:
            rows=[dict(sortie_id=self.ids[i],start=shifts[self.ids[i]]+a,end=shifts[self.ids[i]]+b) for i,a,b in specs]
            color_intervals(rows,'start','end',allowed,'resource')
            for row in rows:assignments[row['sortie_id']]['uav_id' if kind=='UAV' else 'battery_id']=row['resource']
        c=self.core;times=c.original_delivery+np.array([shifts[s] for s in c.delivery.sortie_id])
        energy=sum(r['total_energy_kwh'] for r in selected)
        metrics=dict(J_late=float(np.sum(c.weights*np.maximum(0,times-c.deadlines))),J_norm=float(np.sum(c.weights*times/c.deadlines)/sum(c.weights)),
             joint_makespan_s=max(max(float(c.transport.loc[s].return_s)+v for s,v in shifts.items()),max(r['return_s'] for r in selected)),
             transport_energy_kwh=self.transport_energy,relay_energy_kwh=energy,total_energy_kwh=self.transport_energy+energy,
             transport_sorties=self.n,relay_sorties=len(selected),total_transport_shift_s=sum(shifts.values()),
             total_absolute_transport_shift_s=sum(abs(v) for v in shifts.values()),max_transport_shift_s=max(shifts.values()),
             minimum_M_E_kwh=min(r['energy_margin_kwh'] for r in selected))
        from src.q3.e7_core import sequences_for
        return dict(pareto_id=self.pid,groups=groups,sequences=sequences_for(selected),selected=selected,shifts=shifts,
                    assignments=assignments,metrics=metrics,resource_precedence_cuts=[],objective=axis,J_late_budget=1e-4,
                    level='STRUCTURE_FIXED_EXACT_AUDIT')

def lp_form(a,lo,hi):
    upper=[];bounds=[];equals=[];rhs=[];u_map=[];e_map=[]
    for i,(l,h) in enumerate(zip(lo,hi)):
        if l==h:
            equals.append(a.getrow(i));rhs.append(l);e_map.append(i)
        else:
            if math.isfinite(h):upper.append(a.getrow(i));bounds.append(h);u_map.append((i,1))
            if math.isfinite(l):upper.append(-a.getrow(i));bounds.append(-l);u_map.append((i,-1))
    return (vstack(upper).tocsr() if upper else None,np.array(bounds),
            vstack(equals).tocsr() if equals else None,np.array(rhs),u_map,e_map)

def rational_lagrangian_bound(c,a,lo,hi,lb,ub,u_map,e_map,dual_upper,dual_equal):
    """An exact-rational Lagrangian lower bound for the stored binary64 model.

    No approximate stationarity assumption: minimize its exact residual over
    the finite variable box. Any sign-correct multipliers give a valid bound.
    """
    F=lambda x:Fraction.from_float(float(x))
    multipliers=[Fraction(0) for _ in lo];value=Fraction(0)
    yu=[min(float(y),0.) for y in dual_upper];ye=[float(y) for y in dual_equal]
    for (i,sign),y in zip(u_map,yu):
        q=F(y);multipliers[i]+=sign*q;value+=q*F(hi[i] if sign==1 else -lo[i])
    for i,y in zip(e_map,ye):q=F(y);multipliers[i]+=q;value+=q*F(lo[i])
    residual=[F(v) for v in c]
    for i,y in enumerate(multipliers):
        if not y:continue
        for k in range(a.indptr[i],a.indptr[i+1]):residual[a.indices[k]]-=F(a.data[k])*y
    for r,l,h in zip(residual,lb,ub):value+=r*F(l if r>=0 else h)
    bound=math.nextafter(float(value),-math.inf)
    return dict(lower_bound=bound,numerator=str(value.numerator),denominator=str(value.denominator),
                upper_multipliers=yu,equality_multipliers=ye,
                proof='EXACT_RATIONAL_LAGRANGIAN_WITH_BOX_RESIDUAL_CORRECTION_FOR_STORED_BINARY64_MILP')
