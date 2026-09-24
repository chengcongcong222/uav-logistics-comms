"""Official six-sheet G2 workbook, with explicit Q3 transport timing supplements."""
import ast,json,hashlib
from pathlib import Path
import pandas as pd
import openpyxl
from pyproj import Transformer
from src.reset.geometry import ROOT,OUT,DATA,write,VERSION
Q2=OUT/'q2/pareto_schedules/A11';Q3=OUT/'q3/A11/solutions/A11_Q3_001';Q4=OUT/'q4';DEST=OUT/'submission'
def read(p):return pd.read_csv(p,float_precision='round_trip')
def rows_q2(t):return [[r.sortie_id,r.uav_id,r.uav_type,r.battery_id,r.preparation_start_s,r.service_sequence,r.return_s,r.energy_kwh] for r in t.itertuples()]
def rows_delivery(b):return [[r.box_id,r.sortie_id,r.service_id,r.delivery_time_s] for r in b.itertuples()]
def communication():
    t=read(Q3/'transport_sorties_A11.csv');g=read(Q3/'communication_guarantee_A11.csv');rows=[]
    for r in t.itertuples():
        gg=g[g.transport_sortie_id==r.sortie_id];cuts=sorted(set([r.takeoff_s,r.return_s]+gg.service_start_s.tolist()+gg.service_end_s.tolist()))
        for a,b in zip(cuts[:-1],cuts[1:]):
            if b-a<1e-8:continue
            active=gg[(gg.service_start_s<=(a+b)/2)&(gg.service_end_s>=(a+b)/2)]
            assert len(active)<=1
            provider='TRANSPORT_G01'
            relay=None
            if len(active):provider='TRANSPORT_RELAY_G01';relay=active.iloc[0].relay_sortie_id
            rows.append([r.sortie_id,'全航程保障区间',a,b,provider,relay])
    return rows
def main():
    DEST.mkdir(exist_ok=True);raw=ROOT/'data/raw/结果提交模板.xlsx';w=openpyxl.load_workbook(raw)
    for ws in w:ws.delete_rows(2,ws.max_row)
    types=read(DATA/'transport_uav_types.csv').set_index('uav_type');pk=read(OUT/'q1/q1_packings_rho20.csv')
    data={}
    data['Q1_单点组批']=[[f'Q1_{i:03d}',r.service_id,r.uav_type,','.join(ast.literal_eval(r.box_ids)),r.mass_kg,r.volume_m3,r.time_s,r.energy_kwh,100*(1-r.energy_kwh/types.loc[r.uav_type].battery_energy_kwh)] for i,r in enumerate(pk.itertuples(),1)]
    data['Q2_运输架次']=rows_q2(read(Q2/'q2_sorties.csv'));data['Q2_逐箱交付']=rows_delivery(read(Q2/'q2_box_delivery.csv'))
    sites=read(Q3/'candidate_sites_A11.csv').set_index('site_id');tf=Transformer.from_crs(32649,4326,always_xy=True)
    data['Q3_中继架次']=[]
    for r in read(Q3/'relay_sorties_A11.csv').itertuples():
        s=sites.loc[r.site_id];lon,lat=tf.transform(s.x_m,s.y_m)
        data['Q3_中继架次'].append([r.relay_sortie_id,r.relay_id,r.energy_component_id,r.preparation_start_s,lon,lat,s.z_amsl_m,r.service_start_s,r.service_end_s,r.return_s,r.total_energy_kwh])
    data['Q3_通信保障']=communication();data['Q4_分区配置']=[]
    config=json.loads((Q4/'config.json').read_text());kinds=['TUAV_A','TUAV_B','TUAV_C','TBAT_A','TBAT_B','TBAT_C','RUAV','REC']
    for sid in config['selected']:
        q=json.loads((Q4/'solutions'/sid/'configuration.json').read_text())
        for g in q['groups']:data['Q4_分区配置'].append([q['k'],g['group_id'],','.join(g['services'])]+[g['resources'][k] for k in kinds])
    for name,rows in data.items():
        for row in rows:w[name].append(row)
    for name,header,rows in [('Q3_运输时刻_必读',list(w['Q2_运输架次'].values)[0][:8],rows_q2(read(Q3/'transport_sorties_A11.csv'))),('Q3_逐箱交付_必读',list(w['Q2_逐箱交付'].values)[0][:4],rows_delivery(read(Q3/'box_delivery_A11.csv')))]:
        ws=w.create_sheet(name);ws.append(header)
        for row in rows:ws.append(row)
    for name,path in [('Q3_运输电池日历',Q3/'transport_battery_calendar_A11.csv'),('Q3_中继机日历',Q3/'relay_uav_calendar_A11.csv'),('Q3_中继能源日历',Q3/'relay_energy_calendar_A11.csv'),('Q4_分类型缺口',Q4/'group_configurations.csv')]:
        ws=w.create_sheet(name);f=read(path);ws.append(list(f.columns))
        for row in f.itertuples(index=False,name=None):ws.append([None if pd.isna(v) else v for v in row])
    # The shortage sheet must contain the actual type-specific shortage totals.
    ws=w['Q4_分类型缺口'];ws.delete_rows(1,ws.max_row);ws.append(['方案','资源类型','需求','库存','缺口'])
    for sid in config['selected']:
        q=json.loads((Q4/'solutions'/sid/'configuration.json').read_text())
        for k in kinds:ws.append([sid,k,q['resources'][k],q['inventory'][k],q['shortage'][k]])
    notes=w.create_sheet('口径与来源')
    for row in [
        ['几何版本',VERSION],['正式结果来源','本地原始数据与自主模式生成；不导入 XB 箱组、路线、机型'],
        ['Q2','A11；Q2 时刻只对应 Q2 两页'],['Q3/Q4','A11_Q3_001，Gamma=0；Q4 继承该方案时刻与依赖'],
        ['必须读取 Q3 补充页','Q3 联合调度已改变运输时刻，禁止用 Q2 运输时刻配 Q3 中继表'],
        ['开始时刻','准备开始；起飞、返航、充电完成见完整执行包'],['Q1 往返时间','含准备、装载、飞行、交接；所有架次时长之和不是机队完工时间'],
        ['通信保障','从起飞到返回的区间覆盖；双跳一架中继，其他区间直接到 G01；全航程 0.25 s 数值审计通过'],
        ['Q4 缺口','K2 缺 A 运输机1、B运输机1；K3 另缺 C运输机1、C电池1；需补足才能独立分组执行'],
        ['外部对照','B01/B02 仅另存审计比较，不进入本工作簿'],['证据边界','有限模式/预算下的可行见证与档案非支配点；不声称全局 Pareto；旧 E8 鲁棒等级不转移']
    ]:notes.append(row)
    for ws in w:ws.freeze_panes='A2';ws.auto_filter.ref=ws.dimensions
    w.save(DEST/'结果提交表_G2_自主主方案.xlsx')
    write(DEST/'cell_payload.json',data)
    sources=[raw,OUT/'q1/q1_packings_rho20.csv',DATA/'manifest.json']
    sources += [p for base in [Q2,Q3,Q4] for p in base.rglob('*') if p.is_file() and p.suffix in ['.csv','.json']]
    write(DEST/'input_manifest.json',dict(geometry=VERSION,Q2='A11',Q3='A11_Q3_001',Q4=config['selected'],hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}))
    print('G2_SUBMISSION_CREATED', {k:len(v) for k,v in data.items()})
if __name__=='__main__':main()
