import { Button, Divider, Form, Input, InputNumber, Space } from 'antd';
import { MinusCircleOutlined, PlusOutlined } from '@ant-design/icons';

export type TemplateFormStageValue = {
  name?: string;
  duration_days?: number;
  key_tasks?: string;
};

export type TemplateFormValues = {
  name: string;
  variety?: string | null;
  category?: string | null;
  stages: TemplateFormStageValue[];
};

export default function TemplateForm({ showCategory = false }: { showCategory?: boolean }) {
  return (
    <>
      <Form.Item
        name="name"
        label="名称"
        rules={[{ required: true, message: '请输入模板名称' }]}
      >
        <Input placeholder="如：西瓜" />
      </Form.Item>
      <Form.Item name="variety" label="品种">
        <Input placeholder="如：8424" />
      </Form.Item>
      {showCategory && (
        <Form.Item name="category" label="分类">
          <Input placeholder="如：粮食 / 蔬菜 / 水果" />
        </Form.Item>
      )}

      <Divider>生长阶段</Divider>
      <Form.List name="stages">
        {(fields, { add, remove }) => (
          <>
            {fields.map(({ key, name, ...restField }) => (
              <Space key={key} style={{ display: 'flex', marginBottom: 8 }} align="baseline">
                <Form.Item
                  {...restField}
                  name={[name, 'name']}
                  rules={[{ required: true, message: '阶段名' }]}
                >
                  <Input placeholder="阶段名" style={{ width: 120 }} />
                </Form.Item>
                <Form.Item
                  {...restField}
                  name={[name, 'duration_days']}
                  rules={[{ required: true, message: '天数' }]}
                >
                  <InputNumber placeholder="天数" min={1} style={{ width: 90 }} />
                </Form.Item>
                <Form.Item {...restField} name={[name, 'key_tasks']}>
                  <Input placeholder="关键任务（选填）" style={{ width: 160 }} />
                </Form.Item>
                <MinusCircleOutlined onClick={() => remove(name)} />
              </Space>
            ))}
            <Button type="dashed" onClick={() => add()} block icon={<PlusOutlined />}>
              添加阶段
            </Button>
          </>
        )}
      </Form.List>
    </>
  );
}
