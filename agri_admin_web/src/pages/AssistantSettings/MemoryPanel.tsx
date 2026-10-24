import { useCallback, useEffect, useState } from "react";
import { Alert, App, Button, Select, Space } from "antd";
import { DeleteOutlined, ReloadOutlined } from "@ant-design/icons";
import { Toolbar } from "../../components/PageShell";
import {
  isPersonalizationDemo,
  personalizationApi,
  personalizationErrorMessage,
  type MemoryKind,
  type MemoryCategory,
  type MemoryRecord,
  type MemoryScope,
  type MemoryStatus,
  type PersonalizationSettings,
} from "../../api/personalization";
import DemoNotice from "./DemoNotice";
import MemoryControls from "./MemoryControls";
import MemoryEditModal from "./MemoryEditModal";
import MemoryTable from "./MemoryTable";
import {
  MEMORY_KIND_FILTERS,
  MEMORY_CATEGORY_FILTERS,
  MEMORY_SCOPE_FILTERS,
  MEMORY_STATUS_FILTERS,
} from "./options";

export default function MemoryPanel() {
  const { modal, message } = App.useApp();
  const [memories, setMemories] = useState<MemoryRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);
  const [settingsError, setSettingsError] = useState<string | null>(null);
  const [demo, setDemo] = useState(false);
  const [preferences, setPreferences] = useState<PersonalizationSettings | null>(null);
  const [savingControl, setSavingControl] = useState(false);
  const [scope, setScope] = useState<MemoryScope | undefined>();
  const [kind, setKind] = useState<MemoryKind | undefined>();
  const [category, setCategory] = useState<MemoryCategory | undefined>();
  const [status, setStatus] = useState<MemoryStatus | undefined>();
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<MemoryRecord | null>(null);

  const fetchPreferences = useCallback(async () => {
    // 记忆和设置共享聚合版本，重读完成前不能提交旧版本的开关修改。
    setPreferences(null);
    setSettingsError(null);
    try {
      const data = await personalizationApi.getSettings();
      setPreferences(data);
      setDemo(isPersonalizationDemo());
    } catch (error) {
      setSettingsError(personalizationErrorMessage(error));
    }
  }, []);

  const fetchMemories = useCallback(async () => {
    setLoading(true);
    setListError(null);
    try {
      const data = await personalizationApi.listMemories({
        page,
        page_size: pageSize,
        scope,
        kind,
        category,
        status,
      });
      setMemories(data.items);
      setTotal(data.total);
      setDemo(isPersonalizationDemo());
    } catch (error) {
      setListError(personalizationErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, scope, kind, category, status]);

  useEffect(() => {
    void fetchPreferences();
  }, [fetchPreferences]);

  useEffect(() => {
    void fetchMemories();
  }, [fetchMemories]);

  const handleToggle = async (key: "use_saved_memories" | "auto_learn_enabled", checked: boolean) => {
    if (!preferences) return;
    setSavingControl(true);
    setSettingsError(null);
    try {
      const updated = await personalizationApi.updateSettings({
        expected_revision: preferences.revision,
        [key]: checked,
      });
      setPreferences(updated);
      setDemo(isPersonalizationDemo());
      message.success("记忆控制已更新");
    } catch (error) {
      setSettingsError(personalizationErrorMessage(error));
    } finally {
      setSavingControl(false);
    }
  };

  const handleConfirm = async (record: MemoryRecord) => {
    try {
      await personalizationApi.updateMemory(record.memory_id, {
        expected_revision: record.revision,
        status: "active",
      });
      message.success("已启用，这条记忆将用于后续对话");
      await Promise.all([fetchMemories(), fetchPreferences()]);
    } catch (error) {
      message.error(personalizationErrorMessage(error));
    }
  };

  const handleDelete = (record: MemoryRecord) => {
    modal.confirm({
      title: "删除这条记忆？",
      content: "删除后，助手将立即停止在后续对话中使用这条记忆。此操作不可恢复。",
      okText: "删除",
      cancelText: "取消",
      okButtonProps: { danger: true },
      onOk: async () => {
        try {
          await personalizationApi.deleteMemory(record.memory_id);
          message.success("记忆已删除");
          await fetchPreferences();
          if (memories.length === 1 && page > 1) {
            setPage(page - 1);
          } else {
            await fetchMemories();
          }
        } catch (error) {
          message.error(personalizationErrorMessage(error));
          throw error;
        }
      },
    });
  };

  const handleClear = () => {
    modal.confirm({
      title: "清空全部记忆",
      content:
        "清空后，所有长期记忆会立即停用，助手不再使用它们。个性化设置不会被重置，需要恢复默认请前往“个性化设置”。此操作不可恢复。",
      okText: "确认清空",
      cancelText: "取消",
      okButtonProps: { danger: true },
      onOk: async () => {
        try {
          await personalizationApi.clearMemories();
          message.success("已清空全部记忆");
          setPage(1);
          await Promise.all([fetchMemories(), fetchPreferences()]);
        } catch (error) {
          message.error(personalizationErrorMessage(error));
          throw error;
        }
      },
    });
  };

  const hasFilters = Boolean(scope || kind || category || status);
  const activeCount = memories.filter((memory) => memory.status === "active").length;
  const learnedCount = memories.filter(
    (memory) => memory.source_type === "inferred" && memory.status === "active",
  ).length;

  return (
    <div className="settings-stack memory-panel">
      {demo && (
        <DemoNotice description="后端记忆接口尚未接入，修改只在本次页面会话中生效。" />
      )}

      <div className="memory-summary">
        <div className="memory-stat">
          <div className="memory-stat__label">本页生效</div>
          <div className="memory-stat__value">
            {activeCount}
            <span>条</span>
          </div>
        </div>
        <div className="memory-stat">
          <div className="memory-stat__label">本页自动学习</div>
          <div className="memory-stat__value">
            {learnedCount}
            <span>条</span>
          </div>
        </div>
        <div className="memory-stat">
          <div className="memory-stat__label">全部记忆</div>
          <div className="memory-stat__value">
            {total}
            <span>条</span>
          </div>
        </div>
      </div>

      <MemoryControls
        preferences={preferences}
        settingsError={settingsError}
        savingControl={savingControl}
        onToggleSavedMemories={(checked) => void handleToggle("use_saved_memories", checked)}
        onToggleAutoLearn={(checked) => void handleToggle("auto_learn_enabled", checked)}
        onRetrySettings={() => void fetchPreferences()}
      />

      {listError && (
        <Alert
          type="error"
          showIcon
          message="记忆列表加载失败"
          description={listError}
          action={
            <Button size="small" onClick={() => void fetchMemories()}>
              重新加载
            </Button>
          }
        />
      )}

      <Toolbar
        left={(
          <Space wrap>
            <Select<MemoryCategory>
              allowClear placeholder="全部分类" style={{ width: 140 }} value={category}
              options={MEMORY_CATEGORY_FILTERS}
              onChange={(value) => { setCategory(value); setPage(1); }}
            />
            <Select<MemoryScope>
              allowClear
              placeholder="全部范围"
              style={{ width: 140 }}
              value={scope}
              onChange={(value) => {
                setScope(value);
                setPage(1);
              }}
              options={MEMORY_SCOPE_FILTERS}
            />
            <Select<MemoryKind>
              allowClear
              placeholder="全部类型"
              style={{ width: 130 }}
              value={kind}
              onChange={(value) => {
                setKind(value);
                setPage(1);
              }}
              options={MEMORY_KIND_FILTERS}
            />
            <Select<MemoryStatus>
              allowClear
              placeholder="全部状态"
              style={{ width: 130 }}
              value={status}
              onChange={(value) => {
                setStatus(value);
                setPage(1);
              }}
              options={MEMORY_STATUS_FILTERS}
            />
          </Space>
        )}
        right={(
          <Space wrap>
            <Button type="primary" onClick={() => setCreating(true)}>新增记忆</Button>
            <Button icon={<ReloadOutlined />} onClick={() => void fetchMemories()}>
              刷新
            </Button>
            <Button
              danger
              icon={<DeleteOutlined />}
              disabled={total === 0}
              onClick={handleClear}
            >
              清空记忆
            </Button>
          </Space>
        )}
      />

      <MemoryTable
        memories={memories}
        total={total}
        page={page}
        pageSize={pageSize}
        loading={loading}
        hasFilters={hasFilters}
        onPageChange={setPage}
        onEdit={setEditing}
        onConfirm={(record) => void handleConfirm(record)}
        onDelete={handleDelete}
      />

      {(editing || creating) && (
        <MemoryEditModal
          record={editing}
          open
          onCancel={() => { setEditing(null); setCreating(false); }}
          onSaved={() => {
            setEditing(null);
            setCreating(false);
            void Promise.all([fetchMemories(), fetchPreferences()]);
          }}
        />
      )}
    </div>
  );
}
