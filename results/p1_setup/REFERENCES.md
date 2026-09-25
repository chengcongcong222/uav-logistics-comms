# 资料与用途边界（2026-09-25核查）

这里只收录本轮核查过的原始研究页面或机构材料。没有全文访问的论文标记摘要已核，不声称提取了正文公式或现场数值权重。

|编号|资料|本轮核查层级|可以支持|不能支持|
|---|---|---|---|---|
|S1|IFRC，Code of Conduct for the Movement and NGOs in Disaster Relief|机构原网页|救灾优先级按需求确定|本题时间/能耗/架次的固定数值权重|
|S2|Gralla E, Goentzel J, Fine C. Assessing Trade-offs among Multiple Objectives for Humanitarian Aid Delivery Using Expert Preferences. Production and Operations Management, 2014, 23(6):978–989. DOI:10.1111/poms.12110|期刊原页面及摘要已核，未提取全文效用系数|18名有经验的人道物流人员调查；所调查属性中货量最受重视、成本最低；重视关键物资与脆弱社区但不完全排除其他对象|把该调查当成所有灾害的普遍权重；将原系数直接换成分钟、kWh和架次|
|S3|Nepal Earthquake Response ICC. Prioritisation for inter-agency cargo transport, 2015|机构PDF，6页；视觉核查第1、2页；第1页标注10 July，说明15 July由HCT认可|在季风前向重灾、偏远山区提供基本物资；货类与地点优先级可随需要调整；50/40/10为按货重计算的计划份额|把货重份额写成优化目标系数；把这个阶段的顺序视为所有灾害通则|
|S4|应急管理部，东北地区及西南等地迎较强降雨 国家防总办公室、应急管理部持续会商调度指导，2024-08-01|原机构网页，正文最后一段|湖南资兴灾害中无人机用于灾情侦察和通信保障的实际记录|题中中继配置的现场真实性；题中优化方法已在该灾害采用|
|M1|Ropke S, Pisinger D. An Adaptive Large Neighborhood Search Heuristic for the Pickup and Delivery Problem with Time Windows. Transportation Science, 2006, 40(4):455–472. DOI:10.1287/trsc.1050.0135|期刊原页面及摘要已核|基于历史表现调整竞争子启发式使用频率的ALNS机制|已经完成本题适配；自制版本即最新最强基线|
|M2|Mavrotas G, Florios K. An improved version of the augmented epsilon-constraint method (AUGMECON2) for finding the exact Pareto set in Multi-Objective Integer Programming problems. Applied Mathematics and Computation, 2013, 219(18):9652–9669. DOI:10.1016/j.amc.2013.03.002|作者存储版本的摘要/书目信息及期刊条目已核；存储上传时间不当成论文年份|预算约束扫描与加权偏好互补；明确模型范围和求解条件下可研究完备性|直接宣布带连续时刻、本题有界模式池及限时求解获得原问题完整前沿|

本题的主例规则属于基于上述动机的建模选择，不是从资料中找到的一组现场标准权重。下一阶段仍可增补更接近山区洪涝配送的现场决策资料，但不得看过正式结果后反向改规则以指定本方法获胜。

## 原始来源定位

```text
S1 https://www.ifrc.org/our-promise/do-good/code-conduct-movement-ngos
S2 https://journals.sagepub.com/doi/abs/10.1111/poms.12110
S3 https://logcluster.org/sites/default/files/public/prioritisationlistinteragencycargotransporthumanitariancountryteam_150715.pdf
S4 https://www.mem.gov.cn/xw/yjglbgzdt/202408/t20240801_496746.shtml
M1 https://pubsonline.informs.org/doi/10.1287/trsc.1050.0135
M2 https://mpra.ub.uni-muenchen.de/105034/
```
