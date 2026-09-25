# P1.2 复现

WSL Ubuntu-24.04，仓库 /home/ccc/projects/uav-logistics-comms。
使用本分支源码、原始数据和 .venv；新建独立项目副本，保留基础历史输入。
现有结果禁止覆盖。在复现副本中将随提交的 results/p1_2 改名归档，
创建新的 results/p1_2；重新记录该副本实际存在的历史文件哈希。
原运行保护清单含既存未跟踪文件，因此新副本的保护文件数量可能不同。

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
import hashlib,json
roots=['results','data/raw','docs/paper','src/bench_p1','validation']
files=[p for r in roots for p in Path(r).rglob('*') if p.is_file() and '__pycache__' not in str(p) and not str(p).startswith('results/p1_2/')]
Path('results/p1_2/protected_before.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},indent=2))
PY
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python -m unittest src.bench_p1_2.test_driver -v
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python -m src.bench_p1_2.readmission
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python -m src.bench_p1_2.driver --admit
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/bin/python -m src.bench_p1_2.driver --mode DIAGNOSTIC_WARM --seed 26092511
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/bin/python -m src.bench_p1_2.driver --mode DIAGNOSTIC_WARM --seed 26092512
.venv/bin/python -m src.bench_p1_2.finish
```

A11重验失败须立即停止，不能继续portfolio或driver。
只有两个开发种子；不读取评价权重。所有新缓存属于对应运行，不能复制旧缓存加速重跑。
短运行由固定请求数量及单LP三秒上限约束，不是正式CPU预算；审计时间单列。
暖启动包重验独立于候选搜索。最后校验旧文件与main未改，重验完整包绑定哈希。
源码修改必须新建诊断运行，不能原地覆盖证据。
