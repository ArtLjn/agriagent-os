import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  App,
  Button,
  Col,
  Form,
  Input,
  Row,
  Segmented,
  Space,
  Spin,
  Switch,
} from "antd";
import dayjs from "dayjs";
import {
  AppstoreOutlined,
  EditOutlined,
  SaveOutlined,
  SoundOutlined,
  UserOutlined,
} from "@ant-design/icons";
import {
  isPersonalizationDemo,
  personalizationApi,
  personalizationErrorMessage,
  type PersonalizationSettings,
} from "../../api/personalization";
import DemoNotice from "./DemoNotice";
import PreviewCard from "./PreviewCard";
import ProfileCard from "./ProfileCard";
import SettingsSection from "./SettingsSection";
import StyleChoiceGrid from "./StyleChoiceGrid";
import {
  DETAIL_LEVEL_OPTIONS,
  DISPLAY_FORMAT_OPTIONS,
  EXECUTION_DETAIL_OPTIONS,
} from "./options";
import { toFormValues, type PersonalizationFormValues } from "./types";

const INSTRUCTION_SNIPPETS = [
  "先给结论",
  "少用专业术语",
  "对比信息用表格",
  "需要确认时先提醒我",
];

export default function PersonalizationPanel() {
  const { message } = App.useApp();
  const [form] = Form.useForm<PersonalizationFormValues>();
  const [settings, setSettings] = useState<PersonalizationSettings | null>(null);
  const [preview, setPreview] = useState<PersonalizationFormValues | null>(null);
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
      const values = toFormValues(data);
      setSettings(data);
      setPreview(values);
      form.setFieldsValue(values);
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

  const handleValuesChange = (
    _changed: Partial<PersonalizationFormValues>,
    allValues: PersonalizationFormValues,
  ) => {
    setDirty(true);
    setPreview(allValues);
  };

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
      const nextValues = toFormValues(updated);
      setSettings(updated);
      setPreview(nextValues);
      form.setFieldsValue(nextValues);
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
    const values = toFormValues(settings);
    form.setFieldsValue(values);
    setPreview(values);
    setDirty(false);
    setSaveError(null);
  };

  const appendInstruction = (snippet: string) => {
    if (!settings) return;
    const current =
      (form.getFieldValue("custom_instructions") as string | undefined) ?? "";
    if (current.includes(snippet)) return;
    const next = (
      current.trim()
        ? `${current.trim().replace(/[；;]\s*$/, "")}；${snippet}`
        : snippet
    ).slice(0, 500);
    form.setFieldValue("custom_instructions", next);
    setPreview({ ...(preview ?? toFormValues(settings)), custom_instructions: next });
    setDirty(true);
  };

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      {demo && (
        <DemoNotice description="后端个性化接口尚未接入，修改只在本次页面会话中生效。" />
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
      {loadError && settings && (
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
        onValuesChange={handleValuesChange}
      >
        {!settings ? (
          loading ? (
            <div style={{ textAlign: "center", padding: 64 }}>
              <Spin size="large" />
            </div>
          ) : (
            <Alert
              type="error"
              showIcon
              message="个性化设置加载失败"
              description={loadError || "请稍后重试"}
              action={
                <Button size="small" onClick={() => void loadSettings()}>
                  重新加载
                </Button>
              }
            />
          )
        ) : (
          <>
            <Row gutter={[24, 24]}>
              <Col xs={24} xl={15}>
                <div className="settings-stack">
                  <ProfileCard
                    nickname={preview?.nickname ?? settings.nickname}
                    assistantName={preview?.assistant_name ?? settings.assistant_name}
                    revision={settings.revision}
                  />

                  <SettingsSection
                    icon={<UserOutlined />}
                    title="称呼与身份"
                    description="助手如何称呼你，以及它在界面中使用的名字。"
                  >
                    <div className="settings-field-grid">
                      <Form.Item
                        name="nickname"
                        label="用户称呼"
                        extra="留空时使用默认称呼“农友”。"
                      >
                        <Input placeholder="例如：李师傅" maxLength={20} allowClear />
                      </Form.Item>
                      <Form.Item
                        name="assistant_name"
                        label="助手名称"
                        extra="会显示在对话和界面标题中。"
                      >
                        <Input placeholder="田掌柜" maxLength={20} allowClear />
                      </Form.Item>
                    </div>
                  </SettingsSection>

                  <SettingsSection
                    icon={<SoundOutlined />}
                    title="表达方式"
                    description="风格和详细程度相互独立，可以同时选择“专业严谨”和“简洁”。"
                  >
                    <div className="settings-field">
                      <div className="settings-field__label">回复风格</div>
                      <Form.Item name="reply_style" noStyle>
                        <StyleChoiceGrid />
                      </Form.Item>
                    </div>

                    <Row gutter={16} style={{ marginTop: 18 }}>
                      <Col xs={24} md={12}>
                        <Form.Item
                          name="detail_level"
                          label="回答详细程度"
                          style={{ marginBottom: 0 }}
                        >
                          <Segmented
                            block
                            className="settings-segmented"
                            options={DETAIL_LEVEL_OPTIONS.map((option) => ({
                              value: option.value,
                              label: option.label,
                            }))}
                          />
                        </Form.Item>
                      </Col>
                      <Col xs={24} md={12}>
                        <Form.Item
                          name="display_format"
                          label="默认展示方式"
                          style={{ marginBottom: 0 }}
                        >
                          <Segmented
                            block
                            className="settings-segmented"
                            options={DISPLAY_FORMAT_OPTIONS.map((option) => ({
                              value: option.value,
                              label: option.label,
                            }))}
                          />
                        </Form.Item>
                      </Col>
                    </Row>
                  </SettingsSection>

                  <SettingsSection
                    icon={<EditOutlined />}
                    title="自定义指令"
                    description="只影响表达方式，不会改变业务权限、数据范围或确认流程。"
                  >
                    <Form.Item
                      name="custom_instructions"
                      extra="最多 500 字，保存后从下一轮对话生效。"
                    >
                      <Input.TextArea
                        rows={4}
                        maxLength={500}
                        showCount
                        placeholder="例如：回答成本问题时先给结论，再列出明细。"
                      />
                    </Form.Item>
                    <div className="prompt-chips">
                      {INSTRUCTION_SNIPPETS.map((snippet) => (
                        <button
                          key={snippet}
                          type="button"
                          className="prompt-chip"
                          onClick={() => appendInstruction(snippet)}
                        >
                          + {snippet}
                        </button>
                      ))}
                    </div>
                  </SettingsSection>

                  <SettingsSection
                    icon={<AppstoreOutlined />}
                    title="界面与执行过程"
                    description="控制对话界面的展示方式，不影响实际权限。"
                  >
                    <div className="settings-toggle-row">
                      <div>
                        <div className="settings-toggle-row__title">加载欢迎语</div>
                        <div className="settings-toggle-row__desc">
                          对话加载时显示简短问候。
                        </div>
                      </div>
                      <Form.Item
                        name="loading_greeting_enabled"
                        valuePropName="checked"
                        noStyle
                      >
                        <Switch aria-label="加载欢迎语" />
                      </Form.Item>
                    </div>

                    <div className="settings-toggle-row">
                      <div>
                        <div className="settings-toggle-row__title">执行过程展示</div>
                        <div className="settings-toggle-row__desc">
                          精简只展示关键步骤，详细会展开完整过程。
                        </div>
                      </div>
                      <Form.Item name="execution_detail_level" noStyle>
                        <Segmented
                          className="settings-segmented"
                          options={EXECUTION_DETAIL_OPTIONS.map((option) => ({
                            value: option.value,
                            label: option.label,
                          }))}
                        />
                      </Form.Item>
                    </div>
                  </SettingsSection>
                </div>
              </Col>

              <Col xs={24} xl={9}>
                <div className="preview-sticky">
                  <PreviewCard values={preview ?? toFormValues(settings)} />
                  <div className="settings-tip-card">
                    <strong>设置从下一轮对话生效。</strong>{" "}
                    临时说“这次详细一点”只影响当前回答，不会改变长期设置。
                  </div>
                </div>
              </Col>
            </Row>

            {dirty ? (
              <div className="save-dock">
                <div className="save-dock__text">
                  <span className="save-dock__dot" />
                  有未保存的更改
                </div>
                <Space>
                  <Button onClick={handleReset} disabled={saving}>
                    撤销
                  </Button>
                  <Button
                    type="primary"
                    icon={<SaveOutlined />}
                    loading={saving}
                    onClick={() => void handleSave()}
                  >
                    保存设置
                  </Button>
                </Space>
              </div>
            ) : (
              <div className="settings-saved-footer">
                版本 {settings.revision} · 最近更新{" "}
                {dayjs(settings.updated_at).format("YYYY-MM-DD HH:mm")} · 已保存
              </div>
            )}
          </>
        )}
      </Form>
    </Space>
  );
}
