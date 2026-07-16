import { useState, useEffect, useCallback } from "react";
import {
  Table,
  Tag,
  Button,
  Input,
  Select,
  Space,
  Modal,
  Descriptions,
  App,
  Statistic,
  Progress,
  Row,
  Col,
  InputNumber,
} from "antd";
import {
  TeamOutlined,
  StopOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  SettingOutlined,
} from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import { MetricCard, PageShell, Toolbar } from "../../components/PageShell";
import { palette } from "../../styles/theme";
import {
  usersApi,
  type UserListItem,
  type UserDetail,
  type ListUsersParams,
  type UserQuotaStatus,
  type UserQuotaOverviewItem,
} from "../../api/users";

const BG_CARD = "#21262d";
const BORDER = "#30363d";
const TEXT_SECONDARY = "#8b949e";
const ACCENT = "#58a6ff";
const DEFAULT_MONTHLY_LIMIT = 200000;
const DEFAULT_WEEKLY_LIMIT = 50000;

const quotaPresets = [
  {
    key: "light",
    label: "轻量",
    description: "少量问答和偶发报告",
    monthly: 50000,
    weekly: 15000,
  },
  {
    key: "standard",
    label: "标准",
    description: "日常使用推荐",
    monthly: DEFAULT_MONTHLY_LIMIT,
    weekly: DEFAULT_WEEKLY_LIMIT,
  },
  {
    key: "heavy",
    label: "重度",
    description: "高频测试和多模型使用",
    monthly: 800000,
    weekly: 200000,
  },
];

const statusFilters = [
  { label: "全部", value: "" },
  { label: "正常", value: "active" },
  { label: "已禁用", value: "disabled" },
];

export default function Users() {
  const { modal: modalApi, message } = App.useApp();
  const [users, setUsers] = useState<UserListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [size] = useState(20);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [phoneKeyword, setPhoneKeyword] = useState("");
  const [detailVisible, setDetailVisible] = useState(false);
  const [detail, setDetail] = useState<UserDetail | null>(null);
  const [detailQuota, setDetailQuota] = useState<UserQuotaStatus | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);
  const [quotaModalOpen, setQuotaModalOpen] = useState(false);
  const [quotaMode, setQuotaMode] = useState<"single" | "batch">("single");
  const [quotaTarget, setQuotaTarget] = useState<UserListItem | null>(null);
  const [monthlyLimit, setMonthlyLimit] = useState<number | null>(DEFAULT_MONTHLY_LIMIT);
  const [weeklyLimit, setWeeklyLimit] = useState<number | null>(DEFAULT_WEEKLY_LIMIT);
  const [quotaSaving, setQuotaSaving] = useState(false);

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    try {
      const params: ListUsersParams = { page, size };
      if (statusFilter) params.status = statusFilter;
      if (phoneKeyword.trim()) params.phone_keyword = phoneKeyword.trim();
      const quotaParams = statusFilter ? { page, size, status: statusFilter } : { page, size };
      const [usersRes, quotaRes] = await Promise.all([
        usersApi.list(params),
        usersApi.getQuotaOverview(quotaParams),
      ]);
      const quotaMap = new Map(
        quotaRes.data.items.map((item) => [item.user_id, item])
      );
      setUsers(
        usersRes.data.items.map((user) => ({
          ...user,
          quota: quotaMap.get(user.id),
        }))
      );
      setTotal(usersRes.data.total);
    } catch {
      message.error("加载用户列表失败");
    } finally {
      setLoading(false);
    }
  }, [page, size, statusFilter, phoneKeyword, message]);

  useEffect(() => {
    void Promise.resolve().then(fetchUsers);
  }, [fetchUsers]);

  const handleViewDetail = async (userId: string) => {
    setDetailLoading(true);
    setDetailVisible(true);
    setDetail(null);
    setDetailQuota(null);
    try {
      const [detailRes, quotaRes] = await Promise.all([
        usersApi.getDetail(userId),
        usersApi.getQuota(userId),
      ]);
      setDetail(detailRes.data);
      setDetailQuota(quotaRes.data);
    } catch {
      message.error("加载用户详情失败");
    } finally {
      setDetailLoading(false);
    }
  };

  const handleToggleStatus = (record: UserListItem) => {
    const newStatus = record.status === "active" ? "disabled" : "active";
    const action = newStatus === "disabled" ? "禁用" : "启用";
    modalApi.confirm({
      title: `确认${action}`,
      content: `确定要${action}用户 ${record.nickname}（${record.phone}）吗？`,
      icon: <ExclamationCircleOutlined />,
      okText: "确定",
      cancelText: "取消",
      onOk: async () => {
        try {
          await usersApi.updateStatus(record.id, newStatus);
          message.success(`${action}成功`);
          fetchUsers();
          if (detail && detail.id === record.id) {
            const res = await usersApi.getDetail(record.id);
            setDetail(res.data);
          }
        } catch {
          message.error(`${action}失败`);
        }
      },
    });
  };

  const openSingleQuotaModal = (record: UserListItem) => {
    setQuotaMode("single");
    setQuotaTarget(record);
    setMonthlyLimit(record.quota?.monthly_limit ?? DEFAULT_MONTHLY_LIMIT);
    setWeeklyLimit(record.quota?.weekly_limit ?? DEFAULT_WEEKLY_LIMIT);
    setQuotaModalOpen(true);
  };

  const openBatchQuotaModal = () => {
    if (selectedRowKeys.length === 0) {
      message.warning("请先选择用户");
      return;
    }
    setQuotaMode("batch");
    setQuotaTarget(null);
    setMonthlyLimit(DEFAULT_MONTHLY_LIMIT);
    setWeeklyLimit(DEFAULT_WEEKLY_LIMIT);
    setQuotaModalOpen(true);
  };

  const handleRestoreDefaultQuota = () => {
    setMonthlyLimit(null);
    setWeeklyLimit(null);
  };

  const applyQuotaPreset = (preset: (typeof quotaPresets)[number]) => {
    setMonthlyLimit(preset.monthly);
    setWeeklyLimit(preset.weekly);
  };

  const handleSaveQuota = async () => {
    const userIds = quotaMode === "single"
      ? quotaTarget ? [quotaTarget.id] : []
      : selectedRowKeys.map(String);
    if (userIds.length === 0) {
      message.warning("请先选择用户");
      return;
    }
    const effectiveMonthlyLimit = monthlyLimit ?? DEFAULT_MONTHLY_LIMIT;
    const effectiveWeeklyLimit = weeklyLimit ?? DEFAULT_WEEKLY_LIMIT;
    if (effectiveWeeklyLimit > effectiveMonthlyLimit) {
      message.warning("周额度不能大于月额度");
      return;
    }

    setQuotaSaving(true);
    try {
      const payload = {
        token_monthly_limit: monthlyLimit,
        token_weekly_limit: weeklyLimit,
      };
      if (quotaMode === "single") {
        await usersApi.updateQuota(userIds[0], payload);
        message.success("额度已更新");
      } else {
        const res = await usersApi.batchUpdateQuota({ user_ids: userIds, ...payload });
        message.success(`已更新 ${res.data.updated_count} 个用户`);
        setSelectedRowKeys([]);
      }
      setQuotaModalOpen(false);
      await fetchUsers();
      if (detail && userIds.includes(detail.id)) {
        const quotaRes = await usersApi.getQuota(detail.id);
        setDetailQuota(quotaRes.data);
      }
    } catch {
      message.error("额度更新失败");
    } finally {
      setQuotaSaving(false);
    }
  };

  const activeCount = users.filter((u) => u.status === "active").length;
  const disabledCount = users.filter((u) => u.status === "disabled").length;

  const getQuotaStatus = (percent: number) => {
    if (percent >= 1) return "exception";
    if (percent >= 0.8) return "exception";
    if (percent >= 0.6) return "active";
    return "success";
  };

  const renderQuotaProgress = (
    quota: UserQuotaOverviewItem | undefined,
    usageKey: "monthly_usage" | "weekly_usage",
    limitKey: "monthly_limit" | "weekly_limit",
    percentKey: "monthly_percent" | "weekly_percent"
  ) => {
    if (!quota) return "-";
    const percent = Math.round(quota[percentKey] * 100);
    return (
      <div style={{ minWidth: 150 }}>
        <Progress
          percent={Math.min(100, percent)}
          size="small"
          status={getQuotaStatus(quota[percentKey])}
        />
        <div style={{ color: TEXT_SECONDARY, fontSize: 12 }}>
          {quota[usageKey].toLocaleString()} / {quota[limitKey].toLocaleString()}
        </div>
      </div>
    );
  };

  const columns: ColumnsType<UserListItem> = [
    {
      title: "手机号",
      dataIndex: "phone",
      key: "phone",
      width: 140,
    },
    {
      title: "昵称",
      dataIndex: "nickname",
      key: "nickname",
      width: 120,
    },
    {
      title: "角色",
      dataIndex: "role",
      key: "role",
      width: 80,
      render: (role: string) => (
        <Tag color={role === "admin" ? "orange" : "blue"}>
          {role === "admin" ? "管理员" : "用户"}
        </Tag>
      ),
    },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      width: 80,
      render: (status: string) => (
        <Tag color={status === "active" ? "green" : "red"}>
          {status === "active" ? "正常" : "已禁用"}
        </Tag>
      ),
    },
    {
      title: "农场名",
      dataIndex: "farm_name",
      key: "farm_name",
      width: 140,
      render: (text: string | null) => text || "-",
    },
    {
      title: "月用量/月限额",
      key: "monthly_quota",
      width: 180,
      render: (_: unknown, record: UserListItem) =>
        renderQuotaProgress(record.quota, "monthly_usage", "monthly_limit", "monthly_percent"),
    },
    {
      title: "周用量/周限额",
      key: "weekly_quota",
      width: 180,
      render: (_: unknown, record: UserListItem) =>
        renderQuotaProgress(record.quota, "weekly_usage", "weekly_limit", "weekly_percent"),
    },
    {
      title: "注册时间",
      dataIndex: "created_at",
      key: "created_at",
      width: 180,
      render: (text: string) => new Date(text).toLocaleString("zh-CN"),
    },
    {
      title: "操作",
      key: "action",
      width: 220,
      render: (_: unknown, record: UserListItem) => (
        <Space>
          <Button type="link" size="small" onClick={() => handleViewDetail(record.id)}>
            详情
          </Button>
          <Button type="link" size="small" onClick={() => openSingleQuotaModal(record)}>
            设置额度
          </Button>
          <Button
            type="link"
            size="small"
            danger={record.status === "active"}
            onClick={() => handleToggleStatus(record)}
          >
            {record.status === "active" ? "禁用" : "启用"}
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <PageShell
      title="用户管理"
      description="查看账号状态、农场信息和 Token 配额，支持单人或批量调整额度。"
    >
      <Row gutter={16} style={{ marginBottom: 20 }}>
        <Col xs={24} sm={12} lg={6}>
          <MetricCard>
            <Statistic
              title={<span style={{ color: TEXT_SECONDARY }}>总用户</span>}
              value={total}
              prefix={<TeamOutlined />}
              valueStyle={{ color: ACCENT }}
            />
          </MetricCard>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <MetricCard accent={palette.success}>
            <Statistic
              title={<span style={{ color: TEXT_SECONDARY }}>当前页活跃</span>}
              value={activeCount}
              prefix={<CheckCircleOutlined />}
              valueStyle={{ color: "#3fb950" }}
            />
          </MetricCard>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <MetricCard accent={palette.danger}>
            <Statistic
              title={<span style={{ color: TEXT_SECONDARY }}>当前页禁用</span>}
              value={disabledCount}
              prefix={<StopOutlined />}
              valueStyle={{ color: "#f85149" }}
            />
          </MetricCard>
        </Col>
      </Row>

      <Toolbar
        left={(
          <>
            <Select
              value={statusFilter || undefined}
              onChange={(v) => {
                setStatusFilter(v);
                setPage(1);
              }}
              style={{ width: 140 }}
              options={statusFilters.map((f) => ({ label: f.label, value: f.value }))}
              placeholder="状态筛选"
              allowClear
            />
            <Input.Search
              placeholder="搜索手机号"
              style={{ width: 220 }}
              onSearch={(v) => {
                setPhoneKeyword(v);
                setPage(1);
              }}
              allowClear
              onClear={() => {
                setPhoneKeyword("");
                setPage(1);
              }}
            />
          </>
        )}
        right={(
          <Button
            icon={<SettingOutlined />}
            disabled={selectedRowKeys.length === 0}
            onClick={openBatchQuotaModal}
          >
            批量设置额度{selectedRowKeys.length ? `（${selectedRowKeys.length}）` : ""}
          </Button>
        )}
      />

      <Table<UserListItem>
        columns={columns}
        dataSource={users}
        rowKey="id"
        rowSelection={{
          selectedRowKeys,
          onChange: setSelectedRowKeys,
        }}
        loading={loading}
        pagination={{
          current: page,
          pageSize: size,
          total,
          showSizeChanger: false,
          showTotal: (count) => `共 ${count} 个用户`,
          onChange: (p) => setPage(p),
        }}
        scroll={{ x: 1180 }}
        style={{ background: BG_CARD, borderRadius: 8 }}
      />

      <Modal
        title={quotaMode === "single" ? "设置用户额度" : "批量设置额度"}
        open={quotaModalOpen}
        onCancel={() => setQuotaModalOpen(false)}
        onOk={handleSaveQuota}
        confirmLoading={quotaSaving}
        okText="保存"
        cancelText="取消"
        width={520}
      >
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          <div style={{ color: TEXT_SECONDARY }}>
            {quotaMode === "single" && quotaTarget
              ? `当前用户：${quotaTarget.nickname}（${quotaTarget.phone}）`
              : `将更新 ${selectedRowKeys.length} 个已选用户`}
          </div>
          <div>
            <div style={{ marginBottom: 8 }}>额度档位</div>
            <Row gutter={10}>
              {quotaPresets.map((preset) => {
                const active = monthlyLimit === preset.monthly && weeklyLimit === preset.weekly;
                return (
                  <Col span={8} key={preset.key}>
                    <button
                      type="button"
                      onClick={() => applyQuotaPreset(preset)}
                      style={{
                        width: "100%",
                        minHeight: 92,
                        padding: "10px 12px",
                        textAlign: "left",
                        cursor: "pointer",
                        color: active ? "#e6edf3" : TEXT_SECONDARY,
                        background: active ? "rgba(47,129,247,0.16)" : palette.bgElevated,
                        border: `1px solid ${active ? ACCENT : BORDER}`,
                        borderRadius: 8,
                      }}
                    >
                      <div style={{ color: active ? ACCENT : "#e6edf3", fontWeight: 700 }}>
                        {preset.label}
                      </div>
                      <div style={{ fontSize: 12, marginTop: 4 }}>{preset.description}</div>
                      <div style={{ fontSize: 12, marginTop: 8 }}>
                        月 {preset.monthly.toLocaleString()}
                      </div>
                      <div style={{ fontSize: 12 }}>周 {preset.weekly.toLocaleString()}</div>
                    </button>
                  </Col>
                );
              })}
            </Row>
          </div>
          <div>
            <div style={{ marginBottom: 8 }}>月 Token 额度</div>
            <InputNumber
              min={0}
              precision={0}
              value={monthlyLimit}
              placeholder="输入自定义月额度"
              style={{ width: "100%" }}
              formatter={(value) => `${value}`.replace(/\B(?=(\d{3})+(?!\d))/g, ",")}
              parser={(value) => Number(value?.replace(/,/g, "") || 0)}
              onChange={(value) => setMonthlyLimit(value)}
            />
          </div>
          <div>
            <div style={{ marginBottom: 8 }}>周 Token 额度</div>
            <InputNumber
              min={0}
              precision={0}
              value={weeklyLimit}
              placeholder="输入自定义周额度"
              style={{ width: "100%" }}
              formatter={(value) => `${value}`.replace(/\B(?=(\d{3})+(?!\d))/g, ",")}
              parser={(value) => Number(value?.replace(/,/g, "") || 0)}
              onChange={(value) => setWeeklyLimit(value)}
            />
          </div>
          <Space>
            <Button onClick={handleRestoreDefaultQuota}>恢复标准默认</Button>
            <span style={{ color: TEXT_SECONDARY, fontSize: 12 }}>
              默认按标准档后端配置生效；填 0 表示禁止使用，也可手动输入自定义额度。
            </span>
          </Space>
        </Space>
      </Modal>

      <Modal
        title="用户详情"
        open={detailVisible}
        onCancel={() => setDetailVisible(false)}
        footer={null}
        width={520}
      >
        {detailLoading ? (
          <div style={{ textAlign: "center", padding: 40, color: TEXT_SECONDARY }}>
            加载中...
          </div>
        ) : detail ? (
          <Descriptions column={1} bordered size="small">
            <Descriptions.Item label="ID">{detail.id}</Descriptions.Item>
            <Descriptions.Item label="手机号">{detail.phone}</Descriptions.Item>
            <Descriptions.Item label="昵称">{detail.nickname}</Descriptions.Item>
            <Descriptions.Item label="角色">
              <Tag color={detail.role === "admin" ? "orange" : "blue"}>
                {detail.role === "admin" ? "管理员" : "用户"}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color={detail.status === "active" ? "green" : "red"}>
                {detail.status === "active" ? "正常" : "已禁用"}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="注册时间">
              {new Date(detail.created_at).toLocaleString("zh-CN")}
            </Descriptions.Item>
            <Descriptions.Item label="农场名">
              {detail.farm_name || "-"}
            </Descriptions.Item>
            <Descriptions.Item label="农场位置">
              {detail.farm_location || "-"}
            </Descriptions.Item>
            {detailQuota && (
              <>
                <Descriptions.Item label="月限额">
                  {detailQuota.monthly_limit.toLocaleString()}
                </Descriptions.Item>
                <Descriptions.Item label="月已用">
                  {detailQuota.monthly_usage.toLocaleString()}
                </Descriptions.Item>
                <Descriptions.Item label="月剩余">
                  {detailQuota.monthly_remaining.toLocaleString()}
                </Descriptions.Item>
                <Descriptions.Item label="月周期">
                  {detailQuota.monthly_start} 至 {detailQuota.monthly_end}
                </Descriptions.Item>
                <Descriptions.Item label="周限额">
                  {detailQuota.weekly_limit.toLocaleString()}
                </Descriptions.Item>
                <Descriptions.Item label="周已用">
                  {detailQuota.weekly_usage.toLocaleString()}
                </Descriptions.Item>
                <Descriptions.Item label="周剩余">
                  {detailQuota.weekly_remaining.toLocaleString()}
                </Descriptions.Item>
                <Descriptions.Item label="周周期">
                  {detailQuota.weekly_start} 至 {detailQuota.weekly_end}
                </Descriptions.Item>
                <Descriptions.Item label="配额状态">
                  <Tag color={detailQuota.status === "exceeded" ? "red" : detailQuota.status === "warning" ? "orange" : "green"}>
                    {detailQuota.status}
                  </Tag>
                </Descriptions.Item>
              </>
            )}
          </Descriptions>
        ) : null}
        {detail && (
          <div style={{ marginTop: 16, textAlign: "right" }}>
            <Button
              danger={detail.status === "active"}
              type={detail.status === "active" ? "primary" : "default"}
              onClick={() => {
                handleToggleStatus({
                  id: detail.id,
                  nickname: detail.nickname,
                  phone: detail.phone,
                  status: detail.status,
                } as UserListItem);
              }}
            >
              {detail.status === "active" ? "禁用用户" : "启用用户"}
            </Button>
          </div>
        )}
      </Modal>
    </PageShell>
  );
}
