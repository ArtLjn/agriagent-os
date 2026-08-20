"""Agent Harness 领域包。

子模块按领域显式导入，避免在包初始化阶段加载 LLM、存储和 Runtime，
从而保持 Context 与平台适配器之间的单向依赖。
"""
