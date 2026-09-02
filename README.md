# 拾证

本地抽取股票期权公告候选。不写 D:\StockOptionResearch。候选不是 Truth。

## 用法

1. 解压到 `D:\grok-pdf-处理`
2. 把 PDF 放进 `input\pdf`（哈希文件名也可以）
3. 双击 `run.bat`

会自动装依赖、抽取、从正文识别证券代码/简称、打开 `review\html\index.html`。

只有这一个入口。不要再跑其它 bat / py。
