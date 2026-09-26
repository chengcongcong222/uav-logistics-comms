"""Eight reproducible research figures from admitted numeric data."""
import os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'results/p1_5b'
os.environ['MPLCONFIGDIR']=str(OUT/'_mplcache')
import io,json,hashlib
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Patch
from src.p1_5b.guard import Guard
font_manager.fontManager.addfont('/mnt/c/Windows/Fonts/msyh.ttc')
font_manager.fontManager.addfont('/mnt/c/Windows/Fonts/arial.ttf')
plt.rcParams.update({'font.family':'Microsoft YaHei','font.size':9,'axes.labelsize':9,'axes.titlesize':10,
 'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.7,'lines.linewidth':1.3,
 'xtick.labelsize':8,'ytick.labelsize':8,'pdf.fonttype':42,'ps.fonttype':42,'svg.fonttype':'none',
 'axes.unicode_minus':False,'savefig.dpi':220})
B='#2563a6';O='#d67d24';G='#586674';GREEN='#288b79';PURPLE='#8558a6'
TYPE={'A':B,'B':GREEN,'C':PURPLE};FIG=OUT/'paper/figures';DATA=OUT/'figure_data'
guard=Guard();guard.install()
def read(n):return pd.read_csv(io.StringIO(guard.text(DATA/n)),float_precision='round_trip')
manifest=[]
def save(fig,num,name,caption):
    paths=[]
    for ext in ['png','svg','pdf']:
        p=FIG/f'fig{num:02d}_{name}.{ext}'
        if ext=='svg':
            buf=io.StringIO();fig.savefig(buf,format='svg',bbox_inches='tight')
            p.write_text('\n'.join(line.rstrip() for line in buf.getvalue().splitlines())+'\n')
        else:fig.savefig(p,bbox_inches='tight',metadata={'Creator':'Matplotlib'} if ext=='pdf' else None)
        paths.append(p)
    manifest.append(dict(number=num,name=name,caption=caption,files=[str(p.relative_to(ROOT)) for p in paths],
        sources_read=sorted(guard.reads),generator='src/p1_5b/figures.py'))
    plt.close(fig)
def main():
    FIG.mkdir(parents=True,exist_ok=True)
    mech=guard.json(DATA/'mechanism.json');trade=read('tradeoffs.csv');t=read('transport_sorties.csv');r=read('relay_sorties.csv')
    q4=read('q4_tradeoff.csv');nodes=read('nodes.csv').set_index('node_id')
    # 1: an evidence pipeline, without decorated flowchart boxes.
    fig,ax=plt.subplots(figsize=(10.6,3.2));ax.set(xlim=(-.5,4.5),ylim=(-1.2,1.25));ax.axis('off')
    labels=['统一物理规则','运输模式与排程','通信缺口与中继','时间反馈与验证','固定任务独立分区']
    details=['地形 / 载荷 / 能源\n实体与共享资源','2903 个自主模式\n形成高效运输结构','轨迹逐段检查\n动态服务模式','满足完整通信\n选择时效—资源折中','F13：4 个依赖块\n两组 / 三组完整枚举']
    for i,(l,d) in enumerate(zip(labels,details)):
        c=[G,B,O,B,G][i];ax.scatter(i,.25,s=180,c=c,zorder=3)
        ax.text(i,.6,f'{i+1:02d}  {l}',ha='center',weight='bold',fontsize=9)
        ax.text(i,-.05,d,ha='center',va='top',linespacing=1.8)
        if i<4:ax.annotate('',xy=(i+.88,.25),xytext=(i+.12,.25),arrowprops=dict(arrowstyle='->',color=G,lw=1.1))
    ax.annotate('',xy=(1,-.63),xytext=(3,-.63),arrowprops=dict(arrowstyle='->',color=O,connectionstyle='arc3,rad=-.18'))
    ax.text(2,-1.02,'资源冲突 → 必要约束 → 重排运输时刻与资源次序',ha='center',color=O)
    save(fig,1,'framework','从统一物理模型到固定任务分区的技术路线；通信反馈作用于运输时刻与资源次序。')
    # 2: explicit schematic and an actual model curve.
    fig,(ax,ay)=plt.subplots(1,2,figsize=(10.5,3.5),layout='constrained')
    x=np.array([0,.25,.55,.8,1.]);z=np.array([0,.16,.46,.2,.05])
    ax.fill_between(x,z,0,color='#ccd2d6');ax.plot([0,0,1,1],[0,.68,.68,.05],color=B)
    ax.annotate('',xy=(.55,.68),xytext=(.55,.46),arrowprops=dict(arrowstyle='<->',color=G))
    ax.text(.57,.56,'安全间隔',fontsize=8);ax.text(.04,.73,'爬升 → 巡航 → 下降',color=B)
    ax.text(0,-.1,'O01',ha='center');ax.text(1,-.1,'服务区',ha='center')
    ax.set(title='(a) 原生DEM穿格与航段高度约束示意',ylim=(-.15,.92));ax.axis('off')
    ax.text(.5,.87,'示意图，不表示实测地形剖面',ha='center',fontsize=8,color=G)
    curves=read('payload_energy_curve.csv')
    for typ,frame in curves.groupby('type'):
        ay.plot(frame.mass_kg,frame.energy_kwh,label=f'{typ}型往返能耗',color=TYPE[typ])
        ay.hlines(frame.budget_kwh.iloc[0],0,frame.mass_kg.max(),color=TYPE[typ],ls='--',lw=.8)
    ay.set(title='(b) S004：载荷与往返能耗',xlabel='起飞载荷 / kg',ylabel='能耗 / kWh')
    ay.legend(fontsize=8,loc='upper left');ay.grid(alpha=.15)
    ay.text(.98,.04,'虚线：20%返航余量下可用能量',transform=ay.transAxes,ha='right',fontsize=8)
    save(fig,2,'physics','左图为几何约束示意，右图按统一物理公式计算S004往返能耗，载荷容量与可用能量共同限制单架次。')
    # 3: mode statistics plus actual visit incidence.
    fig,(ax,ay)=plt.subplots(1,2,figsize=(10.5,5.4),gridspec_kw={'width_ratios':[1,2]},layout='constrained')
    ax.barh(['单服务区模式','双服务区模式'],[mech['single_stop'],mech['two_stop']],color=[B,GREEN])
    for i,v in enumerate([296,2607]):ax.text(v+25,i,str(v),va='center')
    ax.set(xlim=(0,3100),ylim=(-1.35,1.65),xlabel='候选模式数',title='(a) 有限模式池')
    ax.text(.02,.025,'61 类等价货箱\n80 箱精确覆盖\n机型、实体与电池共同排程\nF13选取24个运输架次',transform=ax.transAxes,va='bottom',linespacing=1.8)
    ss=[f'S{i:03d}' for i in range(1,16)]
    for i,z in enumerate(t.itertuples()):
        for svc in z.service_sequence.split('>'):ay.scatter(ss.index(svc),i,color=TYPE[z.uav_type],marker='s',s=38)
    ay.set(xticks=range(15),xticklabels=[s[1:] for s in ss],yticks=range(len(t)),yticklabels=t.sortie_id,xlabel='服务区编号',title='(b) F13选中模式的访问关系')
    ay.invert_yaxis();ay.grid(alpha=.15)
    ay.legend(handles=[Patch(color=c,label=f'{k}型') for k,c in TYPE.items()],ncol=3,fontsize=8,loc='upper center',bbox_to_anchor=(.5,-.12))
    save(fig,3,'transport_patterns','有限运输模式池及F13选中架次的访问关系；箱组与访问结构确定后还需实体与共享电池排程。')
    # 4: before and after gap positions in actual transport clocks.
    gaps=read('original_gaps.csv');guarantee=read('communication_guarantee.csv')
    ids=sorted(set(guarantee.transport_sortie_id));show=ids[:min(8,len(ids))]
    fig,(ax,ay)=plt.subplots(2,1,figsize=(10.5,5.8),gridspec_kw={'height_ratios':[1,2]},layout='constrained')
    ax.axis('off')
    stages=['三维轨迹','通信缺口','中继服务模式','占用冲突','必要反馈','运输重排','完整验证']
    for i,s in enumerate(stages):
        ax.text(i/6,.7,s,ha='center',transform=ax.transAxes,color=O if i in [1,2,3] else B,fontsize=9)
        if i<6:ax.annotate('',xy=((i+.78)/6,.7),xytext=((i+.25)/6,.7),xycoords='axes fraction',arrowprops=dict(arrowstyle='->',lw=.8,color=G))
    ax.text(.5,.12,'链路覆盖成立仍需检查站点—中继机一致性、往返、周转与充电；未找到见证不等于物理不可行',ha='center',transform=ax.transAxes,fontsize=8)
    for i,sid in enumerate(show):
        for z in gaps[gaps.transport_sortie_id==sid].itertuples():ay.broken_barh([(z.service_start_s/60,(z.service_end_s-z.service_start_s)/60)],(i-.32,.26),facecolors='#a9bfd6')
        for z in guarantee[guarantee.transport_sortie_id==sid].itertuples():ay.broken_barh([(z.service_start_s/60,(z.service_end_s-z.service_start_s)/60)],(i+.04,.26),facecolors=O)
    ay.set(yticks=range(len(show)),yticklabels=show,xlabel='时刻 / min',title='F13通信保障区间的时序反馈（按编号选取前8个相关架次）')
    ay.grid(axis='x',alpha=.2);ay.legend(handles=[Patch(color='#a9bfd6',label='原运输时刻的通信缺口'),Patch(color=O,label='联合执行时刻的保障区间')],loc='upper center',bbox_to_anchor=(.5,-.2),ncol=2)
    save(fig,4,'coordination','分解协调机制及F13部分通信区间的时刻变化。动态服务模式为启发式生成，图不表示精确列生成收敛。')
    # 5: near-fast data only; no interpolated continuous frontier.
    d=trade[trade.id.isin(['F12','F16','F13','F18'])]
    fig,ax=plt.subplots(figsize=(7.4,4.2),layout='constrained')
    for z in d.itertuples():
        ax.scatter(z.joint_makespan_s/60,z.total_energy_kwh,s=90 if z.id=='F13' else 65,c=O if z.id=='F13' else B,marker='D' if z.id=='F13' else 'o')
        ax.annotate(f'{z.id}  {z.transport_sorties}+{z.relay_sorties}',(z.joint_makespan_s/60,z.total_energy_kwh),xytext=(8,7),textcoords='offset points')
    ax.set(xlim=(102.35,105.5),ylim=(69.75,74),xlabel='联合完工 / min',ylabel='总能耗 / kWh')
    ax.grid(alpha=.2);ax.text(.02,.03,'零迟到；标准通信；四个已验证离散方案',transform=ax.transAxes,fontsize=8)
    save(fig,5,'near_fast','近快端四个已验证折中代表；不连接成连续前沿，不据此声称完整Pareto。')
    # 6: all four actual resource calendars, including energy recovery.
    tu=read('transport_uav_calendar.csv');tb=read('transport_battery_calendar.csv');ru=read('relay_uav_calendar.csv');re=read('relay_energy_calendar.csv')
    panels=[(tu,'uav_id','busy_start_s','busy_end_s',B,'运输无人机'),(ru,'relay_id','busy_start_s','busy_end_s',O,'中继无人机（含周转）'),
       (tb,'battery_id','takeoff_s','energy_ready_s',B,'运输共享电池（含充电）'),(re,'energy_component_id','takeoff_s','charge_end_s',O,'中继能源组件（含充电）')]
    fig,axes=plt.subplots(4,1,figsize=(10.5,11),sharex=True,gridspec_kw={'height_ratios':[3,1.2,4,1.3]},layout='constrained')
    end=max(tb.energy_ready_s.max(),re.charge_end_s.max())/60
    for ax,(frame,key,start,stop,color,title) in zip(axes,panels):
        resources=sorted(frame[key].unique())
        for z in frame.to_dict('records'):
            y=resources.index(z[key]);a=z[start]/60;b=z[stop]/60
            ax.broken_barh([(a,b-a)],(y-.34,.68),facecolors=color,alpha=.8)
            if 'return_s' in z:ax.broken_barh([(z['return_s']/60,b-z['return_s']/60)],(y-.34,.68),facecolors='#bbc2c8',hatch='//',edgecolors='white',lw=.2)
        ax.set(yticks=range(len(resources)),yticklabels=resources,title=title,xlim=(0,end+1))
        ax.grid(axis='x',alpha=.18);ax.axvline(float(trade.set_index('id').loc['F13','joint_makespan_s'])/60,color='#202830',ls='--',lw=.8)
    axes[-1].set_xlabel('时刻 / min');axes[0].text(.99,1.02,'虚线：最后返航；灰色斜线：回场后充电/周转',transform=axes[0].transAxes,ha='right',fontsize=8)
    save(fig,6,'joint_resource_gantt','F13四类资源的实际占用。联合完工取最后返航，不包含其后的充电与周转；这些时段仍计入资源可用性与Q4。')
    # 7: fixed partition maps and typed shortage.
    groups=read('q4_groups.csv');fig=plt.figure(figsize=(10.5,7.6),layout='constrained');gs=fig.add_gridspec(2,2)
    colors={'G1':B,'G2':GREEN,'G3':PURPLE}
    for col,k in enumerate([2,3]):
        ax=fig.add_subplot(gs[0,col]);frame=groups[(groups.k==k)&(groups.role=='缺口优先')]
        for z in frame.itertuples():
            n=nodes.loc[z.service];x=(n.x_m-nodes.loc['O01'].x_m)/1000;y=(n.y_m-nodes.loc['O01'].y_m)/1000
            ax.scatter(x,y,c=colors[z.group],s=45);ax.annotate(z.service[1:],(x,y),xytext=(3,3),textcoords='offset points',fontsize=7)
        ax.scatter(0,0,marker='*',s=95,c=G);ax.annotate('O01',(0,0),xytext=(4,-9),textcoords='offset points',fontsize=7)
        ax.set(title=f'K={k}：缺口优先分区',xlabel='相对东向距离 / km',ylabel='相对北向距离 / km');ax.set_aspect('equal');ax.grid(alpha=.15)
    ax=fig.add_subplot(gs[1,:]);d=q4.sort_values(['k','role']);bottom=np.zeros(len(d))
    kinds=['TUAV_A','TUAV_B','TUAV_C','TBAT_A','TBAT_B','TBAT_C','RUAV','REC']
    palette=[B,GREEN,PURPLE,'#86a9cc','#8cc6b9','#bea7d0',O,'#edbd88']
    for kind,c in zip(kinds,palette):
        ax.bar(np.arange(len(d)),d[kind],bottom=bottom,label=kind,color=c,width=.55);bottom+=d[kind]
    for i,z in enumerate(d.itertuples()):ax.text(i,z.shortage+.35,f'{z.shortage}件\nCV={z.cv:.3f}',ha='center',fontsize=8)
    ax.set(xticks=range(len(d)),xticklabels=[f'K={z.k} {z.role}' for z in d.itertuples()],ylabel='相对库存的缺口 / 件',ylim=(0,23))
    ax.legend(ncol=4,loc='upper center',bbox_to_anchor=(.5,-.14),fontsize=7)
    save(fig,7,'partition_resources','固定F13任务下的分区与资源缺口。上排展示缺口优先分区；下排同时报告均衡优先代表。')
    # 8: sensitivity was explicitly required, so give it its own research plot.
    d=read('q1_levels.csv');payload=read('q1_payload.csv');critical=guard.json(DATA/'q1_breakpoints.json')
    fig,axes=plt.subplots(1,3,figsize=(11,3.6),layout='constrained')
    axes[0].plot(d.rho*100,d.sorties,'o-',color=B);axes[0].set(ylabel='最少运输架次',yticks=[18,19,20])
    for v in critical:axes[0].axvline(v['rho_boundary']*100,color=G,ls=':',lw=.8)
    axes[1].plot(d.rho*100,d.energy_kwh,'s-',color=O);axes[1].set(ylabel='组批总能耗 / kWh')
    for svc,c in [('S004',GREEN),('S008',PURPLE)]:
        f=payload[(payload.service_id==svc)&(payload.uav_type=='C')]
        axes[2].plot(f.rho*100,f.payload_limit_kg,'o-',label=f'C型 / {svc}',color=c)
    axes[2].set(ylabel='最大安全载荷 / kg');axes[2].legend(fontsize=8)
    for ax in axes:ax.set_xlabel('返航安全余量 / %');ax.set_xticks([10,15,20,25,30]);ax.grid(alpha=.18)
    save(fig,8,'reserve_sensitivity','统一几何下的Q1返航安全余量敏感性。载荷可行域连续收缩，不可拆货箱导致架次数在两个阈值附近阶跃。')
    (OUT/'paper/figure_manifest.json').write_text(json.dumps(dict(figures=manifest,source_accesses=sorted(guard.reads),style='Fixed transport/relay/environment semantics; no decorative 3D; all figure data admitted'),ensure_ascii=False,indent=2)+'\n')
    print('FIGURES_BUILT',len(manifest),flush=True)
if __name__=='__main__':main()
