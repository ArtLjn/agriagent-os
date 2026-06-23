import {
  App,
  Button,
  Card,
  Empty,
  Input,
  List,
  Pagination,
  Popconfirm,
  Select,
  Space,
  Switch,
  Tag,
  Tooltip,
  Typography,
} from 'antd';
import { useCallback, useEffect, useState } from 'react';
import { ReloadOutlined } from '@ant-design/icons';
import type { CSSProperties } from 'react';

import {
  REPAIR_PACK_STATUS,
  type DataFlywheelRepairPack,
  type RepairPackStatus,
  discardRepairPack,
  getRepairPack,
  listRepairPacks,
  markRepairPackResolved,
  rebuildRepairPack,
  recordRepairPackVerificationFailure,
  reopenRepairPack,
} from '../../../api/dataFlywheel';
import { cardStyle, palette } from '../../../styles/theme';
import {
  REPAIR_PACK_STATUS_OPTIONS,
  repairPackStatusMeta,
} from './repairPackStatusMeta';

const PAGE_SIZE = 10;

interface RepairPackListPanelProps {
  onOpenDetail: (pack: DataFlywheelRepairPack) => void;
}

export default function RepairPackListPanel({ onOpenDetail }: RepairPackListPanelProps) {
  const { message: messageApi } = App.useApp();
  const [packs, setPacks] = useState<DataFlywheelRepairPack[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState<RepairPackStatus | undefined>(undefined);
  const [fixTargetFilter, setFixTargetFilter] = useState('');
  const [includeDiscarded, setIncludeDiscarded] = useState(false);
  const [actingPackId, setActingPackId] = useState<string | null>(null);

  const loadPacks = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listRepairPacks({
        status: statusFilter,
        fix_target: fixTargetFilter.trim() || undefined,
        include_discarded: includeDiscarded,
        page,
        page_size: PAGE_SIZE,
      });
      setPacks(data.items);
      setTotal(data.total);
    } catch (error) {
      messageApi.error('加载修复包列表失败');
      console.error('[RepairPackListPanel] load failed', error);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, fixTargetFilter, includeDiscarded, page, messageApi]);

  useEffect(() => {
    void loadPacks();
  }, [loadPacks]);

  const handleFilterChange = () => {
    setPage(1);
    void loadPacks();
  };

  const runAction = async (packId: string, action: () => Promise<DataFlywheelRepairPack>) => {
    setActingPackId(packId);
    try {
      await action();
      await loadPacks();
    } catch (error) {
      messageApi.error('操作失败');
      console.error('[RepairPackListPanel] action failed', error);
    } finally {
      setActingPackId(null);
    }
  };

  const handleDiscard = (pack: DataFlywheelRepairPack) => {
    void runAction(pack.pack_id, () =>
      discardRepairPack(pack.pack_id, { reason: '标记为重复或不再需要' })
    );
  };

  const handleReopen = (pack: DataFlywheelRepairPack) => {
    void runAction(pack.pack_id, () => reopenRepairPack(pack.pack_id));
  };

  const handleRebuild = (pack: DataFlywheelRepairPack) => {
    void runAction(pack.pack_id, () => rebuildRepairPack(pack.pack_id));
  };

  const handleResolve = (pack: DataFlywheelRepairPack) => {
    void runAction(pack.pack_id, () =>
      markRepairPackResolved(pack.pack_id, { repair_note: '在列表页标记为已修复' })
    );
  };

  const handleVerificationFailed = (pack: DataFlywheelRepairPack) => {
    void runAction(pack.pack_id, () =>
      recordRepairPackVerificationFailure(pack.pack_id, {
        verification_summary: { source: 'manual', passed: false },
      })
    );
  };

  const handleOpenDetail = async (pack: DataFlywheelRepairPack) => {
    setActingPackId(pack.pack_id);
    try {
      const full = await getRepairPack(pack.pack_id);
      onOpenDetail(full);
    } catch (error) {
      onOpenDetail(pack);
      messageApi.warning('加载失败案例详情失败，仅展示元数据');
      console.error('[RepairPackListPanel] getRepairPack failed', error);
    } finally {
      setActingPackId(null);
    }
  };

  return (
    <div style={panelStyle}>
      <Card
        size="small"
        title={
          <Space size={8}>
            <Typography.Text style={{ color: palette.text }}>修复包列表</Typography.Text>
            <Typography.Text style={{ color: palette.textMuted, fontSize: 12 }}>
              共 {total} 条
            </Typography.Text>
          </Space>
        }
        extra={
          <Button
            size="small"
            icon={<ReloadOutlined />}
            loading={loading}
            onClick={() => void loadPacks()}
          >
            刷新
          </Button>
        }
        style={cardStyle}
        styles={{ body: { padding: 12 } }}
      >
        <Space wrap style={{ marginBottom: 12 }}>
          <Select<RepairPackStatus | undefined>
            allowClear
            placeholder="状态筛选"
            value={statusFilter}
            onChange={(value) => {
              setStatusFilter(value as RepairPackStatus | undefined);
              handleFilterChange();
            }}
            options={REPAIR_PACK_STATUS_OPTIONS}
            style={{ width: 160 }}
          />
          <Input
            allowClear
            placeholder="fix_target 过滤"
            value={fixTargetFilter}
            onChange={(event) => setFixTargetFilter(event.target.value)}
            onPressEnter={handleFilterChange}
            onClear={handleFilterChange}
            style={{ width: 200 }}
          />
          <Space size={6}>
            <Switch
              size="small"
              checked={includeDiscarded}
              onChange={(checked) => {
                setIncludeDiscarded(checked);
                handleFilterChange();
              }}
            />
            <Typography.Text style={{ color: palette.textMuted, fontSize: 12 }}>
              显示已废弃
            </Typography.Text>
          </Space>
        </Space>

        <List
          loading={loading}
          dataSource={packs}
          locale={{
            emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无修复包" />,
          }}
          renderItem={(pack) => (
            <RepairPackRow
              pack={pack}
              acting={actingPackId === pack.pack_id}
              onOpenDetail={handleOpenDetail}
              onDiscard={handleDiscard}
              onReopen={handleReopen}
              onRebuild={handleRebuild}
              onResolve={handleResolve}
              onVerificationFailed={handleVerificationFailed}
            />
          )}
        />

        {total > PAGE_SIZE && (
          <Pagination
            current={page}
            pageSize={PAGE_SIZE}
            total={total}
            onChange={(next) => setPage(next)}
            showSizeChanger={false}
            style={{ marginTop: 12, textAlign: 'right' }}
          />
        )}
      </Card>
    </div>
  );
}

interface RepairPackRowProps {
  pack: DataFlywheelRepairPack;
  acting: boolean;
  onOpenDetail: (pack: DataFlywheelRepairPack) => void;
  onDiscard: (pack: DataFlywheelRepairPack) => void;
  onReopen: (pack: DataFlywheelRepairPack) => void;
  onRebuild: (pack: DataFlywheelRepairPack) => void;
  onResolve: (pack: DataFlywheelRepairPack) => void;
  onVerificationFailed: (pack: DataFlywheelRepairPack) => void;
}

function RepairPackRow({
  pack,
  acting,
  onOpenDetail,
  onDiscard,
  onReopen,
  onRebuild,
  onResolve,
  onVerificationFailed,
}: RepairPackRowProps) {
  const meta = repairPackStatusMeta(pack.status);
  const labels = Array.isArray(pack.labels) ? pack.labels : [];
  const sampleCount = Array.isArray(pack.source_sample_ids) ? pack.source_sample_ids.length : 0;
  const labelIdCount = Array.isArray(pack.source_label_ids) ? pack.source_label_ids.length : 0;
  const created = pack.created_at ? formatRelative(pack.created_at) : '—';
  const isDiscarded = pack.status === REPAIR_PACK_STATUS.DISCARDED;
  const isResolved = pack.status === REPAIR_PACK_STATUS.RESOLVED;

  return (
    <List.Item style={{ borderBottom: `1px solid ${palette.borderSoft}`, padding: '12px 4px' }}>
      <div style={{ width: '100%' }}>
        <Space direction="vertical" size={6} style={{ width: '100%' }}>
          <Space size={8} wrap align="center">
            <Typography.Text copyable style={{ color: palette.text, fontSize: 13 }}>
              {pack.pack_id}
            </Typography.Text>
            <Tag color="blue">{pack.fix_target}</Tag>
            <Tag color={meta.color}>{meta.label}</Tag>
            <Typography.Text style={{ color: palette.textMuted, fontSize: 12 }}>
              {created}
            </Typography.Text>
          </Space>

          <Space size={8} wrap style={{ color: palette.textMuted, fontSize: 12 }}>
            <span>样本 {sampleCount}</span>
            <span>·</span>
            <span>关联标签 {labelIdCount}</span>
            {labels.length > 0 && (
              <>
                <span>·</span>
                <Tooltip title={labels.join(', ')}>
                  <span style={{ maxWidth: 360, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {labels.join(' / ')}
                  </span>
                </Tooltip>
              </>
            )}
            {pack.created_by && (
              <>
                <span>·</span>
                <span>由 {pack.created_by} 创建</span>
              </>
            )}
            {pack.dedup_key && (
              <>
                <span>·</span>
                <Tooltip title={`dedup_key: ${pack.dedup_key}`}>
                  <span style={{ fontFamily: 'monospace', fontSize: 11 }}>
                    #{pack.dedup_key.slice(0, 8)}
                  </span>
                </Tooltip>
              </>
            )}
          </Space>

          <Space size={6} wrap>
            <Button
              size="small"
              onClick={() => onOpenDetail(pack)}
              loading={acting}
              data-testid={`repair-pack-detail-${pack.pack_id}`}
            >
              查看详情
            </Button>
            <Button
              size="small"
              loading={acting}
              onClick={() => onRebuild(pack)}
              data-testid={`repair-pack-rebuild-${pack.pack_id}`}
            >
              同步重建
            </Button>
            {!isResolved && !isDiscarded && pack.status !== REPAIR_PACK_STATUS.EXPORT_FAILED && (
              <Button
                size="small"
                type="primary"
                loading={acting}
                onClick={() => onResolve(pack)}
                data-testid={`repair-pack-resolve-${pack.pack_id}`}
              >
                标记已修复
              </Button>
            )}
            {pack.status === REPAIR_PACK_STATUS.EXPORTED && (
              <Button
                size="small"
                loading={acting}
                onClick={() => onVerificationFailed(pack)}
                data-testid={`repair-pack-fail-${pack.pack_id}`}
              >
                记录验证失败
              </Button>
            )}
            {isResolved && (
              <Button
                size="small"
                loading={acting}
                onClick={() => onReopen(pack)}
                data-testid={`repair-pack-reopen-${pack.pack_id}`}
              >
                撤销已修复
              </Button>
            )}
            {!isDiscarded && (
              <Popconfirm
                title="标记为废弃？"
                description="该修复包将从默认列表中隐藏，可勾选显示已废弃开关找回。"
                onConfirm={() => onDiscard(pack)}
                okText="废弃"
                cancelText="取消"
              >
                <Button
                  size="small"
                  danger
                  loading={acting}
                  data-testid={`repair-pack-discard-${pack.pack_id}`}
                >
                  标记为废弃
                </Button>
              </Popconfirm>
            )}
            {isDiscarded && (
              <Button
                size="small"
                loading={acting}
                onClick={() => onReopen(pack)}
                data-testid={`repair-pack-restore-${pack.pack_id}`}
              >
                恢复
              </Button>
            )}
          </Space>
        </Space>
      </div>
    </List.Item>
  );
}

function formatRelative(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  const diffMs = Date.now() - date.getTime();
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return '刚刚';
  if (minutes < 60) return `${minutes} 分钟前`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} 小时前`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days} 天前`;
  return date.toLocaleDateString('zh-CN');
}

const panelStyle: CSSProperties = {
  width: '100%',
  minHeight: 'calc(100vh - 200px)',
};
