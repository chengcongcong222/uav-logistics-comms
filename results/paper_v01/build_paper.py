"""Build the paper from frozen, independently validated source artifacts.

Run from repository root: .venv/bin/python results/paper_v01/build_paper.py
This script performs no optimization and writes only results/paper_v01.
"""
from pathlib import Path
import csv
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'results/paper_v01'
SOURCES = {}
VERIFIED_ARTIFACT_HASHES = 0


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read(path):
    p = ROOT / path
    SOURCES[path] = sha(p)
    return json.loads(p.read_text())


def write(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def table(headers, rows):
    return '\n'.join(['|' + '|'.join(headers) + '|', '|' + '|'.join(['---'] * len(headers)) + '|'] + ['|' + '|'.join(map(str, row)) + '|' for row in rows])


def freeze_package(label, package, pid, role):
    global VERIFIED_ARTIFACT_HASHES
    mpath = f'{package}/joint_metrics_{pid}.json'
    metrics = read(mpath)
    vpath = f'{package}/validation_0.5.json'
    validation = read(vpath)
    assert validation['hard_violations'] == 0
    assert validation['uncovered_sample_count'] == 0
    assert metrics['J_late'] == 0
    for p, digest in validation['artifact_sha256'].items():
        assert sha(ROOT / p) == digest, p
        VERIFIED_ARTIFACT_HASHES += 1
        SOURCES[p] = digest
    return {'label': label, 'role': role, 'source_package': package,
            'metrics_source': mpath, 'validation_source': vpath,
            'metrics': metrics, 'validation_summary': {k: validation.get(k) for k in ['status', 'step_s', 'boundary_refinement_s', 'full_flight_samples', 'hard_violations', 'uncovered_sample_count']}}


def main():
    audit = read('results/p1_3c/independent_audit.json')
    q3 = []
    for item in audit['packages']:
        pid = item['pid']
        fixed = 'C1_FIXED' in item['package']
        label = pid + (' fixed' if fixed else '')
        role = 'communication_friendly_fixed_timing' if fixed else ('supplementary_rescheduled' if pid == 'T03' else 'coequal_fast_representative')
        q3.append(freeze_package(label, item['package'], pid, role))
    q3.append(freeze_package('C01', 'results/p1_3b/screening/C01/q3/C01/solutions/C01_Q3_001', 'C01', 'low_resource_representative'))
    q3.append(freeze_package('A11', 'results/reset/q3/A11/solutions/A11_Q3_001', 'A11', 'historical_reference_and_Q4_source'))
    q1 = read('results/reset/q1/summary.json')
    q1_validation = read('results/reset/q1/validation.json')
    bounds = read('results/p1_3b/finite_pool_extremes.json')
    q2 = []
    for pid in ['T01', 'T02', 'T03', 'C01', 'N01', 'H_A03', 'H_A11']:
        x = read(f'results/p1_3b/representatives/{pid}.json')
        q2.append({'label': pid, 'metrics': x['metrics'], 'source_package': x['package']})
    q4_validation = read('results/reset/q4/validation.json')
    q4 = []
    for pid, role in [('Q4_K2_005', '缺口优先'), ('Q4_K3_060', '缺口优先'), ('Q4_K2_016', '均衡优先'), ('Q4_K3_030', '均衡优先')]:
        c = read(f'results/reset/q4/solutions/{pid}/configuration.json')
        q4.append({'id': pid, 'role': role, **{k: c[k] for k in ['k', 'total_resource_units', 'total_shortage_units', 'workload_cv', 'shortage', 'resources', 'inventory']}})
    relay_bounds = read('results/p1_3c/full_site_relay_bounds.json')
    read('results/p1_3c/bound_transfer_audit.json')
    read('results/p1_3c/fixed_T01_results.json')
    read('results/reset/geometry/validation.json')
    for p in ['results/p1_preflight/problem_text.txt', 'results/p1_preflight/problem_equations.json', 'docs/model/MODEL_FREEZE_V1.md', 'docs/model/Q2_SEMANTICS.md', 'docs/model/Q3_COMMUNICATION_SEMANTICS.md', 'docs/model/Q4_PARTITION_SEMANTICS.md', 'results/p1_3c/MODEL.md', 'results/p1_3b/MODEL.md']:
        SOURCES[p] = sha(ROOT / p)
    pp = ROOT / 'results/reset/q1/max_safe_payload.csv'
    SOURCES[str(pp.relative_to(ROOT))] = sha(pp)
    payload = list(csv.DictReader(pp.open()))
    freeze = {'version': 'PAPER_DATA_V1', 'frozen_base_commit': '842d950eba19374a287351b9b839fb446ff55d14',
              'geometry': 'G2_UTM49N_STRAIGHT_NATIVE_SUPERCOVER_V1', 'Gamma_C_db': 0,
              'status': 'DRAFT_WITH_EXPLICIT_OPEN_ITEMS', 'Q4_source': 'A11_Q3_001', 'new_fast_solution_Q4_recomputed': False,
              'strict_equal_cpu_multiseed_advantage_claimed': False, 'global_pareto_proven': False,
              'q1': {'summary': q1, 'validation': q1_validation, 'payload': payload},
              'q2': q2, 'q2_extremes': bounds['results'], 'q3': q3, 'q4_historical': q4,
              'q4_validation_scope': q4_validation['scope'],
              'relay_lower_bounds': [{k: b[k] for k in ['pid', 'relay_sorties_lower_bound', 'unique_site_masks', 'two_mask_combinations_checked', 'scope', 'total_tasks']} for b in relay_bounds],
              'sources_sha256': SOURCES}
    write('DATA_FREEZE_V1.json', freeze)
    paper = (OUT / 'PAPER_TEMPLATE.md').read_text()
    paper = paper.replace('{{BOUNDS_TABLE}}', table(['方向', '已验证上界', '有效下界', '相对间隙', '上界方案'], [[r['anchor'], f"{r['upper_bound']:.6f}", f"{r['valid_full_pool_lower_bound']:.6f}", f"{r['relative_gap'] * 100:.2f}%", r['verified_incumbent']] for r in bounds['results']]))
    paper = paper.replace('{{Q2_TABLE}}', table(['运输结构', 'J_late', 'J_norm', '运输完工/s', '能耗/kWh', '运输架次'], [[r['label'], '0', f"{r['metrics']['J_norm']:.6f}", f"{r['metrics']['makespan']:.3f}", f"{r['metrics']['energy']:.6f}", r['metrics']['sorties']] for r in q2]))
    paper = paper.replace('{{Q3_TABLE}}', table(['联合代表', 'J_norm', '联合完工/min', '总能耗/kWh', '运输架次', '中继架次', '用途'], [[r['label'], f"{r['metrics']['J_norm']:.6f}", f"{r['metrics']['joint_makespan_s'] / 60:.3f}", f"{r['metrics']['total_energy_kwh']:.6f}", r['metrics']['transport_sorties'], r['metrics']['relay_sorties'], {'T01':'快速端，交付较早','T02':'快速端，能耗较低','T03':'同结构重排补充','T03 fixed':'原运输日历不变','C01':'低资源端','A11':'历史基准'}[r['label']]] for r in q3]))
    paper = paper.replace('{{Q4_TABLE}}', table(['分组数', '方案', '规则', '需求件数', '缺口件数', '工作量CV'], [[r['k'], r['id'], r['role'], r['total_resource_units'], r['total_shortage_units'], f"{r['workload_cv']:.6f}"] for r in q4]))
    by_payload = {(r['service_id'], r['uav_type']): float(r['payload_limit_kg']) for r in payload}
    paper = paper.replace('{{PAYLOAD_TABLE}}', table(['服务区', 'A型', 'B型', 'C型'], [[f'S{i:03d}'] + [f"{by_payload[(f'S{i:03d}', g)]:.3f}" for g in 'ABC'] for i in range(1, 16)]))
    assert '{{' not in paper
    (OUT / 'PAPER_V01.md').write_text(paper)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    (OUT / 'figures').mkdir(exist_ok=True)
    plt.rcParams.update({'font.size': 10, 'svg.hashsalt': 'paper_v01', 'axes.spines.top': False, 'axes.spines.right': False})
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), gridspec_kw={'width_ratios':[1.05,1]})
    colors = {'T01':'#ad3e2b','T02':'#126f96','T03':'#348153','T03 fixed':'#99852c','C01':'#71549a','A11':'#696969'}
    offsets = {'T01':(8,5),'T02':(8,7),'T03':(8,-15),'T03 fixed':(8,7),'C01':(8,7),'A11':(8,7)}
    for panel, ax in enumerate(axes):
        for row in q3:
            m = row['metrics']; name = row['label']
            ax.scatter(m['joint_makespan_s']/60, m['total_energy_kwh'], color=colors[name], s=65, edgecolor='white', zorder=3)
            if panel == 1 or name in ['A11', 'C01']:
                ax.annotate(f"{name} ({m['transport_sorties']}T+{m['relay_sorties']}R)", (m['joint_makespan_s']/60, m['total_energy_kwh']), xytext=offsets[name], textcoords='offset points', fontsize=8)
        ax.set_xlabel('Joint makespan (min)'); ax.set_ylabel('Total energy (kWh)'); ax.grid(alpha=.2)
    axes[0].set(xlim=(99,214), ylim=(65,76), title='Validated representative archive')
    axes[0].text(112, 74.85, 'Fast-region points: see right panel', fontsize=8)
    axes[1].set(xlim=(101.8,110.6), ylim=(73.60,74.72), title='Fast-region detail')
    fig.tight_layout()
    for ext in ['png','svg','pdf']: fig.savefig(OUT / f'figures/q3_tradeoff.{ext}', dpi=200, metadata={'Creator':'paper_v01'})
    plt.close(fig)
    selected = [r for r in q3 if r['label'] != 'T03']
    lookup = {r['label'].replace('H_', ''):r['metrics']['makespan']/60 for r in q2}
    names = [r['label'] for r in selected]
    q2mins = [lookup[n.replace(' fixed','')] for n in names]
    q3mins = [r['metrics']['joint_makespan_s']/60 for r in selected]
    fig, ax = plt.subplots(figsize=(8,4.6))
    import numpy as np
    xpos = np.arange(len(names))
    ax.bar(xpos-.19, q2mins, width=.38, color='#719bb3', label='Original Q2 return time')
    ax.bar(xpos+.19, q3mins, width=.38, color='#b58a57', label='Validated Q3 joint return time')
    for x, a, b in zip(xpos, q2mins, q3mins):
        ax.text(x-.19,a+1,f'{a:.2f}',ha='center',fontsize=8)
        ax.text(x+.19,b+1,f'{b:.2f}',ha='center',fontsize=8)
    ax.set_xticks(xpos,names); ax.set_ylabel('Makespan (min)'); ax.set_ylim(0,max(q3mins)*1.18)
    ax.legend(frameon=False); ax.grid(axis='y',alpha=.2); ax.set_axisbelow(True)
    fig.tight_layout()
    for ext in ['png','svg','pdf']: fig.savefig(OUT / f'figures/q2_q3_makespan.{ext}',dpi=200,metadata={'Creator':'paper_v01'})
    plt.close(fig)
    checks = {'sources_hashed_for_freeze': len(SOURCES), 'q3_artifact_hashes_compared_to_original_validation': VERIFIED_ARTIFACT_HASHES, 'q3_packages_with_original_validation_and_artifact_hashes_verified': len(q3),
              'generated_table_count':5, 'figure_count':2, 'old_results_modified':False,
              'q1_G2_rho_sensitivity_complete':False, 'new_main_Q4_complete':False,
              'paper_status':'V01_DRAFT_NOT_FINAL_SUBMISSION', 'unresolved_template_tokens':False}
    write('BUILD_CHECK.json', checks)
    print(json.dumps(checks, ensure_ascii=False))


if __name__ == '__main__':
    main()
