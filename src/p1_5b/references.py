"""Curated primary-source bibliography, verified 2026-09-26."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'results/p1_5b/references'
def main():
    specs=[
    ('R1','humanitarian/emergency UAV logistics','Boualem Rabta; Christian Wankmüller; Gerald Reiner',2018,'A drone fleet model for last-mile distribution in disaster relief operations','International Journal of Disaster Risk Reduction, 28:107–112','10.1016/j.ijdrr.2018.02.020','https://www.sciencedirect.com/science/article/pii/S2212420918302000','载荷与能源约束下无人机应急末端配送的建模背景','不支持本题具体性能、通信模型或现场部署结论','1; 2.1'),
    ('R2','heterogeneous vehicle/UAV routing','B. Golden; A. Assad; L. Levy; F. Gheysens',1984,'The fleet size and mix vehicle routing problem','Computers & Operations Research, 11(1):49–66','10.1016/0305-0548(84)90007-8','https://www.sciencedirect.com/science/article/pii/0305054884900078','异构机型配置与路线选择需要共同考虑','其车辆成本模型不直接替代本题无人机物理模型','2.1; 6.1'),
    ('R3','battery/resource scheduling and charging','Alejandro Montoya; Christelle Guéret; Jorge E. Mendoza; Juan G. Villegas',2017,'The electric vehicle routing problem with nonlinear charging function','Transportation Research Part B: Methodological, 103:87–110','10.1016/j.trb.2017.02.004','https://www.sciencedirect.com/science/article/pii/S0191261516304556','充电时长与荷电状态的非线性关系应进入可执行排程','不支持本题65%/35%充电系数；具体参数来自官方附件','2.2; 4.3'),
    ('R4','ALNS / large-neighborhood search','Stefan Ropke; David Pisinger',2006,'An Adaptive Large Neighborhood Search Heuristic for the Pickup and Delivery Problem with Time Windows','Transportation Science, 40(4):455–472','10.1287/trsc.1050.0135','https://pubsonline.informs.org/doi/10.1287/trsc.1050.0135','算子按历史表现竞争的自适应邻域方法类别','不支持本方法属于ALNS，也不支持本题性能优于该方法','2.2'),
    ('R5','set partitioning / route-pattern approaches','M. L. Balinski; R. E. Quandt',1964,'On an Integer Program for a Delivery Problem','Operations Research, 12(2):300–304','10.1287/opre.12.2.300','https://pubsonline.informs.org/doi/10.1287/opre.12.2.300','以整数变量表达配送覆盖与组合选择的方法基础','不支持本题有限模式池具有全路径完备性','2.2; 6.1'),
    ('R6','Benders / decomposition logic','John Hooker',2024,'Logic-Based Benders Decomposition: Theory and Applications','Springer, Synthesis Lectures on Operations Research and Applications','10.1007/978-3-031-45039-6','https://link.springer.com/book/10.1007/978-3-031-45039-6','主问题与子问题以逻辑信息交互的分解思想','本题未实现完整推断对偶或精确收敛框架，不继承其最优性保证','2.3; 7.3'),
    ('R7','UAV relay communication / aerial relay','Yong Zeng; Rui Zhang; Teng Joon Lim',2016,'Wireless Communications with Unmanned Aerial Vehicles: Opportunities and Challenges','IEEE Communications Magazine, 54(5):36–42','10.1109/MCOM.2016.7470933','https://arxiv.org/abs/1602.03602','空中通信的三维位置、视距与能量约束耦合','不是本题衰减系数、站点、时刻或通信验证的来源','2.3; 7.1'),
    ('R8','free-space path loss and LOS/terrain communication','ITU-R',2024,'Calculation of free-space attenuation','Recommendation ITU-R P.525-5 (11/2024)',None,'https://www.itu.int/rec/R-REC-P.525-5-202411-I/en','自由空间损耗的频率—距离对数关系','不支持用自由空间模型替代题设地形遮挡罚损；后者取官方附件','4.4; 7.1'),
    ('R9','multiobjective optimization / epsilon-constraint','George Mavrotas',2009,'Effective implementation of the ε-constraint method in Multi-Objective Mathematical Programming problems','Applied Mathematics and Computation, 213(2):455–465','10.1016/j.amc.2009.03.037','https://www.sciencedirect.com/science/article/pii/S0096300309002574','将其他目标转为预算约束的多目标分析思路','本文未实现完整AUGMECON，也不继承完整Pareto保证','2.4; 8.1'),
    ('R10','task partition / resource allocation','Jon Kleinberg; Éva Tardos',2006,'Algorithm Design','Pearson/Addison-Wesley, 1st ed., Chapter 4; ISBN 9780321295354',None,'https://www.pearson.com/en-us/subject-catalog/p/Kleinberg-Algorithm-Design/P200000003259','固定区间资源需求等于最大重叠深度及贪心着色的区间划分原理','不证明本题分组结构的全局普适最优，只支撑固定时窗资源计数','2.4; 9.2')]
    records=[]
    for id,cat,authors,year,title,venue,doi,url,support,limit,sections in specs:
        records.append(dict(id=id,category=cat,authors=authors.split('; '),year=year,title=title,venue=venue,doi=doi,
          official_or_author_source=url,supports=support,does_not_support=limit,body_sections=sections.split('; '),
          checked_date='2026-09-26',verification='Primary publisher/standard/author record and abstract or theorem statement checked; no competition-answer source',
          access_scope='Publisher metadata and abstract' if id not in ['R6','R7','R8','R10'] else 'Official book/standard or author manuscript record',
          additional_primary_sources=['https://www.cs.princeton.edu/~wayne/kleinberg-tardos/pdf/04GreedyAlgorithmsI.pdf'] if id=='R10' else []))
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'bibliography.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
