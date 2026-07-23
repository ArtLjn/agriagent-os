# 农业知识来源索引

本目录保存农业知识库的来源索引，不保存网页全文、PDF、图片或网页快照。

当前服务基准：

```text
地区：江苏省徐州市睢宁县，优先魏集镇等设施西瓜主产区
作物：西瓜
场景：春季、春提早、设施栽培
```

文件说明：

- `xuzhou-suining-watermelon-sources.jsonl`：主索引，每行一个来源。
- `xuzhou-suining-watermelon-sources.md`：人工审查版。
- `../agri-curated/xuzhou/suining/watermelon/`：整理后的 Markdown 知识卡，后续可进入 QuillRAG。

入库原则：

- 睢宁/徐州本地且有具体农时、设施、风险、肥水或案例事实的资料，才进入核心知识卡。
- 江苏、淮北平原、上海等相近设施栽培资料只能作为 fallback。
- 全国论文、外省资料、无法打开正文、泛泛新闻、营销软文默认只做 source index 或拒绝。
- 农时日期、温度阈值、肥水参数优先进入结构化表；知识卡保留来源依据和解释。
