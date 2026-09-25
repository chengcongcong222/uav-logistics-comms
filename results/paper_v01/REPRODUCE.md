# 论文 V0.1 构建与复核

在 WSL Ubuntu-24.04 仓库根目录执行：

```bash
.venv/bin/python results/paper_v01/build_paper.py
```

使用既有 Python 环境中的 matplotlib 和 numpy；不调用优化器，不重新生成通信候选，不改动历史执行包。脚本验证 6 个 Q3 源包的原独立验证记录及其中产物哈希，从原 JSON/CSV 提取主表，再生成正文和两幅图的 PNG/SVG/PDF。

- `PAPER_V01.md`：完整中文正文，包含Q1—Q4方法、结果、限定域和局限。
- `PAPER_TEMPLATE.md`：正文源稿；五张数据表由脚本填入。
- `DATA_FREEZE_V1.json`：冻结数值、来源、验证摘要和119项文件哈希。
- `EVIDENCE_MAP.md`：各主张的证据和解释边界。
- `OPEN_ITEMS.md`：G2返航余量敏感性、新主例Q4/提交表、文献与实验待办。
- `BUILD_CHECK.json`：实际生成与源包核对结果。
- `figures/`：联合代表完工—能耗图、原Q2与所选Q3完工对照图。

冻结基准为 `842d950eba19374a287351b9b839fb446ff55d14`。正文故意不吸收并行P1.4尚未验证的数据。图表不连接离散点，不暗示连续前沿；不同阶段的执行包不拼接。

构建只复用已有物理验证证据并核对文件哈希，不能称为本轮重新运行无人机独立物理验证。V0.1是工作稿，正式提交前还需处理OPEN_ITEMS。
