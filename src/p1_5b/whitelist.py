"""Explicit B1 additions to the immutable A-stage source policy."""
from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'results/p1_5b'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    old=ROOT/'results/p1_5a/PAPER_SOURCE_WHITELIST.json';policy=json.loads(old.read_text())
    entries={x['path']:x for x in policy['sources']}
    for p,e in entries.items():assert sha(ROOT/p)==e['sha256']
    def add(p,category,reason):
        rel=p.relative_to(ROOT).as_posix()
        entries[rel]=dict(path=rel,sha256=sha(p),category=category,admission_reason=reason)
    audit=json.loads((OUT/'admission.json').read_text())
    for rel,h in audit['added_sources'].items():
        assert sha(ROOT/rel)==h
        add(ROOT/rel,'EXPLICITLY_REQUESTED_AUTONOMOUS_COMPARATOR','Original validator artifact hashes and full autonomous pattern membership checked')
    for directory in ['q1_sensitivity','references','figure_data']:
        for p in (OUT/directory).rglob('*'):
            if p.is_file() and p.suffix in ['.json','.csv']:add(p,'B1_NEW_VALIDATED_DERIVATIVE' if directory!='references' else 'FORMAL_ACADEMIC_STANDARD_REFERENCE','Explicit B1 task; source and use boundaries recorded')
    for name in ['admission.json','admitted_comparators.json','fixed_structure_bound.json']:
        add(OUT/name,'B1_ADMISSION_RESULT','Explicitly requested autonomous comparison')
    template=OUT/'paper/PAPER_TEMPLATE.md'
    if template.exists():add(template,'AUTHOR_MANUSCRIPT_TEMPLATE','Narrative only; numerical result tables inserted from admitted artifacts')
    fonts=[Path('/mnt/c/Windows/Fonts/msyh.ttc'),Path('/mnt/c/Windows/Fonts/arial.ttf')]
    result=dict(version=2,inherited_policy_sha256=sha(old),default_action='DENY',
        publication_builder='src/p1_5b/build.py',figure_builder='src/p1_5b/figures.py',
        additions_authorized_by='P1.5-B1 user task: five reserve levels, autonomous local tradeoffs, low-resource role, formal literature, rebuilt figures',
        historical_manuscripts='Structure reference only; not admitted as numerical evidence or loaded by final builder',
        excluded_categories=policy['blocked_data_categories'],
        sources=sorted(entries.values(),key=lambda x:x['path']),
        runtime_fonts=[dict(path=str(p),sha256=sha(p),role='Rendering only, not scientific evidence') for p in fonts])
    (OUT/'PAPER_SOURCE_WHITELIST.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('B1_WHITELIST',len(entries),flush=True)
if __name__=='__main__':main()
