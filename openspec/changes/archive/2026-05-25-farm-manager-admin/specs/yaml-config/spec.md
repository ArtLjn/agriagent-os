## ADDED Requirements

### Requirement: config.yaml 配置文件
系统 SHALL 使用 config.yaml 作为主配置文件，替代 .env。配置文件 SHALL 位于 backend/ 目录下，包含 server、database、ai、weather 四个顶层分组。系统 SHALL 同时保留环境变量覆盖能力（环境变量优先级高于 YAML 文件）。

#### Scenario: 从 config.yaml 读取配置
- **WHEN** 后端启动且 backend/config.yaml 文件存在
- **THEN** Pydantic Settings 从 YAML 文件解析配置值，各字段类型正确

#### Scenario: 环境变量覆盖 YAML
- **WHEN** 同时存在 config.yaml 和环境变量 AI_API_KEY
- **THEN** Settings 中 ai.api_key 的值为环境变量的值（环境变量优先）

#### Scenario: config.yaml 不存在时降级
- **WHEN** backend/config.yaml 文件不存在
- **THEN** 使用 Settings 中定义的默认值，不报错

### Requirement: config.yaml 模板文件
系统 SHALL 提供 config.yaml.example 模板文件，包含所有配置项和默认值（敏感值留空），供开发者复制使用。

#### Scenario: 新开发者初始化配置
- **WHEN** 新开发者克隆项目
- **THEN** 可通过 `cp config.yaml.example config.yaml` 快速创建配置文件，模板中包含注释说明每个配置项的用途

### Requirement: 后端依赖新增 pyyaml
系统 SHALL 在 requirements.txt 中新增 pyyaml 依赖，用于 Pydantic Settings 的 YAML source 解析。

#### Scenario: 安装依赖
- **WHEN** 执行 pip install -r requirements.txt
- **THEN** pyyaml 被正确安装，Settings 可正常读取 YAML 配置
