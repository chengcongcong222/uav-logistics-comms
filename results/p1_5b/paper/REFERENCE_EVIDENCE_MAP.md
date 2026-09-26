# 正式文献与正文用途

按问题类别组织。以下书目信息来自出版者、标准机构或作者正式记录；所核对范围见每条记录，不将摘要核对表述为全文阅读。具体题目参数和性能结果均不能由这些方法文献代替。

## 1. humanitarian/emergency UAV logistics

[1] Boualem Rabta, Christian Wankmüller, Gerald Reiner. A drone fleet model for last-mile distribution in disaster relief operations. International Journal of Disaster Risk Reduction, 28:107–112, 2018. [10.1016/j.ijdrr.2018.02.020](https://doi.org/10.1016/j.ijdrr.2018.02.020).

- 支撑：载荷与能源约束下无人机应急末端配送的建模背景。
- 不支撑：不支持本题具体性能、通信模型或现场部署结论。
- 核对范围：Publisher metadata and abstract。
- 原始记录：[A drone fleet model for last-mile distribution in disaster relief operations](https://www.sciencedirect.com/science/article/pii/S2212420918302000)。
- 正文位置：1 引言；2.1 应急物流与异构运力。

## 2. heterogeneous vehicle/UAV routing

[2] B. Golden, A. Assad, L. Levy, F. Gheysens. The fleet size and mix vehicle routing problem. Computers & Operations Research, 11(1):49–66, 1984. [10.1016/0305-0548(84)90007-8](https://doi.org/10.1016/0305-0548(84)90007-8).

- 支撑：异构机型配置与路线选择需要共同考虑。
- 不支撑：其车辆成本模型不直接替代本题无人机物理模型。
- 核对范围：Publisher metadata and abstract。
- 原始记录：[The fleet size and mix vehicle routing problem](https://www.sciencedirect.com/science/article/pii/0305054884900078)。
- 正文位置：2.1 应急物流与异构运力。

## 3. battery/resource scheduling and charging

[3] Alejandro Montoya, Christelle Guéret, Jorge E. Mendoza, Juan G. Villegas. The electric vehicle routing problem with nonlinear charging function. Transportation Research Part B: Methodological, 103:87–110, 2017. [10.1016/j.trb.2017.02.004](https://doi.org/10.1016/j.trb.2017.02.004).

- 支撑：充电时长与荷电状态的非线性关系应进入可执行排程。
- 不支撑：不支持本题65%/35%充电系数；具体参数来自官方附件。
- 核对范围：Publisher metadata and abstract。
- 原始记录：[The electric vehicle routing problem with nonlinear charging function](https://www.sciencedirect.com/science/article/pii/S0191261516304556)。
- 正文位置：2.2 模式选择、邻域搜索与充电排程；4.3 通过独立日历落实实体资源。

## 4. ALNS / large-neighborhood search

[4] Stefan Ropke, David Pisinger. An Adaptive Large Neighborhood Search Heuristic for the Pickup and Delivery Problem with Time Windows. Transportation Science, 40(4):455–472, 2006. [10.1287/trsc.1050.0135](https://doi.org/10.1287/trsc.1050.0135).

- 支撑：算子按历史表现竞争的自适应邻域方法类别。
- 不支撑：不支持本方法属于ALNS，也不支持本题性能优于该方法。
- 核对范围：Publisher metadata and abstract。
- 原始记录：[An Adaptive Large Neighborhood Search Heuristic for the Pickup and Delivery Problem with Time Windows](https://pubsonline.informs.org/doi/10.1287/trsc.1050.0135)。
- 正文位置：2.2 模式选择、邻域搜索与充电排程。

## 5. set partitioning / route-pattern approaches

[5] M. L. Balinski, R. E. Quandt. On an Integer Program for a Delivery Problem. Operations Research, 12(2):300–304, 1964. [10.1287/opre.12.2.300](https://doi.org/10.1287/opre.12.2.300).

- 支撑：以整数变量表达配送覆盖与组合选择的方法基础。
- 不支撑：不支持本题有限模式池具有全路径完备性。
- 核对范围：Publisher metadata and abstract。
- 原始记录：[On an Integer Program for a Delivery Problem](https://pubsonline.informs.org/doi/10.1287/opre.12.2.300)。
- 正文位置：2.2 模式选择、邻域搜索与充电排程。

## 6. Benders / decomposition logic

[6] John Hooker. Logic-Based Benders Decomposition: Theory and Applications. Springer, Synthesis Lectures on Operations Research and Applications, 2024. [10.1007/978-3-031-45039-6](https://doi.org/10.1007/978-3-031-45039-6).

- 支撑：主问题与子问题以逻辑信息交互的分解思想。
- 不支撑：本题未实现完整推断对偶或精确收敛框架，不继承其最优性保证。
- 核对范围：Official book/standard or author manuscript record。
- 原始记录：[Logic-Based Benders Decomposition: Theory and Applications](https://link.springer.com/book/10.1007/978-3-031-45039-6)。
- 正文位置：2.3 空中中继与逻辑反馈。

## 7. UAV relay communication / aerial relay

[7] Yong Zeng, Rui Zhang, Teng Joon Lim. Wireless Communications with Unmanned Aerial Vehicles: Opportunities and Challenges. IEEE Communications Magazine, 54(5):36–42, 2016. [10.1109/MCOM.2016.7470933](https://doi.org/10.1109/MCOM.2016.7470933).

- 支撑：空中通信的三维位置、视距与能量约束耦合。
- 不支撑：不是本题衰减系数、站点、时刻或通信验证的来源。
- 核对范围：Official book/standard or author manuscript record。
- 原始记录：[Wireless Communications with Unmanned Aerial Vehicles: Opportunities and Challenges](https://arxiv.org/abs/1602.03602)。
- 正文位置：2.3 空中中继与逻辑反馈。

## 8. free-space path loss and LOS/terrain communication

[8] ITU-R. Calculation of free-space attenuation. Recommendation ITU-R P.525-5 (11/2024), 2024. [官方出版来源](https://www.itu.int/rec/R-REC-P.525-5-202411-I/en).

- 支撑：自由空间损耗的频率—距离对数关系。
- 不支撑：不支持用自由空间模型替代题设地形遮挡罚损；后者取官方附件。
- 核对范围：Official book/standard or author manuscript record。
- 原始记录：[Calculation of free-space attenuation](https://www.itu.int/rec/R-REC-P.525-5-202411-I/en)。
- 正文位置：4.4 通信预算与两跳保障。

## 9. multiobjective optimization / epsilon-constraint

[9] George Mavrotas. Effective implementation of the ε-constraint method in Multi-Objective Mathematical Programming problems. Applied Mathematics and Computation, 213(2):455–465, 2009. [10.1016/j.amc.2009.03.037](https://doi.org/10.1016/j.amc.2009.03.037).

- 支撑：将其他目标转为预算约束的多目标分析思路。
- 不支撑：本文未实现完整AUGMECON，也不继承完整Pareto保证。
- 核对范围：Publisher metadata and abstract。
- 原始记录：[Effective implementation of the ε-constraint method in Multi-Objective Mathematical Programming problems](https://www.sciencedirect.com/science/article/pii/S0096300309002574)。
- 正文位置：2.4 多目标折中与固定任务资源配置；8.1 用时间预算解释资源代价。

## 10. task partition / resource allocation

[10] Jon Kleinberg, Éva Tardos. Algorithm Design. Pearson/Addison-Wesley, 1st ed., Chapter 4; ISBN 9780321295354, 2006. [官方出版来源](https://www.pearson.com/en-us/subject-catalog/p/Kleinberg-Algorithm-Design/P200000003259).

- 支撑：固定区间资源需求等于最大重叠深度及贪心着色的区间划分原理。
- 不支撑：不证明本题分组结构的全局普适最优，只支撑固定时窗资源计数。
- 核对范围：Official book/standard or author manuscript record。
- 原始记录：[Algorithm Design](https://www.pearson.com/en-us/subject-catalog/p/Kleinberg-Algorithm-Design/P200000003259)。
- 正文位置：2.4 多目标折中与固定任务资源配置；9.2 各组独立资源需求与均衡指标。

## 11. 官方题面与附件

[11] 《山区洪涝灾害下无人机运输与通信协同优化》及配套数据与结果提交模板[Z]. 赛题提供资料。

支撑服务区、货箱、设备库存、时间与物理参数；不支撑本文算法最优性或实际部署。使用位置：第1、3、4节。本地官方文件按继承白名单保存，未推测文件未载明的出版年份或机构。
