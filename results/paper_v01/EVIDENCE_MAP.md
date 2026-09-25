# V0.1 主张—证据映射

本稿冻结于 P1.3-C 基准提交 `842d950`。`DATA_FREEZE_V1.json` 是全文主表的机器可读来源，包含源文件 SHA-256；不是新求解结果。

|正文主张|直接证据|允许表述与边界|
|---|---|---|
|题意、80箱、15区及两类库存|`results/p1_preflight/problem_text.txt` 与各包配置|题意规则与建模选择分列；不编造风场、带宽或功耗项|
|G2航段地形|`results/reset/geometry/validation.json`|240条有向航段由另一实现复核；仍为数值求根，不能扩大成无线解析证明|
|非线性等效航程、爬升能耗、SOC|`docs/model/MODEL_FREEZE_V1.md`|区分题给航程、推导水平能耗及势能建模选择|
|Q1 18次、59.130796 kWh|`results/reset/q1/summary.json`, `validation.json`|单点独立组批，无实体机排程；32776.093秒是累计作业时长|
|Q1安全载荷45点|`results/reset/q1/max_safe_payload.csv`|连续质量—能量边界，具体箱组还需体积检查|
|Q1余量单调性|能量可行域包含关系|载荷界不增、最少架次不减；本版未混用旧几何数值敏感性|
|2903自主运输模式|`results/p1_3b/pool_manifest.json`|完整既有池，不是全局所有路线；296单点+2607两点|
|四方向有效连续池界|`results/p1_3b/finite_pool_extremes.json`、`bounds/*/certificate.json`|与保守网格CP界区分；不存在已证明的连续池全局最优|
|T01/T02/T03等Q2表|`results/p1_3b/representatives/*.json`及各Q2包|各行完整指标，极值方向不能拼接|
|T01固定原时刻有占用冲突|`results/p1_3c/fixed_T01_results.json`, `conflict_certificate_replay.json`|M007/M025/M027，4030.471—4112.655秒；冻结原子完整单站服务域，不是任意交接域不可行|
|动态模式与一致性反馈|`results/p1_3c/MODEL.md`, `decomposition_log.json`|启发式pricing与站点/UAV必要松弛，后验精确能量验证；不是完整列生成|
|三个结构最少3中继架次|`results/p1_3c/full_site_relay_bounds.json`, 各成功Q3包|固定运输结构、118站点和关系、原子不拆域；不推广至连续选址与所有结构|
|四个新Q3数值|`results/p1_3c/independent_audit.json`及对应完整包|4独立执行包、0硬违规、0未覆盖采样；0.5秒+0.1秒边界细化|
|T03固定时刻分支|`T03_C1_FIXED_Q3`，`fixed_timing_comparison.json`|原开始时刻及运输资源日历均不变；保留机制例，不自动称前沿点|
|C01低资源代表|`results/p1_3b/screening/C01/q3/C01/solutions/C01_Q3_001/`|19+4、66.500477 kWh、189.803分钟；非所有低架次方案必然慢|
|A11历史基准|`results/reset/q3/A11/solutions/A11_Q3_001/`|119.860分钟、70.464235 kWh、25+5；新快端不能宣称全面支配它|
|历史Q4 31/90种分区、缺口2/4件|`results/reset/q4/validation.json`及4个代表configuration|只适用A11固定时刻与完整中继依赖，不借给T01/T02|
|6/5项测试，19/9证书、19模型见证|对应p1_3b/p1_3c审计和日志|分阶段分对象统计，不把模型可行解数当执行包数|
|论文图1/2|本目录`DATA_FREEZE_V1.json`、`build_paper.py`|离散代表不连成连续前沿，Q2-Q3差值不是逐任务延误或严格因果消融|

## 容易误写的数值

1. T02原值6153.893309522221秒，T01为6153.896634674075秒。T02仅快0.003325秒；正文不放大该差异。
2. T01的J_norm较T02小，A11又较二者小；完工更短不是每箱交付都更早。
3. T03重排能耗73.772136 kWh、固定时刻73.814577 kWh；不能混用。
4. C01 Q2为19次、62.327910 kWh；C01 Q3为19+4、66.500477 kWh。A03的60.047645 kWh属于另一个Q2结构。
5. 三个中继架次使用两架实体中继；原库存六组件，不等于六组件全部同时被用。
6. 保守网格运输主问题原始bound跨到连续Q3被判无效，正文不报连续Q3 gap=0。

## 不纳入V0.1的旧结论

不复制旧稿180秒五种子优势段落；不转移旧Γ=4认证；不纳入外部截图结果；不将P1.4尚未独立验证的新候选写成结果；不覆盖正式主例、Q4或提交表。
