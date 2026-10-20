import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  App,
  Button,
  Form,
  Space,
  Spin,
  Typography,
} from "antd";
import dayjs from "dayjs";
import { SaveOutlined, UndoOutlined } from "@ant-design/icons";
import { palette } from "../../styles/theme";
import {
  isPersonalizationDemo,
  personalizationApi,
  personalizationErrorMessage,
  type PersonalizationSettings,
} from "../../api/personalization";
import PersonalizationFields from "./PersonalizationFields";

type PersonalizationFormValues = Pick<
  PersonalizationSettings,
  | "nickname"
  | "assistant_name"
  | "reply_style"
  | "detail_level"
  | "display_format"
  | "custom_instructions"
  | "loading_greeting_enabled"
  | "execution_detail_level"
>;

function toFormValues(settings: PersonalizationSettings): PersonalizationFormValues {
  return {
    nickname: settings.nickname,
    assistant_name: settings.assistant_name,
    reply_style: settings.reply_style,
    detail_level: settings.detail_level,
    display_format: settings.display_format,
    custom_instructions: settings.custom_instructions,
    loading_greeting_enabled: settings.loading_greeting_enabled,
    execution_detail_level: settings.execution_detail_level,
  };
}

const mutedCaptionStyle = { color: palette.textMuted, fontSize: 12 };

export default function PersonalizationPanel() {
  const { message } = App.useApp();
  const [form] = Form.useForm<PersonalizationFormValues>();
  const [settings, setSettings] = useState<PersonalizationSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [demo, setDemo] = useState(false);

  const loadSettings = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const data = await personalizationApi.getSettings();
      setSettings(data);
      form.setFieldsValue(toFormValues(data));
      setDirty(false);
      setDemo(isPersonalizationDemo());
    } catch (error) {
      setLoadError(personalizationErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }, [form]);

  useEffect(() => {
    void loadSettings();
  }, [loadSettings]);

  const handleSave = async () => {
    if (!settings) return;
    let values: PersonalizationFormValues;
    try {
      values = await form.validateFields();
    } catch {
      return;
    }
    setSaving(true);
    setSaveError(null);
    try {
      const updated = await personalizationApi.updateSettings({
        expected_revision: settings.revision,
        ...values,
      });
      setSettings(updated);
      form.setFieldsValue(toFormValues(updated));
      setDirty(false);
      setLoadError(null);
      setDemo(isPersonalizationDemo());
      message.success("设置已保存，下一轮对话生效");
    } catch (error) {
      setSaveError(personalizationErrorMessage(error));
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    if (!settings) return;
    form.setFieldsValue(toFormValues(settings));
    setDirty(false);
    setSaveError(null);
  };

  if (loading && !settings) {
    return (
      <div style={{ textAlign: "center", padding: 64 }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!settings) {
    return (
      <Alert
        type="error"
        showIcon
        message="个性化设置加载失败"
        description={loadError || "请稍后重试"}
        action={<Button size="small" onClick={() => void loadSettings()}>重新加载</Button>}
      />
    );
  }

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      {demo && (
        <Alert
          type="warning"
          showIcon
          message="演示数据"
          description="后端个性化接口尚未接入，当前展示本地演示数据；修改只在本次页面会话中生效，刷新后恢复。"
        />
      )}
      {saveError && (
        <Alert
          type="error"
          showIcon
          message="保存失败，编辑内容已保留"
          description={saveError}
          action={
            <Button size="small" onClick={() => void loadSettings()}>
              重新加载
            </Button>
          }
        />
      )}
      {loadError && (
        <Alert
          type="error"
          showIcon
          message="重新加载失败"
          description={loadError}
          action={
            <Button size="small" onClick={() => void loadSettings()}>
              重试
            </Button>
          }
        />
      )}

      <Form<PersonalizationFormValues>
        form={form}
        layout="vertical"
        onValuesChange={() => setDirty(true)}
      >
        <PersonalizationFields sources={settings.field_sources} />

        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "flex-end",
            gap: 12,
            padding: "16px 0 4px",
          }}
        >
          <Typography.Text style={mutedCaptionStyle}>
            版本 {settings.revision} · 最近更新{" "}
            {dayjs(settings.updated_at).format("YYYY-MM-DD HH:mm")}
          </Typography.Text>
          <Button
            icon={<UndoOutlined />}
            disabled={!dirty || saving}
            onClick={handleReset}
          >
            撤销更改
          </Button>
          <Button
            type="primary"
            icon={<SaveOutlined />}
            loading={saving}
            disabled={!dirty}
            onClick={() => void handleSave()}
          >
            保存设置
          </Button>
        </div>
      </Form>
    </Space>
  );
}
