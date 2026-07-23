# 外部 RAG 线上只读冒烟验证

## 目标

为 Farm Manager 增加一个 opt-in 的线上冒烟测试，用已部署 QuillRAG 服务验证 `/health` 和 `/retrieve` 基础连通性，避免只在 fake client 下通过。

本验证只读，不调用 `/ingest`，不创建知识库，不写入真实密钥。

## 运行方式

默认无私密环境变量时测试会 skip，不会失败。需要真实冒烟时，在本地 shell 临时注入环境变量：

```bash
export RAG_SERVICE__URL="https://your-quillrag.example"
export RAG_SERVICE__API_KEY="从私密凭据来源读取"
export RAG_SERVICE__DEFAULT_COLLECTION="agri_knowledge"
export RAG_SERVICE__DEFAULT_MODE="hybrid"
export RAG_SERVICE__TOP_K="3"
export RAG_SERVICE__TIMEOUT_SECONDS="5"

cd /Users/ljn/Documents/demo/explore/backend
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider tests/context/test_rag_online_smoke.py -q
```

`RAG_SERVICE__URL` 和 `RAG_SERVICE__API_KEY` 必填；collection、mode、top_k 和 timeout 可按部署情况覆盖。真实值只能来自环境变量或私密配置来源，不能写入代码、测试、文档、commit 或 PR 描述。

## 验证边界

- 缺少 `RAG_SERVICE__URL` 或 `RAG_SERVICE__API_KEY`：skip。
- `/health` 或 `/retrieve` 返回 401/403：fail，按认证失败处理。
- 服务返回 5xx：fail，按 QuillRAG 或依赖组件异常处理。
- 网络不可达或超时：fail，说明 URL、网络或超时时间需要排查。
- `/retrieve` 返回空结果：fail。本冒烟使用 harmless query `番茄苗期管理`，目标 collection 应至少能返回一条结果，才能证明线上检索链路可用。

测试失败信息会避免输出 API key；如需要查看服务端细节，请在受控终端或服务日志中排查，不要把密钥复制到 issue、commit 或 PR。

## 排查步骤

1. 检查 `RAG_SERVICE__URL` 是否指向 QuillRAG 服务根地址，不要带 `/retrieve`。
2. 检查 `RAG_SERVICE__API_KEY` 是否和目标服务的 `AUTH_API_KEY` 匹配。
3. 检查 `RAG_SERVICE__DEFAULT_COLLECTION` 是否存在并已有可检索内容。
4. 检查 `RAG_SERVICE__DEFAULT_MODE` 是否为 `vector`、`bm25` 或 `hybrid`。
5. 检查本机到服务、服务到 Qdrant、服务到 embedding provider 的网络连通性。
6. 临时增大 `RAG_SERVICE__TIMEOUT_SECONDS`，确认不是冷启动或外部 embedding provider 延迟导致超时。
