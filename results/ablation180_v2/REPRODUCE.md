# 复现与审计说明

正式数据仅为本目录的15次运行，协议为 `CPU180_FIVE_SEEDS_Q2_V2`。原 G2 主线以提交 `4ae3d2d0d584d648c814e1b7c2d98613237a920e` 为历史基准，数学结果与工作簿保持不变。

## 环境与预算

工作目录为仓库根目录，运行环境是 Ubuntu-24.04 WSL、仓库 `.venv`；完整 Python 版本、CPU 拓扑及运行前代码哈希见 [protocol.json](protocol.json)。正式机器为 Intel i5-12400F，三种方法各使用一个不同物理核心并逐种子轮换。进程环境限制 OPENBLAS/OMP/MKL/NUMEXPR 为单线程。冻结输入几何为 G2；公共几何预处理不计入180秒预算。

种子为250901、250902、250903、250904、250905。每次180秒为统一进程CPU上限；只有完整保存且 `cpu_ready_s <= 180` 的检查点计入统计。预算保护可能提前结束，无须空耗剩余时间。独立验证与绘图在搜索结束后执行。

## 复核现有证据

以下 Gate 命令读取已保存的独立验证证据，逐项核验哈希与计时，不重跑搜索；它会重新生成本目录 gate.json：

```bash
.venv/bin/python -m unittest validation.mathematical.test_ablation_accounting
.venv/bin/python validation/mathematical/ablation_gate.py
```

统计与图表生成入口为 `src.bench.report`，论文与交接生成入口为 `src.bench.paper`，时钟校准入口为 `src.bench.calibrate`。这些入口写入本权威目录，审计已有发布版本时不要无故重写结果；如需再生成，应在独立工作副本执行，最后重新绑定 Gate 哈希。新增统计代码不改变协议中已冻结的搜索代码。

## 从头重跑搜索

必须使用全新的输出目录。不要直接向本权威目录启动 runner：程序会先写协议，再检查各运行目录是否已存在。

```bash
test ! -e results/ablation180_reproduction
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 PYTHONHASHSEED=0 .venv/bin/python -m src.bench.run --budget 180   --seeds 250901 250902 250903 250904 250905   --root results/ablation180_reproduction
```

重跑前应确认三个所选逻辑核心对应不同物理核心；当前核心选择针对本次记录的机器，并非通用拓扑调度器。有限CPU预算会受求解器运行时波动影响，不承诺逐字节重现每个候选。新运行是新的实验，不能合并进原15次统计。汇总与 Gate 目前绑定权威目录，复核新实验须在独立工作副本明确修改对应输出位置并形成新协议/审计记录。

## 已排除的试运行与初版

`results/ablation_pilot` 与 `results/ablation_pilot_v2` 是12秒计时/落盘试运行。第一版180秒实验因 /proc 观测值与 SIGXCPU 保护触发不一致，整批失效；原因未被证明为某种内核缺陷。原协议、监控记录、日志及当时代码保存在 `results/ablation180`，失效声明为 `timing_invalid.json`。修正计时方式后，全部15次重新开始，没有保留初版中的有利结果。

提交包含正式预算内完整执行包和审计，以及失效/试运行的协议与日志。强制停止时的 `partial/`、临时文件、失效批次执行包不作为正式交付方案；本地保留，不进入汇总。

## 数据含义

141个独立验证检查点是执行包数量，并非141个独立测试实例；13个新增支配反例属于本次Q2实验。原 G2 的21个Q3执行包和7个Q3反例另行统计。本次比较只支持本实例、三个具体Q2实现、五个种子与180秒预算的结论。正式A11_Q3_001、Q4和提交工作簿没有因本实验替换。
