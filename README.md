# 拾证 V0 干净版

本地抽取股票期权公告候选。不写 `D:\StockOptionResearch`。候选不是 Truth。

## 用法

1. 解压到 `D:\grok-pdf-处理`
2. 把要抽的 PDF 放进 `input\pdf`
3. 双击 `install_deps.bat`（首次）
4. 双击 `run_harvest.bat`
5. 双击 `open_review.bat`

结果：

- `review\html\index.html` 总览
- `review\html\C01.html` … 各案
- `candidates\csv\ALL_CANDIDATES.csv`
- `candidates\json\`

批处理文件是英文，避免 Windows 编码把中文 bat 拆坏。不要用 `python -c`。

## 输入

只读取 `input\pdf\*.pdf`。请自行从治理仓只读拷贝，不要用东财/新浪当权威源。
