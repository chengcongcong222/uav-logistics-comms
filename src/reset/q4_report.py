"""Q4 tradeoff figures, template-compatible tables and audit handoff."""
from src.reset.q4 import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import openpyxl

def table(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+['| '+' | '.join(map(str,r))+' |' for r in rows])
def savefig(fig,name):
    for ext in ['png','pdf','svg']:fig.savefig(OUT/f'{name}.{ext}',dpi=180)
    p=OUT/f'{name}.svg';p.write_text('\n'.join(x.rstrip() for x in p.read_text().splitlines())+'\n');plt.close(fig)

def workbook(ids,name,byid):
    raw=ROOT/'data/raw/结果提交模板.xlsx';w=openpyxl.load_workbook(raw)
    for sheet in list(w):
        if sheet.title!='Q4_分区配置':w.remove(sheet)
    ws=w['Q4_分区配置'];rowno=2
    for sid in ids:
        q=byid[sid]
        for group in q['groups']:
            values=[q['k'],group['group_id'],','.join(group['services'])]+[group['resources'][kind] for kind in KINDS]
            for col,value in enumerate(values,1):ws.cell(rowno,col,value)
            rowno+=1
    notes=w.create_sheet('口径与库存缺口');notes.append(['基线','A11_Q3_001，Gamma=0；所有任务时刻、航迹和通信关系冻结'])
    notes.append(['范围','仅 Q4 工作表草稿，不是全题最终提交文件'])
    notes.append(['方案','资源','需求','库存','缺口'])
    for sid in ids:
        for kind in KINDS:notes.append([sid,kind,byid[sid]['resources'][kind],byid[sid]['inventory'][kind],byid[sid]['shortage'][kind]])
    w.save(OUT/name)
    # Read the saved artifact back and compare all template cells.
    check=openpyxl.load_workbook(OUT/name,read_only=True,data_only=True)['Q4_分区配置'];expected=[]
    for sid in ids:
        for group in byid[sid]['groups']:expected.append(tuple([byid[sid]['k'],group['group_id'],','.join(group['services'])]+[group['resources'][kind] for kind in KINDS]))
    actual=list(check.iter_rows(min_row=2,max_row=1+len(expected),max_col=11,values_only=True));assert actual==expected

def main():
    config=json.loads((OUT/'config.json').read_text());records=json.loads((OUT/'all_partitions.json').read_text());byid={x['partition_id']:x for x in records};blocks=json.loads((OUT/'blocks.json').read_text())
    selected=[byid[s] for s in config['selected']];balanced=[byid[s] for s in config['balanced_alternatives']]
    workbook(config['selected'],'Q4_分区配置_缺口优先.xlsx',byid);workbook(config['balanced_alternatives'],'Q4_分区配置_均衡优先.xlsx',byid)
    groups=[]
    for role,rr in [('SHORTAGE_PRIORITY',selected),('BALANCE_PRIORITY',balanced)]:
        for q in rr:
            for g in q['groups']:groups.append(dict(partition_id=q['partition_id'],role=role,k=q['k'],group_id=g['group_id'],services=';'.join(g['services']),boxes=g['box_count'],mass_kg=g['mass_kg'],workload_s=g['workload_uav_occupied_s'],**g['resources']))
    csv(OUT/'group_configurations.csv',groups)
    fig,ax=plt.subplots(figsize=(7.6,4.6),layout='constrained')
    for k,color in [(2,'#2879b9'),(3,'#ba5a3a')]:
        rr=[q for q in records if q['k']==k];ax.scatter([q['total_shortage_units'] for q in rr],[q['workload_cv'] for q in rr],label=f'K={k}: all {len(rr)} feasible partitions',c=color,s=35,alpha=.65)
    for q in selected+balanced:
        ax.scatter(q['total_shortage_units'],q['workload_cv'],s=100,facecolors='none',edgecolors='black')
        ax.annotate(q['partition_id'].replace('Q4_',''),(q['total_shortage_units'],q['workload_cv']),xytext=(5,7),textcoords='offset points',fontsize=8)
    ax.set_xlabel('Additional resource units, summed across types (not monetary cost)');ax.set_ylabel('UAV occupied-time workload CV');ax.set_ylim(-.05,1.3);ax.grid(alpha=.2);ax.legend(fontsize=8);ax.set_title('Fixed Q3 execution: independent partition resource–balance tradeoffs')
    savefig(fig,'partition_resource_balance')
    nodes=read(DATA/'nodes.csv').set_index('node_id');fig,axes=plt.subplots(1,2,figsize=(10,4.6),layout='constrained');colors=['#2879b9','#c96338','#46974f']
    for ax,q in zip(axes,selected):
        for i,g in enumerate(q['groups']):
            f=nodes.loc[g['services']];ax.scatter(f.x_m/1000,f.y_m/1000,c=colors[i],label=g['group_id'],s=42)
            for sid,row in f.iterrows():ax.annotate(sid,(row.x_m/1000,row.y_m/1000),xytext=(3,3),textcoords='offset points',fontsize=7)
        origin=nodes.loc['O01'];ax.scatter(origin.x_m/1000,origin.y_m/1000,marker='^',c='black',label='O01');ax.set_xlabel('UTM easting (km)');ax.set_ylabel('UTM northing (km)');ax.set_aspect('equal');ax.margins(x=.12,y=.08);ax.grid(alpha=.2);ax.legend(fontsize=7);ax.set_title(f"K={q['k']}, inventory-shortage priority")
    savefig(fig,'partition_maps')
    summary=table(['角色','方案','资源总件数','新增缺口件数','工作量 CV','库存可独立执行'],[[role,q['partition_id'],q['total_resource_units'],q['total_shortage_units'],f"{q['workload_cv']:.6f}",('是' if q['inventory_feasible'] else '否，需补足所列缺口')] for role,rr in [('缺口优先',selected),('均衡优先',balanced)] for q in rr])
    resources=table(['资源类型','现库存','不分组最小池','K2 缺口优先需求','K2 缺口','K3 缺口优先需求','K3 缺口'],[[kind,blocks['inventory'][kind],blocks['global_minimum_resources'][kind],selected[0]['resources'][kind],selected[0]['shortage'][kind],selected[1]['resources'][kind],selected[1]['shortage'][kind]] for kind in KINDS])
    group_table=table(['方案','组','服务区','箱数','质量/kg','无人机占用/s','资源向量'],[[q['partition_id'],g['group_id'],','.join(g['services']),g['box_count'],f"{g['mass_kg']:.2f}",f"{g['workload_uav_occupied_s']:.3f}",str([g['resources'][kind] for kind in KINDS])] for q in selected+balanced for g in q['groups']])
    blocktable=table(['不可拆块','服务区'],[[i+1,','.join(ss)] for i,ss in enumerate(blocks['blocks'])])
    report='''# G2 自主主方案的 Q4 独立分区
源方案 A11_Q3_001，ΓC=0；固定运输任务、时刻和整中继架次依赖。库存缺口是结果，不隐瞒也不等同于原 Q3 不可执行。

'''
    report += blocktable+'\n\n'+summary+'\n\n'+resources+'\n\n'+group_table+'\n'
    report += '\n最小性仅适用于本次冻结任务与整中继架次不可拆的分区域。八维资源需求用区间峰值下界与组内着色核对；CV 为无人机占用时长的总体变异系数。资源件数不是采购货币成本。完整分区、缺口、均衡替代及独立证据见 CSV、configuration.json 和 validation.json。\n'
    (OUT/'Q4_REPORT.md').write_text(report)
    write(OUT/'submission_table_checks.json',dict(workbooks=2,rows_per_workbook=5,official_header_columns=11,readback_cell_equality=True,scope='Q4_ONLY'))
    print('G2_Q4_REPORTS_READY',flush=True)

if __name__=='__main__':main()
