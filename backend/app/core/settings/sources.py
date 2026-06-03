from pathlib import Path

import yaml
from pydantic_settings import PydanticBaseSettingsSource


class YamlSettingsSource(PydanticBaseSettingsSource):
    """自定义 YAML 配置源，优先级低于环境变量。"""

    def __init__(self, settings_cls: type, yaml_data: dict):
        super().__init__(settings_cls)
        self._yaml_data = yaml_data

    def get_field_value(self, field, field_name: str):
        return self._yaml_data.get(field_name), field_name, False

    def __call__(self) -> dict:
        result = {}
        for field_name in self.settings_cls.model_fields:
            val, _, _ = self.get_field_value(None, field_name)
            if val is not None:
                result[field_name] = val
        return result


def load_yaml(path: str | Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f) or {}
