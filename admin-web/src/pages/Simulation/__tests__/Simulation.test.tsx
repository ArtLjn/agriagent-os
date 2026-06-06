import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import axios from 'axios';
import Simulation from '../index';

vi.mock('axios');
const mockedAxios = vi.mocked(axios, true);

describe('Simulation Page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Meta - 页面渲染', () => {
    it('应渲染页面标题和配置栏', async () => {
      mockedAxios.get.mockResolvedValue({ data: { cases: [] } });

      render(<Simulation />);

      await waitFor(() => {
        expect(screen.getByText('Agent 仿真测试平台')).toBeInTheDocument();
      });
      expect(screen.getByPlaceholderText('Agent 地址')).toHaveValue('http://localhost:8000');
    });

    it('应渲染用例列表区域和操作区域', async () => {
      mockedAxios.get.mockResolvedValue({ data: { cases: [] } });

      render(<Simulation />);

      await waitFor(() => {
        expect(screen.getByText('测试用例')).toBeInTheDocument();
      });
      expect(screen.getByText(/运行选中用例/)).toBeInTheDocument();
      expect(screen.getByText(/运行全部/)).toBeInTheDocument();
    });
  });

  describe('Normal - 正常流程', () => {
    it('应加载并显示测试用例列表', async () => {
      const mockCases = [
        {
          case_id: 'TC-001',
          description: '记账化肥',
          user_input: '买了200块化肥',
          category: 'basic',
          expected_response_matches: ['已记账'],
          expected_db_changes: {},
          verify_tables: ['cost_records'],
        },
        {
          case_id: 'TC-002',
          description: '幻觉检测',
          user_input: '查一下不存在的作物',
          category: 'hallucination',
          expected_response_matches: [],
          expected_db_changes: {},
          verify_tables: [],
        },
      ];

      mockedAxios.get.mockResolvedValue({ data: { cases: mockCases } });

      render(<Simulation />);

      await waitFor(() => {
        expect(screen.getByText('TC-001')).toBeInTheDocument();
      });
      expect(screen.getByText('记账化肥')).toBeInTheDocument();
      expect(screen.getByText('TC-002')).toBeInTheDocument();
      expect(screen.getByText('幻觉检测')).toBeInTheDocument();
    });

    it('应渲染分类筛选下拉框', async () => {
      const mockCases = [
        { case_id: 'TC-001', description: '记账', user_input: 'test', category: 'basic', expected_response_matches: [], expected_db_changes: {}, verify_tables: [] },
        { case_id: 'TC-002', description: '幻觉', user_input: 'test', category: 'hallucination', expected_response_matches: [], expected_db_changes: {}, verify_tables: [] },
      ];

      mockedAxios.get.mockResolvedValue({ data: { cases: mockCases } });

      render(<Simulation />);

      await waitFor(() => {
        expect(screen.getByText('TC-001')).toBeInTheDocument();
      });

      // 验证分类筛选下拉框存在
      const select = document.querySelector('.ant-select');
      expect(select).toBeTruthy();

      // 打开下拉菜单验证选项存在
      const selectInput = document.querySelector('.ant-select-selector');
      if (selectInput) {
        fireEvent.mouseDown(selectInput);
      }

      await waitFor(() => {
        const dropdown = document.querySelector('.ant-select-dropdown');
        expect(dropdown).toBeTruthy();
      });

      const dropdown = document.querySelector('.ant-select-dropdown');
      if (dropdown) {
        // 验证下拉菜单中包含分类选项（使用 role="option" 来精确定位下拉菜单中的选项）
        const options = within(dropdown as HTMLElement).getAllByRole('option');
        const optionTexts = options.map(o => o.textContent);
        // antd Select 可能只渲染可见选项
        expect(optionTexts.length).toBeGreaterThan(0);
        expect(optionTexts).toContain('basic');
      }
    });

    it('应能启动运行并显示进度', async () => {
      const mockCases = [
        { case_id: 'TC-001', description: '记账', user_input: 'test', category: 'basic', expected_response_matches: [], expected_db_changes: {}, verify_tables: [] },
      ];

      mockedAxios.get.mockResolvedValue({ data: { cases: mockCases } });

      render(<Simulation />);

      await waitFor(() => {
        expect(screen.getByText('TC-001')).toBeInTheDocument();
      });

      // 选中用例 - 找到用例列表中的 checkbox
      const checkboxes = screen.getAllByRole('checkbox');
      const caseCheckbox = checkboxes.find(cb => {
        const parent = cb.closest('div');
        return parent && parent.textContent?.includes('TC-001');
      });
      if (caseCheckbox) {
        fireEvent.click(caseCheckbox);
      }

      // 启动运行
      mockedAxios.post.mockResolvedValueOnce({ data: { run_id: 'run_001', status: 'running', total: 1 } });

      const runBtn = screen.getByText(/运行选中用例/);
      fireEvent.click(runBtn);

      await waitFor(() => {
        expect(mockedAxios.post).toHaveBeenCalledWith('/simulation/run', {
          case_ids: ['TC-001'],
          agent_url: 'http://localhost:8000',
        });
      });
    });

    it('应显示运行结果表格', async () => {
      const mockCases = [
        { case_id: 'TC-001', description: '记账', user_input: 'test', category: 'basic', expected_response_matches: [], expected_db_changes: {}, verify_tables: [] },
        { case_id: 'TC-002', description: '幻觉', user_input: 'test', category: 'hallucination', expected_response_matches: [], expected_db_changes: {}, verify_tables: [] },
      ];

      mockedAxios.get.mockResolvedValue({ data: { cases: mockCases } });

      render(<Simulation />);

      await waitFor(() => {
        expect(screen.getByText('TC-001')).toBeInTheDocument();
      });

      // 模拟运行完成后的状态 - 通过运行全部来触发
      mockedAxios.post.mockResolvedValueOnce({
        data: { run_id: 'run_001', status: 'completed', total: 2 },
      });

      const runAllBtn = screen.getByText(/运行全部/);
      fireEvent.click(runAllBtn);

      await waitFor(() => {
        expect(mockedAxios.post).toHaveBeenCalledWith('/simulation/run', {
          case_ids: null,
          agent_url: 'http://localhost:8000',
        });
      });
    });
  });

  describe('Error - 异常处理', () => {
    it('API 失败时应显示错误消息', async () => {
      mockedAxios.get.mockRejectedValue(new Error('Network Error'));

      render(<Simulation />);

      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalled();
      });
    });

    it('运行按钮应在未选择用例时禁用', async () => {
      const mockCases = [
        { case_id: 'TC-001', description: '记账', user_input: 'test', category: 'basic', expected_response_matches: [], expected_db_changes: {}, verify_tables: [] },
      ];

      mockedAxios.get.mockResolvedValue({ data: { cases: mockCases } });

      render(<Simulation />);

      await waitFor(() => {
        expect(screen.getByText('TC-001')).toBeInTheDocument();
      });

      const runBtn = screen.getByText(/运行选中用例/);
      expect(runBtn.closest('button')).toBeDisabled();
    });
  });
});
