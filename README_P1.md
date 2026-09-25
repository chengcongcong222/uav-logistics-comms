# P1 阶段启动包

先阅读 `results/p1_setup/P1_TASK.md`。它是下一轮执行任务单，不是已完成的性能报告。

`results/p1_setup/REFERENCES.md` 是本轮核查的资料及使用边界；`protocol_design.json` 记录拟采用的比较设计及正式实验前必须解决的项目。

## 复现已执行的工具自检

在本目录或合入文件后的仓库根目录运行：

```bash
python -m src.bench_p1.preferences --out results/p1_setup/preferences.json
python -m unittest discover -s validation/p1_setup -p 'test_*.py' -v
```

没有第三方依赖。当前容器的20项测试通过，仅验证偏好生成、归一化、有限向量关系和边界例子；没有运行原题求解或通信仿真。

下一轮执行代码和独立验证仍需项目本地的完整原始数据、G2输入与既有运行环境。不要把此包独立运行成功解释成无人机系统已经复现。

## 仓库写入状态

GitHub读取成功；本次创建树的写入请求返回403（Resource not accessible by integration），未创建分支、未推送文件、未改动main。此压缩包是本轮的实际交付。解压至已核对的仓库根目录，只新增包内路径；如有同名本地文件，先比较再合入，不直接覆盖。然后把 `results/p1_setup/P1_EXECUTION_PROMPT.md` 交给代码执行端。
