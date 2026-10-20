import { useCallback, useEffect, useState } from "react";
import { Alert, App, Button, Select, Space } from "antd";
import { DeleteOutlined, ReloadOutlined } from "@ant-design/icons";
import { Toolbar } from "../../components/PageShell";
import {
  isPersonalizationDemo,
  personalizationApi,
  personalizationErrorMessage,
  type MemoryKind,
  type MemoryRecord,
  type MemoryScope,
  type MemoryStatus,
  type PersonalizationSettings,
} from "../../api/personalization";
import MemoryControls from "./MemoryControls";
import MemoryEditModal from "./MemoryEditModal";
import MemoryTable from "./MemoryTable";
import {
  MEMORY_KIND_FILTERS,
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
  const [status, setStatus] = useState<MemoryStatus | undefined>();
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [editing, setEditing] = useState<MemoryRecord | null>(null);

  const fetchPreferences = useCallback(async () => {
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
  }, [page, pageSize, scope, kind, status]);

  useEffect(() => {
    void fetchPreferences();
  }, [fetchPreferences]);

  useEffect(() => {
    void fetchMemories();
  }, [fetchMemories]);

  const handleToggleSavedMemories = async (checked: boolean) => {
    if (!preferences) return;
    setSavingControl(true);
    setSettingsError(null);
    try {
      const updated = await personalizationApi.updateSettings({
        expected_revision: preferences.revision,
        use_saved_memories: checked,
      });
      setPreferences(updated);
      setDemo(isPersonalizationDemo());
      message.success(checked ? "已开启记忆使用" : "已关闭记忆使用");
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
      message.success("已确认，这条记忆将用于后续对话");
      await fetchMemories();
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

  const hasFilters = Boolean(scope || kind || status);

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      {demo && (
        <Alert
          type="warning"
          showIcon
          message="演示数据"
          description="后端记忆接口尚未接入，当前展示本地演示数据；修改只在本次页面会话中生效，刷新后恢复。"
        />
      )}

      <MemoryControls
        preferences={preferences}
        settingsError={settingsError}
        savingControl={savingControl}
        onToggleSavedMemories={(checked) => void handleToggleSavedMemories(checked)}
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
          <Space>
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

      <MemoryEditModal
        record={editing}
        open={editing !== null}
        onCancel={() => setEditing(null)}
        onSaved={() => {
          setEditing(null);
          void fetchMemories();
        }}
      />
    </Space>
  );
}
