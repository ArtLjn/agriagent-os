import { Button, Empty, Space, Table, Tag } from "antd";
import type { ColumnsType } from "antd/es/table";
import { CheckOutlined, DeleteOutlined, EditOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { palette } from "../../styles/theme";
import type { MemoryRecord } from "../../api/personalization";
import {
  MEMORY_KIND_META,
  MEMORY_CATEGORY_LABELS,
  MEMORY_SCOPE_META,
  MEMORY_SOURCE_META,
  MEMORY_STATUS_META,
} from "./options";

const captionStyle = { color: palette.textMuted, fontSize: 12 };

function tagColor(color: string): string | undefined {
  return color === "default" ? undefined : color;
}

interface MemoryTableProps {
  memories: MemoryRecord[];
  total: number;
  page: number;
  pageSize: number;
  loading: boolean;
  hasFilters: boolean;
  onPageChange: (page: number) => void;
  onEdit: (record: MemoryRecord) => void;
  onConfirm: (record: MemoryRecord) => void;
  onDelete: (record: MemoryRecord) => void;
}

export default function MemoryTable({
  memories,
  total,
  page,
  pageSize,
  loading,
  hasFilters,
  onPageChange,
  onEdit,
  onConfirm,
  onDelete,
}: MemoryTableProps) {
  const columns: ColumnsType<MemoryRecord> = [
    {
      title: "记忆内容",
      dataIndex: "text",
      key: "text",
      render: (_: unknown, record: MemoryRecord) => (
        <div style={{ maxWidth: 380 }}>
          <div>{record.text}</div>
          <Tag bordered={false}>{MEMORY_CATEGORY_LABELS[record.category ?? "general"]}</Tag>
          {record.review_reason && (
            <div style={captionStyle}>{record.review_reason}</div>
          )}
          {record.conflicts_with && (
            <Tag color="warning">与已有记忆不一致，请核对</Tag>
          )}
          {(record.conditions ?? []).length > 0 && (
            <Space size={4} wrap style={{ marginTop: 6 }}>
              {(record.conditions ?? []).map((condition) => (
                <Tag key={condition} bordered={false} className="memory-condition-tag">
                  {condition}
                </Tag>
              ))}
            </Space>
          )}
        </div>
      ),
    },
    {
      title: "范围",
      key: "scope",
      width: 140,
      render: (_: unknown, record: MemoryRecord) => {
        const meta = MEMORY_SCOPE_META[record.scope];
        return (
          <>
            <Tag color={meta.color}>{meta.label}</Tag>
            {record.scope === "user_farm" && record.farm_name && (
              <div style={captionStyle}>{record.farm_name}</div>
            )}
          </>
        );
      },
    },
    {
      title: "类型",
      key: "kind",
      width: 90,
      render: (_: unknown, record: MemoryRecord) => {
        const meta = MEMORY_KIND_META[record.kind];
        return <Tag color={tagColor(meta.color)}>{meta.label}</Tag>;
      },
    },
    {
      title: "来源",
      key: "source",
      width: 150,
      render: (_: unknown, record: MemoryRecord) => {
        const meta = MEMORY_SOURCE_META[record.source_type];
        return (
          <>
            <Tag color={meta.color}>{meta.label}</Tag>
            <div style={captionStyle}>
              {record.evidence_count} 条证据
              {record.source_type === "inferred" && record.confidence != null
                ? ` · 置信度 ${Math.round(record.confidence * 100)}%`
                : ""}
            </div>
          </>
        );
      },
    },
    {
      title: "状态",
      key: "status",
      width: 100,
      render: (_: unknown, record: MemoryRecord) => {
        const meta = MEMORY_STATUS_META[record.status];
        return <Tag color={tagColor(meta.color)}>{meta.label}</Tag>;
      },
    },
    {
      title: "更新时间",
      dataIndex: "updated_at",
      key: "updated_at",
      width: 150,
      render: (value: string) => dayjs(value).format("YYYY-MM-DD HH:mm"),
    },
    {
      title: "操作",
      key: "actions",
      width: 180,
      render: (_: unknown, record: MemoryRecord) => {
        const editable = record.status === "active" || record.status === "candidate";
        return (
          <Space size={0}>
            <Button
              type="link"
              size="small"
              icon={<EditOutlined />}
              disabled={!editable}
              onClick={() => onEdit(record)}
            >
              编辑
            </Button>
            {record.status === "candidate" && (
              <Button
                type="link"
                size="small"
                icon={<CheckOutlined />}
                onClick={() => onConfirm(record)}
              >
                启用
              </Button>
            )}
            <Button
              type="link"
              size="small"
              danger
              icon={<DeleteOutlined />}
              onClick={() => onDelete(record)}
            >
              删除
            </Button>
          </Space>
        );
      },
    },
  ];

  return (
    <Table<MemoryRecord>
      columns={columns}
      dataSource={memories}
      rowKey="memory_id"
      loading={loading}
      scroll={{ x: 1080 }}
      locale={{
        emptyText: (
          <Empty
            description={
              hasFilters
                ? "没有符合筛选条件的记忆"
                : "还没有长期记忆。开启自动学习后，助手会从日常对话中积累偏好；你也可以主动添加。"
            }
          />
        ),
      }}
      pagination={{
        current: page,
        pageSize,
        total,
        showSizeChanger: false,
        showTotal: (count) => `共 ${count} 条记忆`,
        onChange: onPageChange,
      }}
      style={{ background: palette.bgElevated, borderRadius: 8 }}
    />
  );
}
