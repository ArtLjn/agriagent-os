import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { App } from 'antd';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import RepairPackListPanel from './RepairPackListPanel';
import {
  getRepairPack,
  listRepairPacks,
  reopenRepairPack,
  type DataFlywheelRepairPack,
} from '../../../api/dataFlywheel';

vi.mock('../../../api/dataFlywheel', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../../api/dataFlywheel')>();
  return {
    ...actual,
    discardRepairPack: vi.fn(),
    getRepairPack: vi.fn(),
    listRepairPacks: vi.fn(),
    markRepairPackResolved: vi.fn(),
    recordRepairPackVerificationFailure: vi.fn(),
    reopenRepairPack: vi.fn(),
  };
});

function renderWithApp(ui: React.ReactNode) {
  return render(<App>{ui}</App>);
}

const basePack = (overrides: Partial<DataFlywheelRepairPack>): DataFlywheelRepairPack => ({
  id: 1,
  pack_id: 'repair-router-abc123',
  fix_target: 'router',
  labels: ['bad_reply', 'sensitive_info_leak'],
  source_sample_ids: ['turn:1:s:1', 'turn:2:s:2'],
  source_label_ids: [10, 20],
  dedup_key: 'deadbeefdeadbeef',
  status: 'exported',
  export_path: 'data/repair-packs/repair-router-abc123',
  manifest: {},
  ...overrides,
});

describe('RepairPackListPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(listRepairPacks).mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 10,
    });
  });

  it('初始加载调用 listRepairPacks 并渲染列表', async () => {
    vi.mocked(listRepairPacks).mockResolvedValue({
      items: [basePack({}), basePack({ id: 2, pack_id: 'repair-pending-plan-def456', fix_target: 'pending_plan' })],
      total: 2,
      page: 1,
      page_size: 10,
    });

    renderWithApp(<RepairPackListPanel onOpenDetail={() => undefined} />);

    await waitFor(() => {
      expect(screen.getByText('repair-router-abc123')).toBeInTheDocument();
      expect(screen.getByText('repair-pending-plan-def456')).toBeInTheDocument();
      expect(screen.getByText('共 2 条')).toBeInTheDocument();
    });
  });

  it('exported 状态显示标记为废弃按钮', async () => {
    vi.mocked(listRepairPacks).mockResolvedValue({
      items: [basePack({ status: 'exported' })],
      total: 1,
      page: 1,
      page_size: 10,
    });

    renderWithApp(<RepairPackListPanel onOpenDetail={() => undefined} />);

    await waitFor(() => {
      expect(screen.getByTestId('repair-pack-discard-repair-router-abc123')).toBeInTheDocument();
    });
  });

  it('exported 状态显示标记已修复 + 记录验证失败按钮', async () => {
    vi.mocked(listRepairPacks).mockResolvedValue({
      items: [basePack({ status: 'exported' })],
      total: 1,
      page: 1,
      page_size: 10,
    });

    renderWithApp(<RepairPackListPanel onOpenDetail={() => undefined} />);

    await waitFor(() => {
      expect(screen.getByTestId('repair-pack-resolve-repair-router-abc123')).toBeInTheDocument();
      expect(screen.getByTestId('repair-pack-fail-repair-router-abc123')).toBeInTheDocument();
    });
  });

  it('resolved 状态显示撤销已修复按钮', async () => {
    vi.mocked(listRepairPacks).mockResolvedValue({
      items: [basePack({ status: 'resolved' })],
      total: 1,
      page: 1,
      page_size: 10,
    });
    vi.mocked(reopenRepairPack).mockResolvedValue(basePack({ status: 'exported' }));

    renderWithApp(<RepairPackListPanel onOpenDetail={() => undefined} />);

    await waitFor(() => {
      expect(screen.getByTestId('repair-pack-reopen-repair-router-abc123')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('repair-pack-reopen-repair-router-abc123'));

    await waitFor(() => {
      expect(reopenRepairPack).toHaveBeenCalledWith('repair-router-abc123');
    });
  });

  it('discarded 状态显示恢复按钮', async () => {
    vi.mocked(listRepairPacks).mockResolvedValue({
      items: [basePack({ status: 'discarded' })],
      total: 1,
      page: 1,
      page_size: 10,
    });

    renderWithApp(<RepairPackListPanel onOpenDetail={() => undefined} />);

    await waitFor(() => {
      expect(screen.getByTestId('repair-pack-restore-repair-router-abc123')).toBeInTheDocument();
    });
  });

  it('点击查看详情触发 onOpenDetail 回调', async () => {
    const onOpenDetail = vi.fn();
    const fullPack = basePack({
      cases: [
        {
          sample_id: 'turn:1:s:1',
          labels: ['bad_reply'],
          observed_failure: '回复错误',
          expected_behavior: '应回复正确',
        },
      ],
    });
    vi.mocked(listRepairPacks).mockResolvedValue({
      items: [basePack({})],
      total: 1,
      page: 1,
      page_size: 10,
    });
    vi.mocked(getRepairPack).mockResolvedValue(fullPack);

    renderWithApp(<RepairPackListPanel onOpenDetail={onOpenDetail} />);

    await waitFor(() => {
      expect(screen.getByTestId('repair-pack-detail-repair-router-abc123')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('repair-pack-detail-repair-router-abc123'));

    await waitFor(() => {
      expect(getRepairPack).toHaveBeenCalledWith('repair-router-abc123');
      expect(onOpenDetail).toHaveBeenCalledWith(expect.objectContaining({ pack_id: 'repair-router-abc123' }));
    });
  });
});
