import { useEffect, useRef, useState } from 'react';
import { Alert, Button, Card, Empty, Form, Input, Modal, Segmented, Space, Table, Tag, Typography, message } from 'antd';
import { PlusOutlined, PushpinOutlined, ReloadOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { memosApi, MEMO_PAGE_SIZE, type Memo, type MemoDraft, type MemoUpdate } from '../../api/memos';
import { parseApiError } from '../../api/client';
import { PageShell, Toolbar } from '../../components/PageShell';
import { cardStyle } from '../../styles/theme';

export function MemoPanel() {
  const [items, setItems] = useState<Memo[]>([]);
  const [total, setTotal] = useState(0);
  const [keyword, setKeyword] = useState('');
  const [archived, setArchived] = useState(false);
  const [page, setPage] = useState(1);
  const [revision, setRevision] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [editor, setEditor] = useState<Memo | 'new' | null>(null);
  const requestId = useRef<string | null>(null);
  const mutationPending = useRef(false);
  const [form] = Form.useForm<MemoDraft>();

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    // 切换筛选时清除旧行，避免把上一页或已归档的内容当成当前结果操作。
    setItems([]);
    setTotal(0);
    async function load() {
      try {
        const result = await memosApi.list({ keyword, archived, limit: MEMO_PAGE_SIZE, skip: (page - 1) * MEMO_PAGE_SIZE }, controller.signal);
        if (controller.signal.aborted) return;
        const lastPage = Math.max(1, Math.ceil(result.total / MEMO_PAGE_SIZE));
        if (page > lastPage) { setPage(lastPage); return; }
        setItems(result.items);
        setTotal(result.total);
      } catch (cause) {
        if (controller.signal.aborted) return;
        const response = (cause as { response?: { data?: unknown } }).response;
        setError(parseApiError(response?.data).message || '备忘录加载失败，请重试');
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }
    void load();
    return () => controller.abort();
  }, [keyword, archived, page, revision]);

  function openEditor(memo: Memo | 'new') {
    requestId.current = null;
    form.setFieldsValue(memo === 'new' ? { title: '', content: '' } : { title: memo.title, content: memo.content });
    setEditor(memo);
  }

  async function save(values: MemoDraft) {
    if (mutationPending.current || editor === null) return;
    mutationPending.current = true;
    setSaving(true);
    try {
      if (editor === 'new') {
        // 网络失败时复用同一个请求键；用户修改内容后才生成新键。
        requestId.current ??= crypto.randomUUID();
        await memosApi.create({ ...values, client_request_id: requestId.current });
        setArchived(false);
        setKeyword('');
        setPage(1);
      } else {
        await memosApi.update(editor.id, values);
      }
      setEditor(null);
      setRevision(value => value + 1);
      message.success('备忘录已保存');
    } catch {
      // API 层展示错误，保留输入便于修改或使用同一请求键重试。
    } finally {
      mutationPending.current = false;
      setSaving(false);
    }
  }

  async function update(memo: Memo, changes: MemoUpdate) {
    if (mutationPending.current) return;
    mutationPending.current = true;
    setSaving(true);
    try {
      await memosApi.update(memo.id, changes);
      setRevision(value => value + 1);
      message.success('备忘录已更新');
    } catch {
      // 请求失败时不改动列表，避免显示未保存的状态。
    } finally {
      mutationPending.current = false;
      setSaving(false);
    }
  }

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Typography.Text type="secondary">记录待办与灵感，随时让 Agent 帮你查找。仅展示当前登录用户在当前农场的备忘录；Playground 模拟用户的记录互相隔离。</Typography.Text>
      <Toolbar
        left={<Space wrap>
          <Segmented value={archived ? 'archived' : 'active'} options={[{ label: '我的备忘录', value: 'active' }, { label: '已归档', value: 'archived' }]}
            onChange={value => { setArchived(value === 'archived'); setPage(1); }} />
          <Input.Search key={keyword} defaultValue={keyword} aria-label="搜索备忘录" placeholder="搜索标题或内容" maxLength={200} allowClear
            style={{ width: 260 }} onSearch={value => { setKeyword(value.trim()); setPage(1); }} />
        </Space>}
        right={<Space>
          <Button icon={<ReloadOutlined />} loading={loading} onClick={() => setRevision(value => value + 1)}>刷新</Button>
          <Button type="primary" icon={<PlusOutlined />} disabled={saving} onClick={() => openEditor('new')}>新建备忘录</Button>
        </Space>}
      />
      {error ? <Alert type="error" showIcon message={error} action={<Button onClick={() => setRevision(value => value + 1)}>重试</Button>} /> : (
        <Card style={cardStyle} styles={{ body: { padding: 0 } }}>
          <Table<Memo> rowKey="id" dataSource={items} loading={loading} scroll={{ x: 720 }}
            locale={{ emptyText: <Empty description={keyword ? '没有找到匹配的备忘录' : archived ? '暂无归档备忘录' : '还没有备忘录，记下第一件事吧'} /> }}
            pagination={{ current: page, pageSize: MEMO_PAGE_SIZE, total, showSizeChanger: false, onChange: setPage, showTotal: count => `共 ${count} 条` }}
            columns={[
              { title: '备忘录', key: 'memo', render: (_, memo) => <div style={{ maxWidth: 640 }}>
                <Space>{memo.pinned && <Tag icon={<PushpinOutlined />} color="gold">置顶</Tag>}
                  <Button type="link" disabled={saving} style={{ padding: 0, height: 'auto', whiteSpace: 'normal', textAlign: 'left' }} onClick={() => openEditor(memo)}>{memo.title}</Button>
                </Space>
                <Typography.Paragraph type="secondary" ellipsis={{ rows: 2 }} style={{ margin: '6px 0 0', whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{memo.content}</Typography.Paragraph>
              </div> },
              { title: '更新时间', dataIndex: 'updated_at', width: 170, render: value => dayjs(value).format('YYYY-MM-DD HH:mm') },
              { title: '操作', key: 'actions', width: 205, render: (_, memo) => <Space size={0}>
                <Button type="link" disabled={saving} onClick={() => openEditor(memo)}>编辑</Button>
                <Button type="link" disabled={saving} onClick={() => void update(memo, { pinned: !memo.pinned })}>{memo.pinned ? '取消置顶' : '置顶'}</Button>
                <Button type="link" disabled={saving} onClick={() => void update(memo, { archived: !memo.archived })}>{memo.archived ? '恢复' : '归档'}</Button>
              </Space> },
            ]}
          />
        </Card>
      )}
      <Modal title={editor === 'new' ? '新建备忘录' : '编辑备忘录'} open={editor !== null} okText="保存" cancelText="取消"
        confirmLoading={saving} closable={!saving} maskClosable={!saving} keyboard={!saving} cancelButtonProps={{ disabled: saving }}
        onCancel={() => { if (!saving) setEditor(null); }} onOk={() => form.submit()}>
        <Form form={form} layout="vertical" disabled={saving} onFinish={save} onValuesChange={() => { requestId.current = null; }}>
          <Form.Item name="title" label="标题" rules={[{ required: true, whitespace: true, message: '请输入标题' }, { max: 200 }]}>
            <Input maxLength={200} showCount placeholder="例如：明天的田间巡查" />
          </Form.Item>
          <Form.Item name="content" label="内容" rules={[{ required: true, whitespace: true, message: '请输入内容' }, { max: 10000 }]}>
            <Input.TextArea rows={7} maxLength={10000} showCount placeholder="记下需要留意的事情……" />
          </Form.Item>
          <Typography.Text type="secondary">保存为备忘录，不会自动发送到期通知。</Typography.Text>
        </Form>
      </Modal>
    </Space>
  );
}

export default function Memos() {
  return <PageShell title="提醒 / 备忘录" description="把零散事项记下来，让每件事都有处可查。"><MemoPanel /></PageShell>;
}
