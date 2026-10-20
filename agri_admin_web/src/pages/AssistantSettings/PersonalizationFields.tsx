import {
  Card,
  Col,
  Form,
  Input,
  Radio,
  Row,
  Segmented,
  Select,
  Space,
  Switch,
  Tag,
} from "antd";
import { cardStyle, palette } from "../../styles/theme";
import type {
  FieldSource,
  PersonalizationSettings,
} from "../../api/personalization";
import {
  DETAIL_LEVEL_OPTIONS,
  DISPLAY_FORMAT_OPTIONS,
  EXECUTION_DETAIL_OPTIONS,
  REPLY_STYLE_OPTIONS,
} from "./options";

const mutedCaptionStyle = { color: palette.textMuted, fontSize: 12 };

function fieldLabel(label: string, source?: FieldSource) {
  if (source !== "explicit" && source !== "inferred") {
    return label;
  }
  return (
    <Space size={6}>
      <span>{label}</span>
      <Tag
        color={source === "inferred" ? "purple" : "blue"}
        style={{ marginInlineEnd: 0 }}
      >
        {source === "inferred" ? "自动推断" : "已自定义"}
      </Tag>
    </Space>
  );
}

interface PersonalizationFieldsProps {
  sources: PersonalizationSettings["field_sources"];
}

export default function PersonalizationFields({ sources }: PersonalizationFieldsProps) {
  return (
    <Row gutter={[20, 20]}>
      <Col xs={24} xl={16}>
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          <Card title="称呼与身份" style={cardStyle}>
            <Row gutter={16}>
              <Col xs={24} md={12}>
                <Form.Item
                  name="nickname"
                  label={fieldLabel("用户称呼", sources?.nickname)}
                  extra="助手在对话中如何称呼你，留空则使用默认称呼。"
                >
                  <Input placeholder="例如：李师傅" maxLength={20} allowClear />
                </Form.Item>
              </Col>
              <Col xs={24} md={12}>
                <Form.Item
                  name="assistant_name"
                  label={fieldLabel("助手名称", sources?.assistant_name)}
                  extra="助手在界面和回答中使用的名字。"
                >
                  <Input placeholder="田掌柜" maxLength={20} allowClear />
                </Form.Item>
              </Col>
            </Row>
          </Card>

          <Card title="回复方式" style={cardStyle}>
            <Form.Item
              name="reply_style"
              label={fieldLabel("回复风格", sources?.reply_style)}
            >
              <Select
                options={REPLY_STYLE_OPTIONS.map((option) => ({
                  value: option.value,
                  label: `${option.label} · ${option.description}`,
                }))}
              />
            </Form.Item>
            <Row gutter={24}>
              <Col xs={24} md={12}>
                <Form.Item
                  name="detail_level"
                  label={fieldLabel("回答详细程度", sources?.detail_level)}
                >
                  <Segmented
                    block
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
                  label={fieldLabel("默认展示方式", sources?.display_format)}
                >
                  <Segmented
                    block
                    options={DISPLAY_FORMAT_OPTIONS.map((option) => ({
                      value: option.value,
                      label: option.label,
                    }))}
                  />
                </Form.Item>
              </Col>
            </Row>
            <div style={mutedCaptionStyle}>
              风格与详细程度相互独立，可以同时选择“专业严谨”和“简洁”。
            </div>
          </Card>

          <Card title="自定义指令" style={cardStyle}>
            <Form.Item
              name="custom_instructions"
              extra="只影响助手的表达方式，不会改变业务权限、数据范围或确认流程。"
            >
              <Input.TextArea
                rows={4}
                maxLength={500}
                showCount
                placeholder="例如：回答成本问题时先给结论，再列出明细。"
              />
            </Form.Item>
          </Card>
        </Space>
      </Col>

      <Col xs={24} xl={8}>
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          <Card title="界面与执行过程" style={cardStyle}>
            <Form.Item
              name="loading_greeting_enabled"
              label="加载欢迎语"
              valuePropName="checked"
              extra="对话加载时显示简短问候。"
            >
              <Switch />
            </Form.Item>
            <Form.Item
              name="execution_detail_level"
              label="执行过程展示"
              extra="只影响前端展示，不控制实际权限。"
            >
              <Radio.Group
                optionType="button"
                buttonStyle="solid"
                options={EXECUTION_DETAIL_OPTIONS.map((option) => ({
                  value: option.value,
                  label: option.label,
                }))}
              />
            </Form.Item>
          </Card>

          <Card title="生效说明" style={cardStyle}>
            <Space direction="vertical" size={8} style={mutedCaptionStyle}>
              <span>保存后从下一轮对话开始生效，同一轮内保持稳定。</span>
              <span>临时对话不读取这些设置，也不会产生长期记忆。</span>
              <span>临时改变回答方式时，直接说“这次详细一点”，不会修改长期设置。</span>
            </Space>
          </Card>
        </Space>
      </Col>
    </Row>
  );
}
