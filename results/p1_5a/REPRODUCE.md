# 复现P1.5-A

环境：WSL Ubuntu-24.04，仓库虚拟环境，Python依赖沿用当前项目；本轮不新增求解器依赖。

从仓库根目录运行完整顺序门禁：
```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -u -m src.p1_5a.run
```

分步命令：
```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -u -m src.p1_5a.readmission
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -u -m src.p1_5a.q4
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -u -m src.p1_5a.q4_check
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -u -m src.p1_5a.submission
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest src.p1_5a.test_source_guard -v > results/p1_5a/source_guard_tests.log 2>&1
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -u -m src.p1_5a.firewall freeze
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -u -m src.p1_5a.build_paper
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -u -m src.p1_5a.firewall audit
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -u -m src.p1_5a.seal
```

全部重新计算写入results/p1_5a，不改历史目录。整链复现会更新本轮验证运行时和XLSX容器时间戳，因此文件哈希需重新封存；物理指标、固定分区和工作簿内容应一致。不要将哈希变化当成物理结果变化。

本轮没有随机优化实验。Q4枚举、验证及工作簿构建均为确定性过程。输入与产物SHA256分别见F13_readmission.json、provenance/、PAPER_SOURCE_WHITELIST.json及artifact_manifest.json。

Q4固定整架中继及其保障关系，分组资源必须独立；缺口需要增配而非静默放宽库存。

论文后续构建必须通过src/p1_5a/source_guard.py读取白名单来源，旧results/paper_v01/build_paper.py不在新发布流程中。新增学术依据或V0.2数据须先明确审核加入白名单。
