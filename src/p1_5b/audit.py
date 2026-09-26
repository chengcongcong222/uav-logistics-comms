"""Check immutable sources, manuscript, plots and workbook metric agreement."""
import json,re,hashlib,io,csv,subprocess
from pathlib import Path
import openpyxl
from src.p1_5b.guard import ROOT,OUT,Guard
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def main():
    paper=OUT/'paper';policy=read(OUT/'PAPER_SOURCE_WHITELIST.json');entries={e['path']:e for e in policy['sources']}
    inherited=read(ROOT/'results/p1_5a/PAPER_SOURCE_WHITELIST.json')
    for e in policy['sources']:assert sha(ROOT/e['path'])==e['sha256'],e['path']
    for e in inherited['sources']:assert entries[e['path']]['sha256']==e['sha256']
    denied_paths=[r'results/xb1/',r'/external[_/]',r'/B0[12]/',r'/R\d{2}/',r'UNVERIFIED_EXTERNAL_CHALLENGE']
    assert not [e['path'] for e in policy['sources'] if any(re.search(p,e['path'],re.I) for p in denied_paths)]
    build=read(paper/'build_validation.json');figs=read(paper/'figure_manifest.json');tests=read(paper/'guard_tests.json')
    assert build['status']==tests['status']=='PASSED' and len(tests['cases'])==12 and len(figs['figures'])==8
    for rel in set(build['source_accesses']+figs['source_accesses']):assert rel in entries,rel
    body=(paper/'PAPER_V02.md').read_text();assert sha(paper/'PAPER_V02.md')==build['paper_sha256']
    forbidden=[r'网友',r'其他队伍',r'其他参赛队伍',r'外部挑战',r'external\s+challenge',r'\bB0[12]\b',r'\bXB\w*',r'UNVERIFIED_EXTERNAL_CHALLENGE',r'竞赛解答',r'竞赛答案',r'论坛',r'社交平台',r'\bA11\b']
    scanned=[paper/'PAPER_V02.md',paper/'REFERENCE_EVIDENCE_MAP.md',paper/'CLAIM_EVIDENCE_MAP.md']+sorted((paper/'figures').glob('*.svg'))
    hits=[]
    for p in scanned:
        text=p.read_text()
        for pattern in forbidden:
            if re.search(pattern,text,re.I):hits.append(dict(path=str(p.relative_to(ROOT)),pattern=pattern))
    assert not hits,hits
    assert not re.search(r'\b(Gate|commit|hash|checkpoint)\b',body,re.I)
    assert '@@' not in body and len(re.findall(r'^## \d+ ',body,re.M))==11
    assert len(re.findall(r'^!\[',body,re.M))==8
    for link in re.findall(r'!\[[^\]]*\]\(([^)]+)\)',body):assert (paper/link).is_file()
    assert len(read(OUT/'references/bibliography.json'))==10
    # Read the authoritative workbook without modifying it. Full 22-sheet audit remains A-stage authority.
    consistency=read(ROOT/'results/p1_5a/submission_consistency.json');book=ROOT/consistency['workbook']
    assert sha(book)==consistency['sha256']
    w=openpyxl.load_workbook(io.BytesIO(book.read_bytes()),read_only=True,data_only=True)
    values=list(w['主指标核对'].values);metrics={r[0]:r[1] for r in values[1:]}
    f=read(ROOT/'results/p1_5a/F13_readmission.json')['metrics']
    for k,label in [('joint_makespan_s','Q3联合完工'),('total_energy_kwh','Q3总能耗'),('J_late','J_late'),('J_norm','J_norm')]:assert abs(float(metrics[label])-f[k])<1e-9,(k,metrics)
    assert len(list(w['Q2_逐箱交付'].values))-1==80 and len(list(w['Q2_运输架次'].values))-1==24 and len(list(w['Q3_中继架次'].values))-1==3
    assert len(w.sheetnames)==consistency['checked_sheets']==22;w.close()
    # Independent formula check for every row in the local comparative table.
    comps=read(OUT/'admitted_comparators.json');rows=list(csv.DictReader((OUT/'figure_data/tradeoffs.csv').open()))
    assert len(rows)==5
    for row,item in zip(rows,comps):
        assert row['id']==item['id']
        for key,value in item['metrics'].items():assert abs(float(row[key])-value)<1e-9
    # Ensure exported figure data remains tied to exact admitted F13 source bytes.
    pkg=ROOT/'results/p1_5a/execution/q3/F13/solutions/F13_C2_SITE_B6500_RELAY_00_Q3'
    lineage={}
    for name in ['transport_sorties','box_delivery','transport_uav_calendar','transport_battery_calendar','relay_sorties','relay_uav_calendar','relay_energy_calendar','communication_guarantee']:
        source=pkg/f'{name}_F13.csv';dest=OUT/'figure_data'/f'{name}.csv';assert sha(source)==sha(dest)
        lineage[str(dest.relative_to(ROOT))]=dict(source=str(source.relative_to(ROOT)),sha256=sha(source))
    for fobj in figs['figures']:
        for path in fobj['files']:assert (ROOT/path).stat().st_size>1000
    artifact_hashes={str(p.relative_to(ROOT)):sha(p) for p in scanned}
    # All tracked history is untouched apart from the five changes present on entry.
    dirty=subprocess.check_output(['git','diff','--name-only','-z']).decode().split('\0');dirty=sorted(x for x in dirty if x)
    allowed=['results/q2/q2_battery_calendar.csv','results/q2/q2_box_delivery.csv','results/q2/q2_sorties.csv','results/q2/q2_uav_calendar.csv','results/q3/relay_candidate_gate_stats_raw.csv']
    assert all(x in allowed or x.startswith(('src/p1_5b/','results/p1_5b/')) for x in dirty),dirty
    main=subprocess.check_output(['git','rev-parse','main']).decode().strip();assert main=='c13306ecbc36933502d1197228e5d80f9f7e40cf'
    result=dict(status='PASSED',inherited_sources_unchanged=len(inherited['sources']),explicit_sources=len(entries),default_deny_tests=len(tests['cases']),
      source_accesses_checked=True,forbidden_content_hits=hits,scanned_outputs=artifact_hashes,manuscript_development_jargon_hits=[],
      source_lineage=lineage,F13_workbook_main_metrics_reread=True,full_workbook_audit='Inherited A-stage 22-sheet audit; workbook bytes unchanged',
      workbook_sha256=sha(book),main_unchanged=main,preexisting_tracked_changes_preserved=[x for x in dirty if x in allowed],
      visual_review='All eight PNGs reviewed; dense figures 3, 6, 7 separately inspected; figure 3 overlap and figure 4 ordering corrected',
      boundaries=['No new search','Comparator original audit artifact readmission, not a new full radio run','Reference metadata/abstract/theorem access scopes disclosed','No final PDF/MD5 submission'])
    (paper/'source_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('SOURCE_AUDIT_PASSED',len(entries),'sources',flush=True)
if __name__=='__main__':main()
