import { useCallback, useEffect, useRef, useState } from 'react';
import { Button, Modal, Tooltip, message } from 'antd';
import { CopyOutlined, DeleteOutlined, InboxOutlined, LinkOutlined, LoadingOutlined, MenuFoldOutlined, MenuUnfoldOutlined, ProfileOutlined, RollbackOutlined } from '@ant-design/icons';
import { archiveConversation, deleteConversation, listConversations, type ConversationItem } from '../../api/agent';
import { buildConversationRows } from './conversationRows';

interface Props {
  userToken: string | null;
  sessionId: string;
  sessions: Parameters<typeof buildConversationRows>[0];
  refreshVersion: number;
  collapsed: boolean;
  onCollapse: () => void;
  onSelect: (id: string, archived: boolean) => void;
  onRemove: (id: string) => void;
  onCopyId: (id: string) => void;
  onCopyJson: (id: string) => void;
  onTrace: (id: string) => void;
}

export function ConversationSidebar(props: Props) {
  const { userToken, refreshVersion, collapsed, sessions } = props;
  const [archived, setArchived] = useState(false);
  const [items, setItems] = useState<ConversationItem[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ConversationItem | null>(null);
  const [version, setVersion] = useState(0);
  const generation = useRef(0);
  const retryCursor = useRef<string | undefined>(undefined);
  const mounted = useRef(true);
  const rows = archived ? items : buildConversationRows(sessions, items);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; generation.current += 1; };
  }, []);

  const load = useCallback(async (next?: string) => {
    const request = ++generation.current;
    setLoading(true);
    setFailed(false);
    try {
      const page = await listConversations(50, userToken, { archived, ...(next ? { cursor: next } : {}) });
      if (request !== generation.current || !mounted.current) return;
      setItems((previous) => next ? [...previous, ...page.items.filter((item) => !previous.some((row) => row.conversation_id === item.conversation_id))] : page.items);
      setCursor(page.has_more ? page.next_cursor ?? null : null);
    } catch {
      if (request === generation.current && mounted.current) { retryCursor.current = next; setFailed(true); }
    } finally {
      if (request === generation.current && mounted.current) setLoading(false);
    }
  }, [archived, userToken]);

  useEffect(() => {
    void load();
    return () => { generation.current += 1; };
  }, [load, refreshVersion, version]);

  const changeTab = (value: boolean) => {
    generation.current += 1;
    setItems([]);
    setCursor(null);
    setFailed(false);
    setLoading(true);
    setActionError(null);
    setArchived(value);
  };

  const mutate = async (item: ConversationItem, remove = false) => {
    if (busy) return;
    setBusy(item.conversation_id);
    setActionError(null);
    try {
      if (remove) await deleteConversation(item.conversation_id, userToken);
      else await archiveConversation(item.conversation_id, !archived, userToken);
      if (!mounted.current) return;
      // 作废操作前的列表请求，避免迟到响应把已移走的会话重新放回列表。
      generation.current += 1;
      props.onRemove(item.conversation_id);
      setItems((previous) => previous.filter((row) => row.conversation_id !== item.conversation_id));
      setDeleteTarget(null);
      setVersion((current) => current + 1);
      message.success(remove ? '会话已删除' : archived ? '已恢复到会话列表' : '已归档到草稿箱');
    } catch {
      if (mounted.current) setActionError(remove ? '删除失败，请重试' : '会话操作失败，请重试');
    } finally {
      if (mounted.current) setBusy(null);
    }
  };

  return (
    <aside className={`pg-sidebar${collapsed ? ' pg-sidebar--collapsed' : ''}`} aria-label="会话列表">
      <div className="pg-sidebar__header">
        {!collapsed && <span>{archived ? '草稿箱' : '会话'} <span className="pg-sidebar__count">{rows.length}</span></span>}
        <Button type="text" aria-label={collapsed ? '展开侧边栏' : '折叠侧边栏'}
          icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />} onClick={props.onCollapse} />
      </div>
      {!collapsed && <div className="pg-sidebar__tabs" role="tablist" aria-label="会话分类">
        <button type="button" role="tab" aria-selected={!archived} disabled={Boolean(busy)} onClick={() => { if (archived) changeTab(false); }}>会话</button>
        <button type="button" role="tab" aria-selected={archived} disabled={Boolean(busy)} onClick={() => { if (!archived) changeTab(true); }}><InboxOutlined /> 草稿箱</button>
      </div>}
      {archived && !collapsed && <p className="pg-sidebar__hint">已归档的会话，可恢复或删除</p>}
      {actionError && !deleteTarget && <p className="pg-sidebar__hint" role="alert">{actionError}</p>}
      <div className="pg-sidebar__list surface-scroll" aria-busy={loading}>
        {rows.map((item) => {
          const id = item.conversation_id;
          const local = 'local' in item && item.local;
          const running = Boolean(sessions[id]?.loading);
          const title = item.last_message?.trim() || (local ? '新会话' : id);
          return <div key={id} className={`pg-session${id === props.sessionId ? ' pg-session--active' : ''}`}>
            <button type="button" className="pg-session__select" title={title} aria-label={`查看会话：${title}`}
              disabled={Boolean(busy)} onClick={() => props.onSelect(id, archived)}>
              {collapsed ? <span className="pg-session__dot">{id.slice(-2)}</span> : <>
                <span className="pg-session__title">{running && <LoadingOutlined />} {title}</span>
                <span className="pg-session__meta">{new Date(item.last_at).toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })} · {item.message_count} 条</span>
              </>}
            </button>
            {!collapsed && <div className="pg-session__actions">
              {archived ? <>
                <Tooltip title="恢复会话"><Button type="text" size="small" aria-label="恢复会话" icon={<RollbackOutlined />} disabled={Boolean(busy) || running} onClick={() => void mutate(item)} /></Tooltip>
                <Tooltip title="删除会话"><Button type="text" size="small" danger aria-label="删除会话" icon={<DeleteOutlined />} disabled={Boolean(busy) || running} onClick={() => setDeleteTarget(item)} /></Tooltip>
              </> : <>
                <Tooltip title="复制 Session ID"><Button type="text" size="small" aria-label="复制 Session ID" icon={<CopyOutlined />} onClick={() => props.onCopyId(id)} /></Tooltip>
                <Tooltip title="跳转链路追踪"><Button type="text" size="small" aria-label="跳转链路追踪" icon={<LinkOutlined />} onClick={() => props.onTrace(id)} /></Tooltip>
                <Tooltip title="复制调试 JSON"><Button type="text" size="small" aria-label="复制调试 JSON" icon={<ProfileOutlined />} onClick={() => props.onCopyJson(id)} /></Tooltip>
                <Tooltip title={running ? '生成结束后可归档' : '归档到草稿箱'}><Button type="text" size="small" aria-label="归档到草稿箱" icon={<InboxOutlined />} loading={busy === id} disabled={Boolean(busy) || running || Boolean(local)} onClick={() => void mutate(item)} /></Tooltip>
              </>}
            </div>}
          </div>;
        })}
        {!collapsed && loading && <p className="pg-sidebar__hint" role="status">加载中…</p>}
        {!collapsed && failed && <Button type="text" onClick={() => void load(retryCursor.current)}>加载失败，点击重试</Button>}
        {!collapsed && !loading && !failed && rows.length === 0 && <p className="pg-sidebar__hint">{archived ? '草稿箱为空' : '暂无历史会话'}</p>}
        {!collapsed && cursor && !failed && <Button type="text" loading={loading} onClick={() => void load(cursor)}>加载更多</Button>}
      </div>
      <Modal title="删除这段会话？" open={deleteTarget !== null} okText="删除" cancelText="取消"
        okButtonProps={{ danger: true, 'aria-label': '确认删除' }} confirmLoading={Boolean(busy)} closable={!busy}
        cancelButtonProps={{ disabled: Boolean(busy) }} onCancel={() => { if (!busy) setDeleteTarget(null); }}
        onOk={() => { if (deleteTarget) void mutate(deleteTarget, true); }}>
        <p>删除后无法恢复该会话。已保存的个性化记忆会继续保留，可在个人设置中管理。</p>
        <p className="pg-sidebar__delete-preview">{deleteTarget?.last_message}</p>
        {actionError && <p role="alert">{actionError}</p>}
      </Modal>
    </aside>
  );
}
