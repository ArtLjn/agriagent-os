import { useEffect, useState } from 'react';
import {
  Typography,
  Button,
  Table,
  Tag,
  Empty,
  Spin,
  Modal,
  Descriptions,
  message,
} from 'antd';
import { FileSearchOutlined, ReloadOutlined } from '@ant-design/icons';
import { listPrompts, reloadPrompts, type PromptItem } from '../../api/admin';

const CARD_BG = '#161b22';
const BORDER = '#30363d';
const TEXT = '#e6edf3';
const TEXT_DIM = '#8b949e';

export default function PromptInspector() {
  const [prompts, setPrompts] = useState<PromptItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [reloadLoading, setReloadLoading] = useState(false);
  const [previewModalOpen, setPreviewModalOpen] = useState(false);
  const [previewPrompt, setPreviewPrompt] = useState<PromptItem | null>(null);

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await listPrompts();
      setPrompts(res.items);
    } catch {
      // 错误已在 api client 中处理
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleReload = async () => {
    setReloadLoading(true);
    try {
      const res = await reloadPrompts();
      message.success(res.message || '重新加载成功');
      await fetchData();
    } catch {
      // 错误已在 api client 中处理
    } finally {
      setReloadLoading(false);
    }
  };

  const handlePreview = (prompt: PromptItem) => {
    setPreviewPrompt(prompt);
    setPreviewModalOpen(true);
  };

  const columns = [
    {
      title: '名称',
      dataIndex: 'name',
      render: (v: string) => <span style={{ color: TEXT }}>{v}</span>,
    },
    {
      title: '版本',
      dataIndex: 'version',
      width: 120,
      render: (v: string) => <span style={{ color: TEXT_DIM }}>{v}</span>,
    },
    {
      title: '状态',
      dataIndex: 'active',
      width: 100,
      render: (v: boolean) => (
        <Tag color={v ? 'success' : 'default'}>{v ? '启用' : '禁用'}</Tag>
      ),
    },
    {
      title: '内容长度',
      dataIndex: 'content_length',
      width: 120,
      render: (v: number) => (
        <span style={{ color: TEXT_DIM }}>{v.toLocaleString()}</span>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_: unknown, record: PromptItem) => (
        <Button type="link" onClick={() => handlePreview(record)}>
          预览
        </Button>
      ),
    },
  ];

  return (
    <div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 16,
        }}
      >
        <Typography.Title level={4} style={{ color: TEXT, margin: 0 }}>
          <FileSearchOutlined style={{ marginRight: 8 }} />
          Prompt 检查器
        </Typography.Title>
        <Button
          type="primary"
          icon={<ReloadOutlined />}
          loading={reloadLoading}
          onClick={handleReload}
        >
          重新加载模板
        </Button>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: 64 }}>
          <Spin size="large" />
        </div>
      ) : prompts.length === 0 ? (
        <Empty description="暂无 Prompt 数据" style={{ marginTop: 64 }} />
      ) : (
        <Table
          rowKey="name"
          dataSource={prompts}
          columns={columns}
          pagination={false}
          style={{
            backgroundColor: CARD_BG,
            border: `1px solid ${BORDER}`,
            borderRadius: 8,
          }}
        />
      )}

      <Modal
        title="Prompt 预览"
        open={previewModalOpen}
        onCancel={() => setPreviewModalOpen(false)}
        footer={null}
        width={520}
        styles={{
          content: { backgroundColor: CARD_BG },
          header: {
            backgroundColor: CARD_BG,
            color: TEXT,
            borderBottom: `1px solid ${BORDER}`,
          },
          body: { backgroundColor: CARD_BG },
        }}
      >
        {previewPrompt && (
          <div>
            <Descriptions
              column={1}
              labelStyle={{ color: TEXT_DIM, width: 100 }}
              contentStyle={{ color: TEXT }}
            >
              <Descriptions.Item label="名称">
                {previewPrompt.name}
              </Descriptions.Item>
              <Descriptions.Item label="版本">
                {previewPrompt.version}
              </Descriptions.Item>
              <Descriptions.Item label="状态">
                <Tag color={previewPrompt.active ? 'success' : 'default'}>
                  {previewPrompt.active ? '启用' : '禁用'}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="内容长度">
                {previewPrompt.content_length.toLocaleString()} 字符
              </Descriptions.Item>
            </Descriptions>
            <div
              style={{
                marginTop: 16,
                padding: 12,
                backgroundColor: '#0d1117',
                border: `1px solid ${BORDER}`,
                borderRadius: 6,
                maxHeight: 400,
                overflow: 'auto',
              }}
            >
              <pre
                style={{
                  color: TEXT,
                  fontSize: 13,
                  lineHeight: 1.6,
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  margin: 0,
                  fontFamily: 'monospace',
                }}
              >
                {previewPrompt.content}
              </pre>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
