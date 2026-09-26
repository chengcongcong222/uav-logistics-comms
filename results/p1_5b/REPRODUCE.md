# P1.5-B1 复现

在WSL `Ubuntu-24.04` 的仓库根目录 `/home/ccc/projects/uav-logistics-comms` 执行。使用已有 `.venv`，依赖版本见 `environment.json`。不读取历史竞赛对照文件，不重跑Q2/Q3搜索；不要把全仓库未提交文件一并纳入本分支。

完整数值重算与内容构建：

```bash
export PYTHONDONTWRITEBYTECODE=1
.venv/bin/python -m src.p1_5b.q1
.venv/bin/python -m src.p1_5b.references
.venv/bin/python -m src.p1_5b.admit
.venv/bin/python -m src.p1_5b.data
.venv/bin/python -m src.p1_5b.whitelist
.venv/bin/python -m src.p1_5b.test_guard
.venv/bin/python -m src.p1_5b.build
.venv/bin/python -m src.p1_5b.figures
.venv/bin/python -m src.p1_5b.audit
.venv/bin/python -m src.p1_5b.seal
```

Q1包含完整子集枚举和150次MILP，耗时取决于环境。本轮已实际运行，无随机种子或新算法性能实验。`references`仅从本轮人工核对并保存的正式来源记录生成书目，不会联网抓取任何新页面；其元数据、摘要/定理访问范围记录在文献映射中。

仅重建正文与图片时，先确认原数据未变，再运行`test_guard`、`build`、`figures`、`audit`、`seal`。白名单采用内容校验；不要为绕过失败随意运行`whitelist`吸收未知变化。源码/模板或准入来源确需修改时，应先审查变化，再重新准入并完整核验。

本轮模板为`paper/PAPER_TEMPLATE.md`，结果字段由构建器注入，非模型搜索输入。图用Windows已有Microsoft YaHei和Arial，白名单固定字体内容。其他环境复现需先提供相同字体或明确记录字体替换并更新字体准入；模型数值不依赖字体。

PDF/SVG可能含绘图库生成元数据，复建标准是数值与图形内容一致，不要求创建时间等元数据逐字节相同。每次封存会重新记录实际文件SHA-256。这里的SHA-256用于内部工件核对，不是最终提交MD5。

`audit`会校验全部准入来源，比较工作簿主指标与正文数据、五个比较例与绘图表，并扫描正文/映射/SVG。图像可读性仍需人工检查。历史F13执行包、Q4、工作簿及模式池均保持原内容；原有5个无关跟踪文件变更不属于本轮。

最后只提交`src/p1_5b/`与`results/p1_5b/`。缓存`_mplcache/`和运行日志不纳入封存。不要生成最终论文PDF、AI使用说明或提交MD5；这些属于后续B2。
