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
  message,
  Statistic,
  Progress,
  Row,
  Col,
  Card,
} from "antd";
import {
  TeamOutlined,
  StopOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
} from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import {
  usersApi,
  type UserListItem,
  type UserDetail,
  type ListUsersParams,
  type UserQuotaStatus,
  type UserQuotaOverviewItem,
} from "../../api/users";

const BG_SECONDARY = "#161b22";
const BG_CARD = "#21262d";
const BORDER = "#30363d";
const TEXT_SECONDARY = "#8b949e";
const ACCENT = "#58a6ff";

const statusFilters = [
  { label: "全部", value: "" },
  { label: "正常", value: "active" },
  { label: "已禁用", value: "disabled" },
];

export default function Users() {
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
  }, [page, size, statusFilter, phoneKeyword]);

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
    Modal.confirm({
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
      width: 160,
      render: (_: unknown, record: UserListItem) => (
        <Space>
          <Button type="link" size="small" onClick={() => handleViewDetail(record.id)}>
            详情
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
    <div>
      <Row gutter={16} style={{ marginBottom: 20 }}>
        <Col span={6}>
          <Card
            style={{ background: BG_SECONDARY, borderColor: BORDER }}
            styles={{ body: { padding: "16px 24px" } }}
          >
            <Statistic
              title={<span style={{ color: TEXT_SECONDARY }}>总用户</span>}
              value={total}
              prefix={<TeamOutlined />}
              valueStyle={{ color: ACCENT }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card
            style={{ background: BG_SECONDARY, borderColor: BORDER }}
            styles={{ body: { padding: "16px 24px" } }}
          >
            <Statistic
              title={<span style={{ color: TEXT_SECONDARY }}>当前页活跃</span>}
              value={activeCount}
              prefix={<CheckCircleOutlined />}
              valueStyle={{ color: "#3fb950" }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card
            style={{ background: BG_SECONDARY, borderColor: BORDER }}
            styles={{ body: { padding: "16px 24px" } }}
          >
            <Statistic
              title={<span style={{ color: TEXT_SECONDARY }}>当前页禁用</span>}
              value={disabledCount}
              prefix={<StopOutlined />}
              valueStyle={{ color: "#f85149" }}
            />
          </Card>
        </Col>
      </Row>

      <Space style={{ marginBottom: 16 }}>
        <Select
          value={statusFilter || undefined}
          onChange={(v) => {
            setStatusFilter(v);
            setPage(1);
          }}
          style={{ width: 120 }}
          options={statusFilters.map((f) => ({ label: f.label, value: f.value }))}
          placeholder="状态筛选"
          allowClear
        />
        <Input.Search
          placeholder="搜索手机号"
          style={{ width: 200 }}
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
      </Space>

      <Table<UserListItem>
        columns={columns}
        dataSource={users}
        rowKey="id"
        loading={loading}
        pagination={{
          current: page,
          pageSize: size,
          total,
          showSizeChanger: false,
          onChange: (p) => setPage(p),
        }}
        style={{ background: BG_CARD, borderRadius: 8 }}
      />

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
    </div>
  );
}
