# 研究审计与求解方法重构

## 一、应撤回或修正的判断

“通过独立验证”“细化到0.25秒”“生成更多Pareto点”“相对较差基线改善86.6%”不能代替优化质量比较。前期过早固定Q2 P01的箱组、访问次序与机型，然后主要优化时序和中继，使Q3探索被限制在固定运输结构。现有方法改进不应继续以新增鲁棒场景或仿真层数为中心。

本轮独立Q2试验已经给出具体反例，而不再只是对网友数字的猜测。现有Q2三点确实可以被同冻结物理口径下自行生成的方案支配。不能据此推导现有Q3必然被同一方案支配：新Q2见证尚无通信排程。

## 二、源码诊断

基准提交 `badc8a4282f9935018c837e52b32b86539c96071`。

1. `src/q2/operators.py::_insert_box` 最终返回 `cands[:12]`。候选按已有任务顺序生成，尾部任务和新建任务可能根本不参与评价。四个隔离用例之一：14个已有架次时，12个返回选项只涉及前6个架次，没有新建架次。
2. 同一函数的新建任务探测只覆盖A/B，未覆盖C。其他局部机型变更算子存在，不能说整个程序从未使用C；问题是新架次修复邻域不完整且有稳定偏向。
3. `_insert_many` 继续按 `J_time`、makespan、energy、sorties排序；`J_time` 实为 `J_norm` 兼容别名，与E3.2改用的 `J_late` 主目标和不同ε子问题不一致。存在零迟到候选被正迟到候选压过的最小反例。
4. `evaluator_sol.py` 每次评价都重新按固定紧迫性排序，再调用贪心decoder。因此“任务优先顺序”并没有作为一个真正可自由优化的变量保留。固定序下decoder失败不是所有可能调度均不可行的证明。
5. `alns.py` 累计算子分数，但选择仍用均匀 `rng.choice`，分数没有驱动选择概率。这不是已实现的自适应选择。
6. `_remove_boxes` 用 `list(by.keys())` 重建服务顺序，可以改变仍保留站点的既有访问顺序。

这些行为证明存在严重漏搜风险，但未对每一个缺陷分别做完整因果消融；不能把本轮全部收益精确归因到某一行代码。

源文件链接：
- https://github.com/chengcongcong222/uav-logistics-comms/blob/badc8a4282f9935018c837e52b32b86539c96071/src/q2/operators.py
- https://github.com/chengcongcong222/uav-logistics-comms/blob/badc8a4282f9935018c837e52b32b86539c96071/src/q2/alns.py
- https://github.com/chengcongcong222/uav-logistics-comms/blob/badc8a4282f9935018c837e52b32b86539c96071/src/q2/evaluator_sol.py
- https://github.com/chengcongcong222/uav-logistics-comms/blob/badc8a4282f9935018c837e52b32b86539c96071/src/q2/e32_reaudit.py
- https://github.com/chengcongcong222/uav-logistics-comms/blob/badc8a4282f9935018c837e52b32b86539c96071/docs/model/Q3_JOINT_E7_SEMANTICS.md

## 三、筛选文献：来源支持什么，不支持什么

以下不是声称全部逐页精读。核查层级分别注明；对于只取得官方摘要或作者摘要者，不据此宣称复现其算法。文献中的性能、近似比、最优性保证不能直接移植到本题。

### 1. Dorling et al., Vehicle Routing Problems for Drone Delivery
IEEE Transactions on Systems, Man, and Cybernetics: Systems, 2017, 47(1):70–85. DOI:10.1109/TSMC.2016.2582745。
作者稿：https://arxiv.org/abs/1608.02305
本轮核查：作者摘要与出版信息。
支持：无人机复用、多架次、载荷/电池相关能耗；分别以时限和成本预算研究权衡。
迁移：正确表示一架无人机可重复出动，成本预算和完工预算是不同子问题。
不能照搬：该文近似能耗不能替换赛题冻结的能耗公式；没有本题两中继及独立组件的全部约束。

### 2. Cheng, Adulyasak & Rousseau, Drone routing with energy function: Formulation and exact algorithm
Transportation Research Part B, 2020, 139:364–387. DOI:10.1016/j.trb.2020.06.011。
出版商：https://www.sciencedirect.com/science/article/pii/S019126152030360X
作者实例：https://sites.google.com/site/chun123cheng/instances
本轮核查：出版商检索摘要及作者实例入口；出版商全文访问受限。
支持：非线性载荷能耗、multi-trip、分支割结构。
迁移：对固定箱组/路线精确预计算能耗，不为方便整数模型而静默线性化物理能耗。

### 3. Şahin & Yaman, A Branch and Price Algorithm for the Heterogeneous Fleet Multi-Depot Multi-Trip Vehicle Routing Problem with Time Windows
Transportation Science, 2022, 56(6):1636–1657. DOI:10.1287/trsc.2022.1146。
https://pubsonline.informs.org/doi/10.1287/trsc.2022.1146
本轮核查：出版商摘要与方法概要。
支持：异构机队、多次出动、时间窗与共享设施资源；以工作日变量建模并列生成。
迁移：不要把“路线选好以后随便安排时间”当作联合优化。路线/工作模式与资源调度需要联动。
不能照搬：他们的工作日列并不是本题的完整无人机—电池—中继模式；其规模实验不保证本题规模可直接求完。

### 4. Jagtenberg et al., Columnwise neighborhood search: A novel set partitioning matheuristic and its application to the VeRoLog Solver Challenge 2019
Networks, 2020, 76(2):273–293. DOI:10.1002/net.21961。
https://onlinelibrary.wiley.com/doi/full/10.1002/net.21961
本轮核查：开放正文，重点读集合划分、整数规划邻域与分解说明。
支持：用数学规划精确搜索当前解附近的大邻域，而不是只靠逐个贪心插入。
迁移：本题最直接的改进来源——多个架次一起拆开后，联合重选箱组、机型、时序和资源。
不能照搬：精确邻域最优不等于全问题最优；本文也不是本题同场景。

### 5. Vidal, Hybrid Genetic Search for the CVRP: Open-Source Implementation and SWAP* Neighborhood
Computers & Operations Research, 2022, 140:105643. DOI:10.1016/j.cor.2021.105643。
作者稿：https://arxiv.org/abs/2012.10384
代码：https://github.com/vidalt/HGS-CVRP
本轮核查：作者摘要、方法描述与开源入口。
支持：有效局部交换、实现细节、跨路线重新插入的重要性。
迁移：用成熟邻域设计作为控制算法，而不是自写少量同名算子就认为达到了文献ALNS/HGS水平。
不能照搬：CVRP没有本题共享电池、硬/软期限与中继资源，不可直接替代全部求解器。

### 6. Wouda, Lan & Kool, PyVRP: a high-performance VRP solver package
INFORMS Journal on Computing, 2024. DOI:10.1287/ijoc.2023.0055。
作者稿：https://arxiv.org/abs/2403.13795
开源：https://github.com/PyVRP/PyVRP
本轮核查：作者摘要、发表信息与软件说明。
支持：成熟的VRPTW混合遗传搜索、Python/C++职责分离及可复用实现。
迁移：适合作为邻域实现/路线生成的基准；题目特有资源仍需自建联合调度模型。
本轮未在运行环境中安装或使用PyVRP；新三点来自自行编写的SciPy/HiGHS模型。

### 7. Liang et al., Optimizing the Deployment of Static and Mobile Roadside Units Using a Branch-and-Price Algorithm
IEEE Transactions on Intelligent Transportation Systems, 2024, 25(11):17078–17091. DOI:10.1109/TITS.2024.3407757。
作者机构摘要：https://researchportal.hkust.edu.hk/en/publications/optimizing-the-deployment-of-static-and-mobile-roadside-units-usi/
IEEE：https://ieeexplore.ieee.org/document/10552425/
本轮核查：作者机构的完整摘要及出版元数据。
支持：由车辆轨迹构造时空网络、路线模型、通信设施部署和列生成。
迁移：通信保障可以做成随交通轨迹变化的模式/时空选择问题，不只是静态摆点。
不能照搬：路侧单元部署不含本题中继飞行能量和充电周转。

### 8. Mostajabdaveh, Salman & Gutjahr, A Branch-and-Price Algorithm for Fast and Equitable Last-Mile Relief Aid Distribution
European Journal of Operational Research, 2025, 324(2):522–537. DOI:10.1016/j.ejor.2025.01.032。
作者稿：https://arxiv.org/abs/2512.19882
本轮核查：作者摘要、出版信息。
支持：救灾配送、多目标、ε约束与路线型精确方法的结合。
迁移：系统地求不同预算下的方案，不只筛旧随机样本。
不能照搬：该文公平性/未满足需求目标与本题80箱全部配送不同，不应新增公平目标替换题意。

### 9. Attenni et al., Scheduling UAV-Based Deliveries With an Approximation Algorithm
IEEE Transactions on Vehicular Technology, 2026, 75(6):9144–9156（2025在线）. DOI:10.1109/TVT.2025.3639763。
https://ieeexplore.ieee.org/document/11278089/
作者页面：https://sites.google.com/di.uniroma1.it/vivianaarrigoni/home
本轮核查：IEEE索引摘要及作者出版页面，未逐页复现近似算法。
支持：无人机配送调度可以研究有界性能而不仅仅报启发式数值。
迁移：应增加有效下界、小规模精确对照和证明范围。
不能照搬：该文分布式换电站条件不同，近似保证不能套用本题四资源联合约束。

### 10. Mavrotas & Florios, An improved version of the augmented ε-constraint method (AUGMECON2) for finding the exact Pareto set in multi-objective integer programming problems
Applied Mathematics and Computation, 2013, 219(18):9652–9669. DOI:10.1016/j.amc.2013.03.002。
作者存档：https://mpra.ub.uni-muenchen.de/105034/
公开实现：https://www.gams.com/latest/gamslib_ml/libhtml/gamslib_epscmmip.html
本轮核查：作者存档摘要和公开实现说明。
支持：增强ε约束避免弱非支配解，并在适当整数目标网格/精确求解条件下取得完整整数Pareto集合。
不能照搬：连续开始时刻、有限候选池、有界启发式或仅重放档案不满足自动全局完整性保证。

### 11. Hooker, Logic-based Benders decomposition for large-scale optimization
2019，作者方法章节。
https://arxiv.org/abs/1910.11944
本轮核查：作者摘要及框架说明。
迁移：资源子问题返回经过证明的冲突信息，而不是简单“排不出来”。未完成搜索、候选池不全或强行限定架次导致的失败，不得成为原问题永久不可行割。

## 四、推荐的一条主方法

**候选运输模式池 + 联合资源整数调度 + 冲突驱动的精确大邻域 + 预算扫描 + 主动支配检验。**

先不实现完整Branch-and-Price；候选池与精确邻域核心已有本轮实例见证。候选规模失控且确有收益时，再增加有数学依据的定价/列生成。

### 1. 模式表示

每个运输模式保存箱集合、机型、服务次序、逐航段剩余载荷、精确能量、逐箱交付偏移、准备/飞行/交接时长、返场SOC和充电时间。由于模式已确定，非线性能耗可精确计算为常数；这不是对物理公式做线性近似。

### 2. 主问题联合选模式和开始时刻

对模式p及候选开始时刻τ，用x[p,τ]表示执行次数/选择。按真正等价货箱类别的供需精确覆盖（或直接逐箱exactly-once），同时约束各机型运输机和共享电池的占用。无人机占用准备开始至返场，电池占用起飞至返场后充满；不可永久绑定飞机/电池。

本轮zero-late可行性实验把所有期望时间作为附加硬上界，仅用于证明零迟到可达；正式完整多目标模型仍允许普通物资迟到并计J_late。若不能找到zero-late，不能宣称全局不存在。

### 3. 多点扩展和精确邻域

以单点方案为强基线，加入所有机型的两点顺序、局部三点任务、跨架次箱交换和机型替换。候选按多种目标/紧迫性/资源代价生成，不按文件先后顺序截前12个。

每次挑选数个互相影响的架次，释放箱归属、路线、机型、开始时刻、具体UAV/电池。使用受限MILP/CP-SAT联合修复，而不是逐箱贪心插入后只运行一次固定顺序decoder。必须保留原可行见证，超时返回UNKNOWN或已有可行解，不得通过伪不可行删好结构。

### 4. Q3是联合结构优化，不是固定新Q2后永远只平移

新Q2三方案和旧Q3均作为不同起点。对Q3高迟到/中继冲突邻域，同时释放相关运输模式与中继分组/站点/时序；按影响闭包纳入共享中继与UAV/电池链的关联任务。候选站点继续按冲突扩展，精确验证保留。

通信模板按相对时间缓存。在静态DEM/链路模型和固定完整相对轨迹下，M(t;s)=M_relative(t-s)。改变起飞时刻不应触发整条轨迹重新穿DEM；改变箱组、机型、停靠箱数、次序、地形/算法版本则必须换缓存指纹。搜索加速后将节省的计算用于更多真正不同的运输结构，而非更密的重复审计。

## 五、怎样检验非支配性

已验证档案筛选只证明“已存方案之间不支配”。要挑战一个候选x，在声明的搜索域X_C内求：

max_y  Σ_j [f_j(x)-f_j(y)]/s_j
s.t. y∈X_C, f_j(y)≤f_j(x) 对所有核心目标成立，s_j>0。

这里归一化和只用于寻找支配反例，不是新的最终偏好权重。x自身必须包含在X_C中。找到正改进的可行y即证明x被支配；全局最优目标为0且有对应界证据，才证明该声明域内x非支配。超时且没有改进、仅在档案里枚举、或者只求一个固定邻域，都不能宣称整个题目非支配。

若沿用词典序TimelinessKey，应另行处理J_late严格改善与J_late相等/J_norm改善两个分支。把J_norm独立非增的标量检验未找到改进，不能推出词典序偏好下无支配者。

精确完成的ε子问题还应依次优化剩余核心目标消除弱非支配；有连续时间和不完整模式池时，不承诺完整全局Pareto。求解器的下界/间隙注明对应模式池、网格、预算和目标，不能把不完整路线池的LP值当作原题全局下界。

## 六、创新表述应收缩到可检验贡献

所有物理资源约束、ALNS/MILP/CP-SAT名称、Pareto和更细时间采样本身不应单列为创新。

值得检验的贡献是：
- 用运输与中继依赖闭包定义同步重构邻域，避免改一处、卡另一处。
- 相对通信模板与按需模式扩展，使结构搜索具备可承受的评估成本。
- 预算生成的每个执行方案配独立可行性证据及明确范围的支配挑战结果。

要在相同数据、相同模型、相同计算预算下，与修正后的普通LNS、固定模式池MILP、无通信依赖的精确邻域分别比较。只有检验出贡献，才写为方法改进；不预先宣称首创或优于所有参赛者。
