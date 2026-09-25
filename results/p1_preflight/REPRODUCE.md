# P1.1 复现与边界

基准为c13306ecbc36933502d1197228e5d80f9f7e40cf，工作分支p1-preflight。原始启动包完整导入，未覆盖同名异内容文件。库版本、输入与偏好哈希见resolved_protocol.json；每批次开始时的协议和源码快照保存在runs/下。

没有正式算法比较，没有运行260926xx正式种子，没有使用64组仅评价偏好评分或调参。这里的输出是开发接口记录与独立验证证据，不能据其重复运行次数作胜负统计。

## 复核现有证据

仓库根目录、原.venv环境：

```bash
.venv/bin/python -m unittest discover -s validation/p1_setup -v
.venv/bin/python -m unittest discover -s validation/mathematical -p test_ablation_accounting.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/bin/python -m src.bench_p1.audit
.venv/bin/python -m src.bench_p1.finish
```

audit检查每个预算内完整执行包。已有独立验证文件先复核全部哈希；不存在时才完整重算。Q3全过程通信验证为0.5秒加边界细化。finish检查历史保全、计时与开发结果后汇总正式准入阻塞，不启动搜索。测试会重新写small_domain_certificate.json等开发报告；重验建议在独立工作副本执行，并重新生成gate。

顺序修补阳性控制：

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/bin/python -m src.bench_p1.sequential_fixture
```

它将本轮已验证JOINT执行包的运输时刻固定，再检查顺序修补能否闭合；不是给比较算法赠送该见证作初始解，也不计入冷启动成功数。

## 新开发运行

仅开发种子26092511/26092512可用。必须使用不存在的新目录后缀，例如：

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
.venv/bin/python -m src.bench_p1.run Q2 --budget 30 --revision reproduction1
```

run拒绝覆盖既有目录。任务规定梯度30/120/300秒，同层全部方法同预算。不要在本轮结束后自行扩为600秒正式实验。超预算或中断的partial目录不算成绩。

本轮发生过实现修正：Q2 v1/v2为初始共享算子uniform诊断，v3恢复历史uniform；Q3 120 v2有运行中接线修改，整批仅诊断；300 v3识别固定运输正例中的人为分离缓冲问题，300 v4是修正核后同预算重跑。所有运行记录保留。不同源码/预算阶段不能混成一个性能样本。审计适配器的标签合并和验证结果缓存修复均属独立事后验证代码，不改变搜索。

## 数值状态

normalization.json和budget_queries.json给出共同开发范围、正尺度回退、原始单位预算和无见证断面，但正式参数尚未冻结。Q3目前完成有限请求流程原型，尚未完成整个预算内的多偏好档案驱动。gate为P1_BLOCKED时不得启动正式比较。

原题文本与公式提取、19份原始文件哈希、物理负例和阳性fixture均保留。独立验证阶段会为Q3指标文件补充审计标签；搜索CPU记录对应完整求解包，最后哈希对应独立审计后的交付版本。负例fixture不属于可行解档案。
