# 科研结论与证据对应

主例、比较例和敏感性分开解释；所有来源必须经当前默认拒绝白名单准入。

## 统一物理与资源模型

正文：3–4。证据方法：官方附件、冻结G2几何及参数。边界：质量/体积/电量/充电/库存，不含真实随机信道证明。

- `results/reset/geometry/transport_uav_types.csv`
- `results/reset/geometry/route_geometry.csv`

## 五档225载荷与18/18/18/19/20架次

正文：5。证据方法：独立标量重算、完整单点子集覆盖MILP。边界：单服务区组合域；不含共享资源并行排程。

- `results/p1_5b/q1_sensitivity/summary.json`
- `results/p1_5b/q1_sensitivity/validation.json`

## 两个架次数阈值与机型更换

正文：5.3。证据方法：子集能量边界及上下侧重新组批。边界：等号可行；边界上方用1e-8余量探测。

- `results/p1_5b/q1_sensitivity/all_capacity_feasible_subsets.csv`
- `results/p1_5b/q1_sensitivity/summary.json`

## 自主模式成员与比较方案准入

正文：6、8。证据方法：原独立核验输出完整性、所有选中模式与自主池相符。边界：原核验工件重准入；比较方案本轮未重跑通信物理验证。

- `results/p1_5b/admission.json`
- `results/p1_5b/admitted_comparators.json`

## F13有限固定结构完工下界

正文：6.3。证据方法：机型占用工作量/库存下界。边界：只属于F13固定箱组/访问/机型。

- `results/p1_5b/fixed_structure_bound.json`

## F13零迟到、24+3、能耗与时间

正文：摘要、7、8、11。证据方法：上阶段重新独立准入的主例及原始执行包。边界：当前阶段性主例，不是全局最优。

- `results/p1_5a/F13_readmission.json`

## 数值全航程通信核验

正文：7.4。证据方法：69003样本、相位/缺口边界及0.1秒细化。边界：不证明任意连续时刻覆盖或随机鲁棒性。

- `results/p1_5a/F13_readmission.json`

## 近快端局部折中

正文：8。证据方法：F12/F16/F13/F18及C01各自原核验结果。边界：有限已验证档案；非完整Pareto，非等算力性能结论。

- `results/p1_5b/admitted_comparators.json`
- `results/p1_5b/figure_data/tradeoffs.csv`

## F13不可拆块、13种分区、分类缺口和CV

正文：9。证据方法：图可达性、无标签完整枚举、独立峰值扫描与着色。边界：F13固定任务及整中继架次依赖域。

- `results/p1_5a/q4/blocks.json`
- `results/p1_5a/q4/independent_validation.json`

## 主例工作簿与正文统一

正文：附录。证据方法：同一执行包和工作簿一致性检查。边界：本轮不改工作簿、不进入最终提交排版。

- `results/p1_5a/submission_consistency.json`
