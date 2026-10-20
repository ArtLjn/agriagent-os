import { useEffect, useState } from "react";
import {
  Alert,
  App,
  Descriptions,
  Form,
  Input,
  Modal,
  Tag,
} from "antd";
import {
  personalizationApi,
  personalizationErrorMessage,
  type MemoryRecord,
} from "../../api/personalization";
import { MEMORY_KIND_META, MEMORY_SCOPE_META, MEMORY_SOURCE_META } from "./options";

interface MemoryEditModalProps {
  record: MemoryRecord | null;
  open: boolean;
  onCancel: () => void;
  onSaved: () => void;
}

interface MemoryEditFormValues {
  text: string;
}

export default function MemoryEditModal({
  record,
  open,
  onCancel,
  onSaved,
}: MemoryEditModalProps) {
  const { message } = App.useApp();
  const [form] = Form.useForm<MemoryEditFormValues>();
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open || !record) return;
    form.resetFields();
    form.setFieldsValue({ text: record.text });
  }, [open, record, form]);

  const handleSave = async () => {
    if (!record) return;
    let values: MemoryEditFormValues;
    try {
      values = await form.validateFields();
    } catch {
      return;
    }
    setSaving(true);
    try {
      await personalizationApi.updateMemory(record.memory_id, {
        expected_revision: record.revision,
        text: values.text.trim(),
      });
      message.success("记忆已更新，来源已标记为手动编辑");
      onSaved();
    } catch (error) {
      message.error(personalizationErrorMessage(error));
    } finally {
      setSaving(false);
    }
  };

  const scopeMeta = record ? MEMORY_SCOPE_META[record.scope] : null;
  const kindMeta = record ? MEMORY_KIND_META[record.kind] : null;
  const sourceMeta = record ? MEMORY_SOURCE_META[record.source_type] : null;

  return (
    <Modal
      title="编辑记忆"
      open={open}
      onCancel={onCancel}
      onOk={() => void handleSave()}
      confirmLoading={saving}
      okText="保存"
      cancelText="取消"
      width={560}
      destroyOnHidden
    >
      {record && (
        <>
          <Descriptions column={2} size="small" style={{ marginBottom: 16 }}>
            <Descriptions.Item label="范围">
              <Tag color={scopeMeta?.color}>{scopeMeta?.label}</Tag>
              {record.farm_name ? ` ${record.farm_name}` : ""}
            </Descriptions.Item>
            <Descriptions.Item label="类型">
              <Tag color={kindMeta?.color}>{kindMeta?.label}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="来源">
              <Tag color={sourceMeta?.color}>{sourceMeta?.label}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="证据">
              {record.evidence_count} 条
            </Descriptions.Item>
          </Descriptions>

          <Form<MemoryEditFormValues> form={form} layout="vertical">
            <Form.Item
              name="text"
              label="记忆内容"
              rules={[
                { required: true, whitespace: true, message: "请填写记忆内容" },
                { max: 500, message: "记忆内容不能超过 500 个字符" },
              ]}
            >
              <Input.TextArea rows={4} maxLength={500} showCount />
            </Form.Item>
          </Form>

          <Alert
            type="info"
            showIcon
            message="修改后这条记忆会转为手动保存，并立即用于后续对话。原始证据引用会保留，便于追溯。"
          />
        </>
      )}
    </Modal>
  );
}
