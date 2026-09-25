"""Freeze allowed source graph and scan publication artifacts without importing legacy results."""
import re,json,hashlib,zipfile
from pathlib import Path
from src.p1_5a.common import *
PATTERNS={
 'competition_peer_reference':re.compile(r'网友|其他队伍|其他参赛|外部挑战|external\s+challenge|UNVERIFIED_EXTERNAL_CHALLENGE',re.I),
 'excluded_structure_id':re.compile(r'(?<![A-Za-z0-9])(?:B0[12]|XB\d*|R0[1-9]_Q[23])(?=$|[^A-Za-z0-9])',re.I),
 'answer_site':re.compile(r'zhihu\.com|csdn\.net|bilibili\.com|tieba\.baidu|竞赛解答|竞赛答案',re.I)}
def scan_text(text):
    return [{'category':k,'line':text.count('\n',0,m.start())+1} for k,p in PATTERNS.items() for m in p.finditer(text)]
def scan_file(p):
    if p.suffix.lower() in ['.md','.txt','.json','.csv','.svg']:
        return scan_text(p.read_text(errors='replace'))
    if p.suffix.lower() in ['.xlsx','.docx']:
        hits=[]
        with zipfile.ZipFile(p) as z:
            for n in z.namelist():
                if n.endswith(('.xml','.rels')):
                    hits.extend([dict(x,part=n) for x in scan_text(z.read(n).decode('utf-8',errors='replace'))])
        return hits
    return None

def freeze():
    require_admitted()
    entries={}
    def add(p,category,parents=(),purpose='data'):
        p=Path(p);rel=p.relative_to(ROOT).as_posix()
        assert p.is_file()
        assert not rel.startswith(('results/xb1/','results/quality_reset/','results/reset/controls'))
        entries[rel]=dict(path=rel,sha256=digest(p),category=category,parents=list(parents),purpose=purpose)
        return rel
    raw=[add(p,'OFFICIAL_PROBLEM_AND_ATTACHMENTS') for p in (ROOT/'data/raw').rglob('*') if p.is_file()]
    processed=[]
    for name in ['boxes.csv','nodes.csv','transport_uav_types.csv','transport_uavs.csv','transport_batteries.csv','relay_uav_types.csv','relay_uavs.csv','relay_energy_components.csv','communication_parameters.json','dem_metadata.json']:
        processed.append(add(ROOT/'data/processed'/name,'OFFICIAL_DATA_DERIVATIVE',raw))
    geom=[]
    for name in ['boxes.csv','nodes.csv','transport_uav_types.csv','transport_uavs.csv','transport_batteries.csv','relay_uav_types.csv','relay_uavs.csv','relay_energy_components.csv','communication_parameters.json','route_geometry.csv']:
        geom.append(add(GEOMETRY/name,'AUTONOMOUS_G2_PHYSICS',processed))
    geocheck=add(OUT/'provenance/geometry_check.json','INDEPENDENT_VALIDATION',geom+raw)
    add(OUT/'provenance/independent_geometry.csv','INDEPENDENT_VALIDATION',geom+raw)
    pool=add(ROOT/'results/p1_3b/inputs/pattern_pool.json','AUTONOMOUS_PATTERN_POOL',geom)
    rep=add(ROOT/'results/p1_4/representatives/F13.json','AUTONOMOUS_TRANSPORT_STRUCTURE',[pool])
    src=add(SOURCE/'q2/pareto_schedules/F13/missions.json','AUTONOMOUS_TRANSPORT_STRUCTURE',[rep,pool])
    siteparents=[]
    for rel in read(ROOT/'results/p1_preflight/site_provenance.json')['sources']:
        siteparents.append(add(ROOT/rel,'AUTONOMOUS_HISTORICAL_SITE_COORDINATES',processed+raw,purpose='coordinate_lineage_only'))
    sitechain=add(OUT/'provenance/site_chain.json','INDEPENDENT_PROVENANCE_CHECK',siteparents)
    incumbent=add(OUT/'provenance/incumbent_origin.json','INDEPENDENT_PROVENANCE_CHECK',[pool,rep])
    patterncheck=add(OUT/'provenance/pattern_chain.json','INDEPENDENT_PROVENANCE_CHECK',[pool,rep,src])
    execpaths=[]
    for p in PACKAGE.iterdir():
        if p.suffix=='.csv' and not p.name.startswith('communication_violations'):
            execpaths.append(add(p,'READMITTED_F13_EXECUTION',[src,sitechain,geocheck]))
    metrics=add(PACKAGE/'joint_metrics_F13.json','READMITTED_F13_METRICS',execpaths)
    val=add(PACKAGE/'validation_0.5.json','INDEPENDENT_VALIDATION',execpaths+[metrics,geocheck])
    admission=add(OUT/'F13_readmission.json','MAIN_CANDIDATE_ADMISSION',[val,patterncheck,sitechain,incumbent])
    q1=[]
    for p in (ROOT/'results/reset/q1').iterdir():
        if p.suffix in ['.json','.csv']:q1.append(add(p,'AUTONOMOUS_G2_Q1',geom))
    q4=[]
    for p in (OUT/'q4').rglob('*'):
        if p.is_file() and p.suffix in ['.json','.csv']:
            q4.append(add(p,'F13_FIXED_TASK_PARTITION',execpaths+[admission]))
    # Machine-readable metrics are the only facts the new paper builder uses.
    facts=dict(main_candidate='F13',status='CURRENT_AUTONOMOUS_MAIN_CANDIDATE',
        metrics=read(OUT/'F13_readmission.json')['metrics'],
        validation={k:read(PACKAGE/'validation_0.5.json')[k] for k in ['full_flight_samples','hard_violations','uncovered_sample_count','step_s','boundary_refinement_s']},
        q1=read(ROOT/'results/reset/q1/validation.json'),
        q4=read(OUT/'q4/independent_validation.json'),
        scope='Fixed F13 executable solution and fixed-task partitions. No global optimality or complete Pareto claim.')
    write(OUT/'publication_facts.json',facts)
    add(OUT/'publication_facts.json','PUBLICATION_FACTS',[admission]+q1+q4)
    add(OUT/'submission_consistency.json','INDEPENDENT_WORKBOOK_READBACK',[admission]+q4+q1)
    for p in (OUT/'submission').iterdir():
        if p.is_file():add(p,'F13_SUBMISSION',[admission]+q4+q1)
    # No academic literature or rules have been fetched this stage.
    policy=dict(version=1,base_commit=BASE,default_action='DENY',hash_policy='SHA256_REQUIRED_AT_EVERY_READ',
        publication_entrypoint='src/p1_5a/build_paper.py',publication_output='results/p1_5a/paper_export',
        legacy_paper_builders_authorized=False,
        source_categories_allowed=['OFFICIAL_PROBLEM_AND_ATTACHMENTS','OFFICIAL_RULES_IF_EXPLICITLY_ADMITTED','OFFICIAL_DATA_DERIVATIVE','AUTONOMOUS_RESULT','INDEPENDENT_VALIDATION','FORMAL_ACADEMIC_STANDARD_GOVERNMENT_BACKGROUND_IF_EXPLICITLY_ADMITTED'],
        blocked_data_categories=['OTHER_COMPETITION_SOLUTIONS','SOCIAL_FORUM_ANSWERS','EXTERNAL_CHALLENGE_RESULTS','EXTERNAL_STRUCTURE_CONTROLS','TARGETS_DERIVED_FROM_COMPETITION_ANSWERS'],
        blocked_paths=['results/xb1/**','results/quality_reset/**','external control packages','historical R/B/XB solution packages'],
        documents_with_UNVERIFIED_EXTERNAL_CHALLENGE_allowed=False,
        official_rules_verified_this_stage=False,academic_sources_added_this_stage=[],
        evidence_graph_scope='Explicit admitted file dependency graph; source filenames and historical serializer names are not themselves external solution data',
        sources=sorted(entries.values(),key=lambda x:x['path']))
    write(OUT/'PAPER_SOURCE_WHITELIST.json',policy)
    print('WHITELIST',len(entries),flush=True)

def audit():
    legacy=[];binary=[]
    for p in (ROOT/'results/paper_v01').rglob('*'):
        if not p.is_file():continue
        if p.suffix=='.py':continue
        hits=scan_file(p)
        if hits is None:
            binary.append(dict(path=str(p.relative_to(ROOT)),action='EXCLUDED_FROM_NEW_EXPORT_UNSCANNED_BINARY'))
        elif hits:legacy.append(dict(path=str(p.relative_to(ROOT)),hits=hits))
    current=[]
    for folder in [OUT/'paper_export',OUT/'submission']:
        for p in folder.rglob('*'):
            if p.is_file():
                hits=scan_file(p)
                assert hits is not None, 'New export contains unscanned format'
                current.append(dict(path=str(p.relative_to(ROOT)),sha256=digest(p),hits=hits))
    assert all(not x['hits'] for x in current)
    policy=read(OUT/'PAPER_SOURCE_WHITELIST.json');entries={x['path']:x for x in policy['sources']}
    assert all(digest(ROOT/rel)==v['sha256'] for rel,v in entries.items())
    assert all(parent in entries for x in entries.values() for parent in x['parents'])
    visited=set();pending=set()
    def visit(p):
        assert p not in pending,'Cycle in admitted evidence graph'
        if p in visited:return
        pending.add(p)
        for parent in entries[p]['parents']:visit(parent)
        pending.remove(p);visited.add(p)
    for p in entries:visit(p)
    write(OUT/'paper_source_audit.json',dict(status='PASSED',new_export_clean=True,
      whitelist_entries=len(entries),graph_acyclic=True,hashes_verified=True,
      legacy_paper_findings=legacy,legacy_binary_quarantine=binary,
      legacy_policy='Historical V0.1 is retained unchanged and excluded wholesale from the new publication export; scan hits are not silently edited away',
      export_files=current,source_guard='API and process-wide file-open hook; exact path plus SHA256; legacy builder not authorized',
      claim_limit='This verifies recorded data lineage and enforced file access. It does not establish that historical human reasoning had no unrecorded influence.',
      V02_body_not_generated=True))
    print('FIREWALL_SCAN',len(current),'clean; legacy flagged',len(legacy),'binary excluded',len(binary),flush=True)
if __name__=='__main__':
    import argparse
    a=argparse.ArgumentParser();a.add_argument('action',choices=['freeze','audit']);args=a.parse_args()
    if args.action=='freeze':freeze()
    else:audit()
