## MODIFIED Requirements

### Requirement: Prompt 模板单一数据源
系统 SHALL 仅从 `prompts/` 目录的 `.j2` 文件加载 prompt 模板，不在代码中硬编码 prompt 副本。模板加载失败时 SHALL 抛出 KeyError 而非返回过时的硬编码内容。新增 `PromptComposer` SHALL 从 `snippets/` 子目录加载可复用片段，按 `config.yaml` 中 `compositions` 配置组合渲染。

#### Scenario: 模板文件正常加载
- **WHEN** 应用启动，`prompts/config.yaml`、`prompts/*.j2` 和 `prompts/snippets/*.j2` 文件存在
- **THEN** `PromptRegistry` 从文件加载所有模板，`PromptComposer` 加载所有 snippet 和组合配置

#### Scenario: 模板未注册时抛异常
- **WHEN** 调用 `PromptComposer.compose("nonexistent")` 或 `render_prompt("nonexistent")`
- **THEN** 抛出 KeyError，日志记录模板/场景未注册

#### Scenario: 无硬编码 fallback
- **WHEN** 检查 `prompt_registry.py` 和 `prompt_composer.py` 源码
- **THEN** 不存在 `_DEFAULT_PROMPTS` 字典、`get_fallback()` 方法或硬编码的 snippet 内容
