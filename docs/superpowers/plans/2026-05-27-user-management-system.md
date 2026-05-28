# User Management System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 接入多用户认证体系 — 后端 admin 用户管理 API、admin-web 用户管理页面、App 端登录/注册/个人中心。

**Architecture:** 三个独立子系统。后端新增 `require_admin` 依赖 + `admin_users` 路由模块；admin-web 新增 `api/users.ts` + `pages/Users/`；App 端新增 `authStore`（Zustand + AsyncStorage）+ 登录/注册页面 + 导航守卫。

**Tech Stack:** FastAPI + SQLAlchemy (backend), React 19 + Ant Design 5 + Axios (admin-web), React Native 0.74 + Zustand + Axios (mobile)

**Prerequisite:** 后端 `storage-redesign-multi-user` 已完成（users 表、JWT、auth API 已就绪）。

---

## File Structure

```
PHASE 1: Backend
├── app/api/deps.py                  # MODIFY: 新增 require_admin 依赖
├── app/schemas/admin_user.py        # CREATE: admin 用户管理 schemas
├── app/api/admin_users.py           # CREATE: admin 用户管理路由
├── app/main.py                      # MODIFY: 注册 admin_users router
└── tests/api/test_admin_users.py    # CREATE: 集成测试

PHASE 2: admin-web
├── src/api/users.ts                 # CREATE: 用户管理 API 模块
├── src/pages/Users/index.tsx        # CREATE: 用户列表页面 + 详情弹窗
├── src/layouts/AdminLayout.tsx       # MODIFY: 添加"用户管理"导航项
└── src/App.tsx                       # MODIFY: 添加 /users 路由

PHASE 3: FarmManagerMobile
├── src/api/types.ts                  # MODIFY: 新增 auth 相关类型
├── src/stores/authStore.ts           # CREATE: 认证状态管理
├── src/api/client.ts                 # MODIFY: token 注入 + 401 处理
├── src/screens/auth/LoginScreen.tsx  # CREATE: 登录页
├── src/screens/auth/RegisterScreen.tsx # CREATE: 注册页
├── src/navigation/AppNavigator.tsx   # MODIFY: auth 守卫 + 新增路由
└── src/screens/settings/SettingsScreen.tsx # MODIFY: profile + logout
```

---

## Phase 1: Backend — Admin 用户管理 API

### Task 1: 添加 require_admin 依赖

**Files:**
- Modify: `backend/app/api/deps.py`

- [ ] **Step 1: 在 deps.py 末尾添加 require_admin 依赖函数**

在 `backend/app/api/deps.py` 文件末尾（`verify_resource_owner` 函数之后）添加：

```python
def require_admin(user: User = Depends(get_current_user)) -> User:
    """Layer 0: 校验当前用户是否为管理员。"""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user
```

- [ ] **Step 2: 验证 deps.py 语法正确**

Run: `cd backend && python -c "from app.api.deps import require_admin; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/deps.py
git commit -m "feat: add require_admin dependency to deps.py"
```

---

### Task 2: 创建 Admin 用户管理 Schemas

**Files:**
- Create: `backend/app/schemas/admin_user.py`

- [ ] **Step 1: 创建 schema 文件**

创建 `backend/app/schemas/admin_user.py`：

```python
"""Admin 用户管理 Schema。"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import PaginatedResponse


class AdminUserListItem(BaseModel):
    """用户列表项（含农场名）。"""

    id: str
    phone: str
    nickname: str
    avatar_url: str | None = None
    role: str
    status: str
    created_at: datetime
    farm_name: str | None = None

    model_config = {"from_attributes": True}


class AdminUserListResponse(PaginatedResponse[AdminUserListItem]):
    """用户列表分页响应。"""

    pass


class AdminUserDetailResponse(BaseModel):
    """用户详情（含农场信息）。"""

    id: str
    phone: str
    nickname: str
    avatar_url: str | None = None
    role: str
    status: str
    created_at: datetime
    farm_id: int | None = None
    farm_name: str | None = None
    farm_location: str | None = None

    model_config = {"from_attributes": True}


class UpdateUserStatusRequest(BaseModel):
    """修改用户状态请求。"""

    status: str = Field(..., pattern="^(active|disabled)$")


class UpdateUserStatusResponse(BaseModel):
    """修改用户状态响应。"""

    id: str
    status: str

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: 验证 schema 导入**

Run: `cd backend && python -c "from app.schemas.admin_user import AdminUserListResponse, AdminUserDetailResponse, UpdateUserStatusRequest; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/admin_user.py
git commit -m "feat: add admin user management schemas"
```

---

### Task 3: 创建 Admin 用户管理路由

**Files:**
- Create: `backend/app/api/admin_users.py`

- [ ] **Step 1: 创建路由文件**

创建 `backend/app/api/admin_users.py`：

```python
"""Admin 用户管理 API — 列表、详情、状态管理。"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin
from app.models.farm import Farm
from app.models.user import User
from app.schemas.admin_user import (
    AdminUserDetailResponse,
    AdminUserListItem,
    AdminUserListResponse,
    UpdateUserStatusRequest,
    UpdateUserStatusResponse,
)

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


@router.get("", response_model=AdminUserListResponse)
def list_users(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None, description="按状态筛选: active/disabled"),
    phone_keyword: str | None = Query(None, description="手机号模糊搜索"),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> AdminUserListResponse:
    """查询用户列表（分页、筛选）。"""
    query = db.query(User, Farm.name.label("farm_name")).outerjoin(
        Farm, Farm.user_id == User.id
    )

    if status:
        query = query.filter(User.status == status)
    if phone_keyword:
        query = query.filter(User.phone.contains(phone_keyword))

    total = query.count()
    rows = (
        query.order_by(User.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )

    items = [
        AdminUserListItem(
            id=user.id,
            phone=user.phone,
            nickname=user.nickname,
            avatar_url=user.avatar_url,
            role=user.role,
            status=user.status,
            created_at=user.created_at,
            farm_name=farm_name,
        )
        for user, farm_name in rows
    ]

    return AdminUserListResponse(items=items, total=total)


@router.get("/{user_id}", response_model=AdminUserDetailResponse)
def get_user_detail(
    user_id: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> AdminUserDetailResponse:
    """获取用户详情（含农场信息）。"""
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    farm = db.query(Farm).filter(Farm.user_id == user.id).first()

    return AdminUserDetailResponse(
        id=user.id,
        phone=user.phone,
        nickname=user.nickname,
        avatar_url=user.avatar_url,
        role=user.role,
        status=user.status,
        created_at=user.created_at,
        farm_id=farm.id if farm else None,
        farm_name=farm.name if farm else None,
        farm_location=farm.location if farm else None,
    )


@router.put("/{user_id}/status", response_model=UpdateUserStatusResponse)
def update_user_status(
    user_id: str,
    req: UpdateUserStatusRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> UpdateUserStatusResponse:
    """修改用户状态（禁用/启用）。"""
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    if user.role == "admin":
        raise HTTPException(status_code=400, detail="不能修改管理员状态")

    user.status = req.status
    db.commit()

    return UpdateUserStatusResponse(id=user.id, status=user.status)
```

- [ ] **Step 2: 在 main.py 注册路由**

在 `backend/app/main.py` 中：

a) 在 import 区块（第 20-36 行）添加 `admin_users` 的导入：

```python
from app.api import (
    admin,
    admin_config,
    admin_stats,
    admin_trace,
    admin_users,
    agent,
    auth,
    cost,
    cost_categories,
    crop,
    cycle,
    debt,
    feedback,
    log,
    user_settings,
    weather,
)
```

b) 在路由注册区（`app.include_router(feedback.router)` 之后）添加：

```python
app.include_router(admin_users.router)
```

- [ ] **Step 3: 验证路由注册**

Run: `cd backend && python -c "from app.main import app; routes = [r.path for r in app.routes]; print([r for r in routes if 'admin' in r])"`
Expected: 输出包含 `/admin/users`, `/admin/users/{user_id}`, `/admin/users/{user_id}/status`

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/admin_users.py backend/app/main.py
git commit -m "feat: add admin user management API routes"
```

---

### Task 4: 后端集成测试

**Files:**
- Create: `backend/tests/api/test_admin_users.py`
- Modify: `backend/tests/conftest.py`

- [ ] **Step 1: 在 conftest.py 添加 admin 用户 fixture**

在 `backend/tests/conftest.py` 末尾（`auth_headers` fixture 之后）添加：

```python
@pytest.fixture()
def admin_user(db):
    """创建管理员用户。"""
    admin = User(
        id="test-admin-001",
        phone="99999999999",
        password_hash="h",
        nickname="管理员",
        role="admin",
        status="active",
    )
    db.add(admin)
    db.commit()
    return admin


@pytest.fixture()
def admin_headers(admin_user):
    """管理员 JWT 请求头。"""
    token = create_access_token(user_id=admin_user.id)
    return {"Authorization": f"Bearer {token}"}
```

注意：`admin_user` fixture 不用 `autouse`，需要显式引用才会创建。但 `clean_db` 是 `autouse=True` 的，会在每个测试前重建表。`admin_user` fixture 需要在 `clean_db` 之后执行。由于 `clean_db` yield 后才结束，而 `admin_user` 通过参数 `db` 依赖于 `get_db`（不是 fixture），所以需要在函数体内直接创建。

修正 `admin_user` fixture（不依赖 db 参数，因为 clean_db 已经重建了表）：

```python
@pytest.fixture()
def admin_user():
    """创建管理员用户。"""
    db = SessionLocal()
    admin = User(
        id="test-admin-001",
        phone="99999999999",
        password_hash="h",
        nickname="管理员",
        role="admin",
        status="active",
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    db.close()
    return admin


@pytest.fixture()
def admin_headers(admin_user):
    """管理员 JWT 请求头。"""
    token = create_access_token(user_id=admin_user.id)
    return {"Authorization": f"Bearer {token}"}
```

- [ ] **Step 2: 创建测试文件**

创建 `backend/tests/api/test_admin_users.py`：

```python
"""Admin 用户管理 API 集成测试。"""

from app.core.security import create_access_token
from app.models.farm import Farm
from app.models.user import User


def test_list_users_empty(client, admin_headers):
    """管理员查询空用户列表。"""
    resp = client.get("/admin/users", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data


def test_list_users_with_data(client, admin_headers, admin_user):
    """管理员查询用户列表，包含管理员自己和普通用户。"""
    db_resp = client.get("/admin/users", headers=admin_headers)
    assert db_resp.status_code == 200
    data = db_resp.json()
    assert data["total"] >= 1
    assert any(u["phone"] == "99999999999" for u in data["items"])


def test_list_users_filter_by_status(client, admin_headers, admin_user):
    """按状态筛选用户。"""
    resp = client.get("/admin/users?status=active", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert all(u["status"] == "active" for u in data["items"])


def test_list_users_search_phone(client, admin_headers, admin_user):
    """按手机号模糊搜索。"""
    resp = client.get("/admin/users?phone_keyword=9999", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert any("9999" in u["phone"] for u in data["items"])


def test_list_users_pagination(client, admin_headers, admin_user):
    """分页查询。"""
    resp = client.get("/admin/users?page=1&size=1", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) <= 1


def test_get_user_detail(client, admin_headers, admin_user):
    """获取用户详情。"""
    resp = client.get(f"/admin/users/{admin_user.id}", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == admin_user.id
    assert data["phone"] == "99999999999"
    assert "farm_id" in data
    assert "farm_name" in data


def test_get_user_detail_not_found(client, admin_headers):
    """查询不存在的用户。"""
    resp = client.get("/admin/users/nonexistent-id", headers=admin_headers)
    assert resp.status_code == 404


def test_update_user_status_disable(client, admin_headers, admin_user):
    """禁用用户。"""
    target_id = "test-user-001"
    resp = client.put(
        f"/admin/users/{target_id}/status",
        json={"status": "disabled"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "disabled"


def test_update_user_status_enable(client, admin_headers, admin_user):
    """启用用户。"""
    target_id = "test-user-001"
    client.put(
        f"/admin/users/{target_id}/status",
        json={"status": "disabled"},
        headers=admin_headers,
    )
    resp = client.put(
        f"/admin/users/{target_id}/status",
        json={"status": "active"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"


def test_update_admin_status_forbidden(client, admin_headers, admin_user):
    """不能修改管理员状态。"""
    resp = client.put(
        f"/admin/users/{admin_user.id}/status",
        json={"status": "disabled"},
        headers=admin_headers,
    )
    assert resp.status_code == 400


def test_non_admin_forbidden(client, auth_headers):
    """普通用户访问 admin 接口返回 403。"""
    resp = client.get("/admin/users", headers=auth_headers)
    assert resp.status_code == 403


def test_no_auth_returns_401(client):
    """未认证访问返回 401。"""
    resp = client.get("/admin/users")
    assert resp.status_code == 401
```

- [ ] **Step 3: 运行测试**

Run: `cd backend && python -m pytest tests/api/test_admin_users.py -v`
Expected: 所有 11 个测试 PASS

- [ ] **Step 4: 运行全量测试确保无回归**

Run: `cd backend && python -m pytest -x -q`
Expected: 所有测试 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tests/api/test_admin_users.py backend/tests/conftest.py
git commit -m "test: add admin user management API integration tests"
```

---

## Phase 2: admin-web — 用户管理页面

### Task 5: 创建用户管理 API 模块

**Files:**
- Create: `admin-web/src/api/users.ts`

- [ ] **Step 1: 创建 API 模块**

创建 `admin-web/src/api/users.ts`：

```typescript
import apiClient from "./client";

export interface UserListItem {
  id: string;
  phone: string;
  nickname: string;
  avatar_url: string | null;
  role: string;
  status: string;
  created_at: string;
  farm_name: string | null;
}

export interface UserListResponse {
  items: UserListItem[];
  total: number;
}

export interface UserDetail extends UserListItem {
  farm_id: number | null;
  farm_location: string | null;
}

export interface ListUsersParams {
  page?: number;
  size?: number;
  status?: string;
  phone_keyword?: string;
}

export const usersApi = {
  list: (params?: ListUsersParams) =>
    apiClient.get<UserListResponse>("/admin/users", { params }),

  getDetail: (userId: string) =>
    apiClient.get<UserDetail>(`/admin/users/${userId}`),

  updateStatus: (userId: string, status: string) =>
    apiClient.put(`/admin/users/${userId}/status`, { status }),
};
```

- [ ] **Step 2: 验证 TypeScript 编译**

Run: `cd admin-web && npx tsc --noEmit 2>&1 | head -20`
Expected: 无错误（或仅有已存在的错误）

- [ ] **Step 3: Commit**

```bash
git add admin-web/src/api/users.ts
git commit -m "feat(admin-web): add users API module"
```

---

### Task 6: 创建用户列表页面 + 详情弹窗

**Files:**
- Create: `admin-web/src/pages/Users/index.tsx`

- [ ] **Step 1: 创建页面组件**

创建 `admin-web/src/pages/Users/index.tsx`：

```tsx
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
  Row,
  Col,
  Card,
} from "antd";
import {
  TeamOutlined,
  UserOutlined,
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
} from "../../api/users";

const BG_PRIMARY = "#0d1117";
const BG_SECONDARY = "#161b22";
const BG_CARD = "#21262d";
const BORDER = "#30363d";
const TEXT_PRIMARY = "#c9d1d9";
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
  const [detailLoading, setDetailLoading] = useState(false);

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    try {
      const params: ListUsersParams = { page, size };
      if (statusFilter) params.status = statusFilter;
      if (phoneKeyword.trim()) params.phone_keyword = phoneKeyword.trim();
      const res = await usersApi.list(params);
      setUsers(res.data.items);
      setTotal(res.data.total);
    } catch {
      message.error("加载用户列表失败");
    } finally {
      setLoading(false);
    }
  }, [page, size, statusFilter, phoneKeyword]);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  const handleViewDetail = async (userId: string) => {
    setDetailLoading(true);
    setDetailVisible(true);
    try {
      const res = await usersApi.getDetail(userId);
      setDetail(res.data);
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
```

- [ ] **Step 2: 验证 TypeScript 编译**

Run: `cd admin-web && npx tsc --noEmit 2>&1 | head -20`
Expected: 无新增错误

- [ ] **Step 3: Commit**

```bash
git add admin-web/src/pages/Users/index.tsx
git commit -m "feat(admin-web): add users list page with detail modal"
```

---

### Task 7: 更新导航和路由

**Files:**
- Modify: `admin-web/src/layouts/AdminLayout.tsx`
- Modify: `admin-web/src/App.tsx`

- [ ] **Step 1: 在 AdminLayout.tsx 添加导航项**

在 `admin-web/src/layouts/AdminLayout.tsx` 中：

a) 在 icons 导入中添加 `TeamOutlined`：

```typescript
import {
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  BranchesOutlined,
  BarChartOutlined,
  MessageOutlined,
  AppstoreOutlined,
  FileSearchOutlined,
  SettingOutlined,
  TeamOutlined,
} from '@ant-design/icons';
```

b) 在 `menuItems` 数组中，在第一项之前添加用户管理：

```typescript
const menuItems = [
  { key: '/users', icon: <TeamOutlined />, label: '用户管理' },
  { key: '/dev/traces', icon: <BranchesOutlined />, label: '链路追踪' },
  { key: '/dev/tokens', icon: <BarChartOutlined />, label: 'Token 看板' },
  { key: '/dev/playground', icon: <MessageOutlined />, label: 'Playground' },
  { key: '/dev/skills', icon: <AppstoreOutlined />, label: 'Skill 注册表' },
  { key: '/dev/prompts', icon: <FileSearchOutlined />, label: 'Prompt 检查器' },
  { key: '/dev/config', icon: <SettingOutlined />, label: '配置管理' },
];
```

c) 在 `pageTitles` 对象中添加：

```typescript
const pageTitles: Record<string, string> = {
  '/users': '用户管理',
  '/dev/traces': '链路追踪',
  '/dev/tokens': 'Token 看板',
  '/dev/playground': 'Playground',
  '/dev/skills': 'Skill 注册表',
  '/dev/prompts': 'Prompt 检查器',
  '/dev/config': '配置管理',
};
```

- [ ] **Step 2: 在 App.tsx 添加路由**

在 `admin-web/src/App.tsx` 中：

a) 添加 Users 页面导入：

```typescript
import Users from './pages/Users';
```

b) 在 Routes 中添加（在 `<Route path="/" .../>` 之后）：

```tsx
<Route path="/users" element={<Users />} />
```

- [ ] **Step 3: 验证编译**

Run: `cd admin-web && npx tsc --noEmit 2>&1 | head -20`
Expected: 无新增错误

- [ ] **Step 4: 手动验证**

Run: `cd admin-web && npm run dev`

在浏览器打开 admin-web，验证：
1. 左侧导航出现"用户管理"菜单项
2. 点击后跳转到 `/users`
3. 页面正确渲染（表格、筛选、搜索）
4. 默认页改为 `/users` 或保持 `/dev/traces`

- [ ] **Step 5: Commit**

```bash
git add admin-web/src/layouts/AdminLayout.tsx admin-web/src/App.tsx
git commit -m "feat(admin-web): add user management navigation and routing"
```

---

## Phase 3: FarmManagerMobile — 认证接入

### Task 8: 创建 Auth 类型定义

**Files:**
- Modify: `FarmManagerMobile/src/api/types.ts`

- [ ] **Step 1: 在 types.ts 末尾添加 auth 相关类型**

在 `FarmManagerMobile/src/api/types.ts` 文件末尾添加：

```typescript
export interface UserProfile {
  id: string;
  phone: string;
  nickname: string;
  avatar_url: string | null;
  role: string;
  status: string;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: UserProfile;
}

export interface LoginParams {
  phone: string;
  password: string;
}

export interface RegisterParams {
  phone: string;
  password: string;
  nickname?: string;
}

export interface UpdateProfileParams {
  nickname?: string;
  avatar_url?: string;
}
```

- [ ] **Step 2: 验证 TypeScript**

Run: `cd FarmManagerMobile && npx tsc --noEmit 2>&1 | head -20`
Expected: 无新增错误

- [ ] **Step 3: Commit**

```bash
git add FarmManagerMobile/src/api/types.ts
git commit -m "feat(mobile): add auth type definitions"
```

---

### Task 9: 创建 Auth Store

**Files:**
- Create: `FarmManagerMobile/src/stores/authStore.ts`

- [ ] **Step 1: 创建 auth store**

创建 `FarmManagerMobile/src/stores/authStore.ts`：

```typescript
import AsyncStorage from '@react-native-async-storage/async-storage';
import { create } from 'zustand';
import { apiClient } from '../api/client';
import type {
  UserProfile,
  LoginParams,
  RegisterParams,
  TokenResponse,
  UpdateProfileParams,
} from '../api/types';

const TOKEN_KEY = 'farm_manager_auth_token';

interface AuthState {
  token: string | null;
  user: UserProfile | null;
  isLoggedIn: boolean;
  isInitializing: boolean;
  login: (params: LoginParams) => Promise<void>;
  register: (params: RegisterParams) => Promise<void>;
  logout: () => Promise<void>;
  updateProfile: (params: UpdateProfileParams) => Promise<void>;
  initialize: () => Promise<void>;
  setToken: (token: string) => Promise<void>;
}

let onUnauthorizedCallback: (() => void) | null = null;

export const setOnUnauthorized = (cb: () => void) => {
  onUnauthorizedCallback = cb;
};

export const triggerUnauthorized = () => {
  onUnauthorizedCallback?.();
};

export const useAuthStore = create<AuthState>((set, get) => ({
  token: null,
  user: null,
  isLoggedIn: false,
  isInitializing: true,

  setToken: async (token: string) => {
    await AsyncStorage.setItem(TOKEN_KEY, token);
    set({ token });
  },

  login: async (params: LoginParams) => {
    const res = await apiClient.post<TokenResponse>('/auth/login', params);
    const { access_token, user } = res.data;
    await AsyncStorage.setItem(TOKEN_KEY, access_token);
    set({ token: access_token, user, isLoggedIn: true });
  },

  register: async (params: RegisterParams) => {
    const res = await apiClient.post<TokenResponse>('/auth/register', params);
    const { access_token, user } = res.data;
    await AsyncStorage.setItem(TOKEN_KEY, access_token);
    set({ token: access_token, user, isLoggedIn: true });
  },

  logout: async () => {
    await AsyncStorage.removeItem(TOKEN_KEY);
    set({ token: null, user: null, isLoggedIn: false });
  },

  updateProfile: async (params: UpdateProfileParams) => {
    const res = await apiClient.post<TokenResponse>('/auth/me', params);
    const user = res.data as unknown as UserProfile;
    set({ user });
  },

  initialize: async () => {
    set({ isInitializing: true });
    try {
      const token = await AsyncStorage.getItem(TOKEN_KEY);
      if (!token) {
        set({ isLoggedIn: false, isInitializing: false });
        return;
      }
      set({ token });
      const res = await apiClient.get<UserProfile>('/auth/me');
      set({ user: res.data, isLoggedIn: true, isInitializing: false });
    } catch {
      await AsyncStorage.removeItem(TOKEN_KEY);
      set({ token: null, user: null, isLoggedIn: false, isInitializing: false });
    }
  },
}));
```

- [ ] **Step 2: 验证 TypeScript**

Run: `cd FarmManagerMobile && npx tsc --noEmit 2>&1 | head -20`
Expected: 无新增错误

- [ ] **Step 3: Commit**

```bash
git add FarmManagerMobile/src/stores/authStore.ts
git commit -m "feat(mobile): add auth store with Zustand"
```

---

### Task 10: API Client Token 注入 + 401 处理

**Files:**
- Modify: `FarmManagerMobile/src/api/client.ts`

- [ ] **Step 1: 修改请求拦截器添加 token 注入**

在 `FarmManagerMobile/src/api/client.ts` 中，修改请求拦截器：

将：
```typescript
apiClient.interceptors.request.use(async (config) => {
  const today = new Date().toISOString().split('T')[0];
  config.headers['X-Current-Date'] = today;
  return config;
});
```

替换为：
```typescript
apiClient.interceptors.request.use(async (config) => {
  const today = new Date().toISOString().split('T')[0];
  config.headers['X-Current-Date'] = today;
  const { useAuthStore } = require('../stores/authStore');
  const token = useAuthStore.getState().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});
```

注意：使用 `require` 而非 `import` 避免循环依赖。

- [ ] **Step 2: 修改响应拦截器添加 401 处理**

在响应拦截器的 error handler 中，在现有的 `if (error.response)` 块的开头添加 401 处理：

将：
```typescript
  (error) => {
    if (error.response) {
      const detail = error.response.data?.detail;
```

替换为：
```typescript
  (error) => {
    if (error.response) {
      if (error.response.status === 401) {
        const { useAuthStore } = require('../stores/authStore');
        const store = useAuthStore.getState();
        if (store.isLoggedIn) {
          store.logout();
          const { triggerUnauthorized } = require('../stores/authStore');
          triggerUnauthorized();
        }
        return Promise.reject(new Error('登录已过期，请重新登录'));
      }
      const detail = error.response.data?.detail;
```

- [ ] **Step 3: 验证 TypeScript**

Run: `cd FarmManagerMobile && npx tsc --noEmit 2>&1 | head -20`
Expected: 无新增错误

- [ ] **Step 4: Commit**

```bash
git add FarmManagerMobile/src/api/client.ts
git commit -m "feat(mobile): add token injection and 401 handling to API client"
```

---

### Task 11: 创建登录页面

**Files:**
- Create: `FarmManagerMobile/src/screens/auth/LoginScreen.tsx`

- [ ] **Step 1: 创建登录页面**

创建 `FarmManagerMobile/src/screens/auth/LoginScreen.tsx`：

```tsx
import React, { useState, useCallback } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  Alert,
  KeyboardAvoidingView,
  Platform,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useAuthStore } from "../../stores/authStore";
import { colors } from "../../theme/colors";
import { spacing, fontSize, borderRadius } from "../../theme/spacing";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";

const PHONE_REGEX = /^1[3-9]\d{9}$/;

export const LoginScreen: React.FC<{
  onNavigateToRegister: () => void;
}> = ({ onNavigateToRegister }) => {
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const login = useAuthStore((s) => s.login);

  const handleLogin = useCallback(async () => {
    if (!PHONE_REGEX.test(phone)) {
      Alert.alert("提示", "请输入正确的11位手机号");
      return;
    }
    if (!password) {
      Alert.alert("提示", "请输入密码");
      return;
    }
    setLoading(true);
    try {
      await login({ phone, password });
    } catch (e: any) {
      Alert.alert("登录失败", e.message || "手机号或密码错误");
    } finally {
      setLoading(false);
    }
  }, [phone, password, login]);

  return (
    <SafeAreaView style={styles.container} edges={["bottom"]}>
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : "height"}
        style={styles.inner}
      >
        <View style={styles.header}>
          <View style={styles.logoIcon}>
            <Icon name="sprout" size={40} color={colors.primary} />
          </View>
          <Text style={styles.title}>农博社</Text>
          <Text style={styles.subtitle}>智能种植管理平台</Text>
        </View>

        <View style={styles.form}>
          <View style={styles.inputContainer}>
            <Icon
              name="phone"
              size={20}
              color={colors.textTertiary}
              style={styles.inputIcon}
            />
            <TextInput
              style={styles.input}
              placeholder="手机号"
              placeholderTextColor={colors.textTertiary}
              keyboardType="phone-pad"
              maxLength={11}
              value={phone}
              onChangeText={setPhone}
              editable={!loading}
            />
          </View>

          <View style={styles.inputContainer}>
            <Icon
              name="lock"
              size={20}
              color={colors.textTertiary}
              style={styles.inputIcon}
            />
            <TextInput
              style={styles.input}
              placeholder="密码"
              placeholderTextColor={colors.textTertiary}
              secureTextEntry
              value={password}
              onChangeText={setPassword}
              editable={!loading}
            />
          </View>

          <TouchableOpacity
            style={[styles.loginButton, loading && styles.loginButtonDisabled]}
            onPress={handleLogin}
            disabled={loading || phone.length < 11 || !password}
            activeOpacity={0.8}
          >
            <Text style={styles.loginButtonText}>
              {loading ? "登录中..." : "登录"}
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            onPress={onNavigateToRegister}
            disabled={loading}
            style={styles.registerLink}
          >
            <Text style={styles.registerLinkText}>
              还没有账号？<Text style={styles.registerLinkHighlight}>去注册</Text>
            </Text>
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  inner: {
    flex: 1,
    justifyContent: "center",
    paddingHorizontal: spacing.xl,
  },
  header: {
    alignItems: "center",
    marginBottom: 48,
  },
  logoIcon: {
    width: 80,
    height: 80,
    borderRadius: 20,
    backgroundColor: colors.primaryMuted,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.md,
  },
  title: {
    fontSize: 28,
    fontWeight: "700",
    color: colors.text,
    marginBottom: 4,
  },
  subtitle: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
  },
  form: {
    gap: spacing.md,
  },
  inputContainer: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    borderWidth: 1,
    borderColor: colors.borderLight,
    paddingHorizontal: spacing.md,
    height: 52,
  },
  inputIcon: {
    marginRight: spacing.sm,
  },
  input: {
    flex: 1,
    fontSize: fontSize.lg,
    color: colors.text,
    padding: 0,
  },
  loginButton: {
    backgroundColor: colors.primary,
    borderRadius: borderRadius.lg,
    height: 52,
    alignItems: "center",
    justifyContent: "center",
    marginTop: spacing.sm,
  },
  loginButtonDisabled: {
    opacity: 0.5,
  },
  loginButtonText: {
    color: "#fff",
    fontSize: fontSize.lg,
    fontWeight: "600",
  },
  registerLink: {
    alignItems: "center",
    marginTop: spacing.md,
  },
  registerLinkText: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
  },
  registerLinkHighlight: {
    color: colors.primary,
    fontWeight: "600",
  },
});
```

- [ ] **Step 2: Commit**

```bash
git add FarmManagerMobile/src/screens/auth/LoginScreen.tsx
git commit -m "feat(mobile): add login screen"
```

---

### Task 12: 创建注册页面

**Files:**
- Create: `FarmManagerMobile/src/screens/auth/RegisterScreen.tsx`

- [ ] **Step 1: 创建注册页面**

创建 `FarmManagerMobile/src/screens/auth/RegisterScreen.tsx`：

```tsx
import React, { useState, useCallback } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  Alert,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useAuthStore } from "../../stores/authStore";
import { colors } from "../../theme/colors";
import { spacing, fontSize, borderRadius } from "../../theme/spacing";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";

const PHONE_REGEX = /^1[3-9]\d{9}$/;

export const RegisterScreen: React.FC<{
  onNavigateToLogin: () => void;
}> = ({ onNavigateToLogin }) => {
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [nickname, setNickname] = useState("");
  const [loading, setLoading] = useState(false);

  const register = useAuthStore((s) => s.register);

  const handleRegister = useCallback(async () => {
    if (!PHONE_REGEX.test(phone)) {
      Alert.alert("提示", "请输入正确的11位手机号");
      return;
    }
    if (password.length < 8) {
      Alert.alert("提示", "密码至少8位");
      return;
    }
    if (password !== confirmPassword) {
      Alert.alert("提示", "两次密码不一致");
      return;
    }
    setLoading(true);
    try {
      await register({
        phone,
        password,
        nickname: nickname.trim() || undefined,
      });
    } catch (e: any) {
      Alert.alert("注册失败", e.message || "注册失败，请重试");
    } finally {
      setLoading(false);
    }
  }, [phone, password, confirmPassword, nickname, register]);

  return (
    <SafeAreaView style={styles.container} edges={["bottom"]}>
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : "height"}
        style={styles.inner}
      >
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          keyboardShouldPersistTaps="handled"
        >
          <View style={styles.header}>
            <Text style={styles.title}>创建账号</Text>
            <Text style={styles.subtitle}>注册后即可使用全部功能</Text>
          </View>

          <View style={styles.form}>
            <View style={styles.inputContainer}>
              <Icon
                name="phone"
                size={20}
                color={colors.textTertiary}
                style={styles.inputIcon}
              />
              <TextInput
                style={styles.input}
                placeholder="手机号"
                placeholderTextColor={colors.textTertiary}
                keyboardType="phone-pad"
                maxLength={11}
                value={phone}
                onChangeText={setPhone}
                editable={!loading}
              />
            </View>

            <View style={styles.inputContainer}>
              <Icon
                name="lock"
                size={20}
                color={colors.textTertiary}
                style={styles.inputIcon}
              />
              <TextInput
                style={styles.input}
                placeholder="密码（至少8位）"
                placeholderTextColor={colors.textTertiary}
                secureTextEntry
                value={password}
                onChangeText={setPassword}
                editable={!loading}
              />
            </View>

            <View style={styles.inputContainer}>
              <Icon
                name="lock-check"
                size={20}
                color={colors.textTertiary}
                style={styles.inputIcon}
              />
              <TextInput
                style={styles.input}
                placeholder="确认密码"
                placeholderTextColor={colors.textTertiary}
                secureTextEntry
                value={confirmPassword}
                onChangeText={setConfirmPassword}
                editable={!loading}
              />
            </View>

            <View style={styles.inputContainer}>
              <Icon
                name="account"
                size={20}
                color={colors.textTertiary}
                style={styles.inputIcon}
              />
              <TextInput
                style={styles.input}
                placeholder="昵称（可选，默认"农友"）"
                placeholderTextColor={colors.textTertiary}
                maxLength={20}
                value={nickname}
                onChangeText={setNickname}
                editable={!loading}
              />
            </View>

            <TouchableOpacity
              style={[styles.registerButton, loading && styles.registerButtonDisabled]}
              onPress={handleRegister}
              disabled={
                loading || phone.length < 11 || !password || !confirmPassword
              }
              activeOpacity={0.8}
            >
              <Text style={styles.registerButtonText}>
                {loading ? "注册中..." : "注册"}
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              onPress={onNavigateToLogin}
              disabled={loading}
              style={styles.loginLink}
            >
              <Text style={styles.loginLinkText}>
                已有账号？<Text style={styles.loginLinkHighlight}>去登录</Text>
              </Text>
            </TouchableOpacity>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  inner: {
    flex: 1,
  },
  scrollContent: {
    justifyContent: "center",
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.xxl,
  },
  header: {
    alignItems: "center",
    marginBottom: 40,
  },
  title: {
    fontSize: 28,
    fontWeight: "700",
    color: colors.text,
    marginBottom: 4,
  },
  subtitle: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
  },
  form: {
    gap: spacing.md,
  },
  inputContainer: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    borderWidth: 1,
    borderColor: colors.borderLight,
    paddingHorizontal: spacing.md,
    height: 52,
  },
  inputIcon: {
    marginRight: spacing.sm,
  },
  input: {
    flex: 1,
    fontSize: fontSize.lg,
    color: colors.text,
    padding: 0,
  },
  registerButton: {
    backgroundColor: colors.primary,
    borderRadius: borderRadius.lg,
    height: 52,
    alignItems: "center",
    justifyContent: "center",
    marginTop: spacing.sm,
  },
  registerButtonDisabled: {
    opacity: 0.5,
  },
  registerButtonText: {
    color: "#fff",
    fontSize: fontSize.lg,
    fontWeight: "600",
  },
  loginLink: {
    alignItems: "center",
    marginTop: spacing.md,
  },
  loginLinkText: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
  },
  loginLinkHighlight: {
    color: colors.primary,
    fontWeight: "600",
  },
});
```

- [ ] **Step 2: Commit**

```bash
git add FarmManagerMobile/src/screens/auth/RegisterScreen.tsx
git commit -m "feat(mobile): add register screen"
```

---

### Task 13: 更新 AppNavigator 添加认证流程

**Files:**
- Modify: `FarmManagerMobile/src/navigation/AppNavigator.tsx`

- [ ] **Step 1: 重写 AppNavigator 支持认证守卫**

将 `FarmManagerMobile/src/navigation/AppNavigator.tsx` 替换为：

```tsx
import React, { useEffect } from "react";
import { View, ActivityIndicator, StyleSheet } from "react-native";
import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { MainTabNavigator } from "./MainTabNavigator";
import { CycleDetailScreen } from "../screens/cycle/CycleDetailScreen";
import { CycleCreateScreen } from "../screens/cycle/CycleCreateScreen";
import { LogListScreen } from "../screens/log/LogListScreen";
import { LogCreateScreen } from "../screens/log/LogCreateScreen";
import { CostCreateScreen } from "../screens/cost/CostCreateScreen";
import { CostCategoryScreen } from "../screens/cost/CostCategoryScreen";
import { ProfitScreen } from "../screens/cost/ProfitScreen";
import { AgentChatScreen } from "../screens/agent/AgentChatScreen";
import { AgentReportScreen } from "../screens/agent/AgentReportScreen";
import { GuideScreen } from "../screens/settings/GuideScreen";
import { DebtListScreen } from "../screens/debt/DebtListScreen";
import { DebtCreateScreen } from "../screens/debt/DebtCreateScreen";
import { CropTemplateScreen } from "../screens/crop/CropTemplateScreen";
import { WeatherDetailScreen } from "../screens/weather/WeatherDetailScreen";
import { LoginScreen } from "../screens/auth/LoginScreen";
import { RegisterScreen } from "../screens/auth/RegisterScreen";
import { useAuthStore, setOnUnauthorized } from "../stores/authStore";
import { colors } from "../theme/colors";

export type RootStackParamList = {
  Main: undefined;
  CycleDetail: { cycleId: number };
  CycleCreate: undefined;
  LogList: { cycleId: number };
  LogCreate: { cycleId: number };
  CostCreate: undefined;
  CostCategory: undefined;
  Profit: { cycleId: number };
  AgentChat: { cycleId?: number };
  AgentReport: {
    cycleId?: number;
    content?: string;
    reportType?: string;
    createdAt?: string;
    reportId?: number;
  };
  Guide: undefined;
  DebtList: undefined;
  DebtCreate: undefined;
  CropTemplate: undefined;
  WeatherDetail: undefined;
  Login: undefined;
  Register: undefined;
};

const Stack = createNativeStackNavigator<RootStackParamList>();

const screenOptions = {
  headerStyle: {
    backgroundColor: colors.headerBg,
  },
  headerTintColor: colors.headerText,
  headerTitleStyle: {
    fontSize: 18,
    fontWeight: "700" as const,
  },
  headerShadowVisible: false,
  contentStyle: {
    backgroundColor: colors.background,
  },
};

export const AppNavigator: React.FC = () => {
  const isLoggedIn = useAuthStore((s) => s.isLoggedIn);
  const isInitializing = useAuthStore((s) => s.isInitializing);
  const initialize = useAuthStore((s) => s.initialize);

  useEffect(() => {
    initialize();
  }, []);

  if (isInitializing) {
    return (
      <View style={styles.loading}>
        <ActivityIndicator size="large" color={colors.primary} />
      </View>
    );
  }

  return (
    <NavigationContainer
      ref={(ref) => {
        if (ref) {
          setOnUnauthorized(() => {
            try {
              ref.reset({ index: 0, routes: [{ name: "Login" }] });
            } catch {}
          });
        }
      }}
    >
      <Stack.Navigator screenOptions={screenOptions}>
        {isLoggedIn ? (
          <>
            <Stack.Screen
              name="Main"
              component={MainTabNavigator}
              options={{ headerShown: false }}
            />
            <Stack.Screen
              name="CycleDetail"
              component={CycleDetailScreen}
              options={{ title: "茬口详情" }}
            />
            <Stack.Screen
              name="CycleCreate"
              component={CycleCreateScreen}
              options={{ title: "新建茬口" }}
            />
            <Stack.Screen
              name="LogList"
              component={LogListScreen}
              options={{ title: "农事记录" }}
            />
            <Stack.Screen
              name="LogCreate"
              component={LogCreateScreen}
              options={{ title: "快速打卡" }}
            />
            <Stack.Screen
              name="CostCreate"
              component={CostCreateScreen}
              options={{ title: "记一笔" }}
            />
            <Stack.Screen
              name="CostCategory"
              component={CostCategoryScreen}
              options={{ title: "分类管理" }}
            />
            <Stack.Screen
              name="Profit"
              component={ProfitScreen}
              options={{ title: "利润统计" }}
            />
            <Stack.Screen
              name="AgentChat"
              component={AgentChatScreen}
              options={{ title: "农事顾问" }}
            />
            <Stack.Screen
              name="AgentReport"
              component={AgentReportScreen}
              options={{ title: "种植报告" }}
            />
            <Stack.Screen
              name="Guide"
              component={GuideScreen}
              options={{ title: "使用指南" }}
            />
            <Stack.Screen
              name="DebtList"
              component={DebtListScreen}
              options={{ title: "赊账管理" }}
            />
            <Stack.Screen
              name="DebtCreate"
              component={DebtCreateScreen}
              options={{ title: "记赊账" }}
            />
            <Stack.Screen
              name="CropTemplate"
              component={CropTemplateScreen}
              options={{ title: "作物模板" }}
            />
            <Stack.Screen
              name="WeatherDetail"
              component={WeatherDetailScreen}
              options={{ title: "天气详情", headerShown: false }}
            />
          </>
        ) : (
          <>
            <Stack.Screen
              name="Login"
              component={(props: any) => (
                <LoginScreen
                  onNavigateToRegister={() => props.navigation.navigate("Register")}
                />
              )}
              options={{ headerShown: false }}
            />
            <Stack.Screen
              name="Register"
              component={(props: any) => (
                <RegisterScreen
                  onNavigateToLogin={() => props.navigation.navigate("Login")}
                />
              )}
              options={{ headerShown: false }}
            />
          </>
        )}
      </Stack.Navigator>
    </NavigationContainer>
  );
};

const styles = StyleSheet.create({
  loading: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: colors.background,
  },
});
```

- [ ] **Step 2: 验证 TypeScript**

Run: `cd FarmManagerMobile && npx tsc --noEmit 2>&1 | head -20`
Expected: 无新增错误

- [ ] **Step 3: Commit**

```bash
git add FarmManagerMobile/src/navigation/AppNavigator.tsx
git commit -m "feat(mobile): add auth flow to AppNavigator"
```

---

### Task 14: 更新 SettingsScreen 添加个人中心 + 退出登录

**Files:**
- Modify: `FarmManagerMobile/src/screens/settings/SettingsScreen.tsx`

- [ ] **Step 1: 修改 SettingsScreen 添加 auth 集成**

在 `FarmManagerMobile/src/screens/settings/SettingsScreen.tsx` 中：

a) 在导入区添加 authStore：

```typescript
import { useAuthStore } from "../../stores/authStore";
```

b) 在 `SettingsScreen` 组件内部，在其他 store 解构之后添加：

```typescript
const user = useAuthStore((s) => s.user);
const logout = useAuthStore((s) => s.logout);
```

c) 将 `handleProfilePress` 函数替换为：

```typescript
const handleProfilePress = useCallback(() => {
  if (!user) return;
  Alert.prompt(
    "修改昵称",
    "输入新昵称",
    [
      { text: "取消", style: "cancel" },
      {
        text: "确定",
        onPress: async (value?: string) => {
          const trimmed = (value || "").trim();
          if (trimmed) {
            try {
              await useAuthStore.getState().updateProfile({ nickname: trimmed });
            } catch {
              showToast("修改失败");
            }
          }
        },
      },
    ],
    "plain-text",
    user.nickname
  );
}, [user]);
```

d) 添加退出登录处理函数（在 `handleClearCache` 之后）：

```typescript
const handleLogout = useCallback(() => {
  Alert.alert("退出登录", "确定要退出登录吗？", [
    { text: "取消", style: "cancel" },
    {
      text: "确定",
      style: "destructive",
      onPress: async () => {
        await logout();
      },
    },
  ]);
}, [logout]);
```

e) 将 Profile Header 的硬编码 "农友" 替换为动态用户名：

将：
```tsx
<Text style={styles.profileName}>农友</Text>
```

替换为：
```tsx
<Text style={styles.profileName}>{user?.nickname || "农友"}</Text>
```

将：
```tsx
<Text style={styles.profileSub}>让种植更简单</Text>
```

替换为：
```tsx
<Text style={styles.profileSub}>{user?.phone || "让种植更简单"}</Text>
```

f) 在 "数据管理" section 的 "清除缓存" 菜单项之后，添加退出登录项：

```tsx
<MenuItem
  icon="logout"
  iconColor={colors.danger}
  label="退出登录"
  onPress={handleLogout}
  isLast
/>
```

同时将原来的 "清除缓存" 的 `isLast` 移除（改为 `false` 或直接删除该 prop）。

g) 删除 `handleProfilePress` 中原来的 `Alert.alert("提示", "登录功能即将上线")` — 已被步骤 c 替换。

- [ ] **Step 2: 验证 TypeScript**

Run: `cd FarmManagerMobile && npx tsc --noEmit 2>&1 | head -20`
Expected: 无新增错误

- [ ] **Step 3: Commit**

```bash
git add FarmManagerMobile/src/screens/settings/SettingsScreen.tsx
git commit -m "feat(mobile): add profile editing and logout to SettingsScreen"
```

---

### Task 15: 端到端验证

- [ ] **Step 1: 后端全量测试**

Run: `cd backend && python -m pytest -x -q`
Expected: 全部 PASS

- [ ] **Step 2: admin-web 编译检查**

Run: `cd admin-web && npx tsc --noEmit && npm run build 2>&1 | tail -5`
Expected: 构建成功

- [ ] **Step 3: Mobile 编译检查**

Run: `cd FarmManagerMobile && npx tsc --noEmit`
Expected: 无错误

- [ ] **Step 4: 手动端到端验证清单**

| # | 场景 | 验证点 |
|---|------|--------|
| 1 | App 注册新用户 | 注册成功 → 自动进入主界面 |
| 2 | App 退出登录 | 退出后回到登录页 |
| 3 | App 重新登录 | 登录成功 → 进入主界面 |
| 4 | App 修改昵称 | 昵称更新成功 |
| 5 | admin-web 查看用户 | 列表显示新注册的用户 |
| 6 | admin-web 禁用用户 | 禁用成功，状态标签变红 |
| 7 | App 被禁用后请求 | 下次请求返回 401 → 跳转登录页 |
| 8 | App 杀进程重启 | 已登录 → 直接进主界面（token 有效） |
| 9 | admin-web 启用用户 | 启用成功，用户可重新登录 |

---

## Self-Review Checklist

**1. Spec Coverage:**

| Spec Requirement | Task |
|---|---|
| GET /admin/users (分页/筛选/搜索) | Task 3 |
| GET /admin/users/{id} (详情+农场信息) | Task 3 |
| PUT /admin/users/{id}/status (禁用/启用) | Task 3 |
| require_admin 依赖 | Task 1 |
| 不返回 password_hash | Task 3 (schema 不含该字段) |
| admin-web 用户列表页 | Task 6 |
| admin-web 用户详情弹窗 | Task 6 |
| admin-web 导航+路由 | Task 7 |
| App 登录页 | Task 11 |
| App 注册页 | Task 12 |
| App 个人中心 | Task 14 |
| Token 存储 (AsyncStorage) | Task 9 |
| Token 注入 | Task 10 |
| 401 处理 → 跳转登录 | Task 10 + Task 13 |
| App 启动验证 token | Task 9 (initialize) + Task 13 |
| 导航守卫 (已登录/未登录) | Task 13 |

**2. Placeholder Scan:** 无 TBD、TODO、"implement later" 等占位符。

**3. Type Consistency:**
- `UserProfile` 定义在 `api/types.ts`，在 `authStore.ts` 和 `LoginScreen`/`RegisterScreen` 中通过 `TokenResponse.user` 获取
- `UserListItem` / `UserDetail` / `ListUsersParams` 在 `admin-web/src/api/users.ts` 中定义，在 `pages/Users/index.tsx` 中使用
- `UpdateUserStatusRequest` 的 `status` 字段使用 regex 校验 `^(active|disabled)$`，与 `UserStatus` 枚举一致
- `authStore.login` 接收 `LoginParams`，`authStore.register` 接收 `RegisterParams`，与 `LoginScreen`/`RegisterScreen` 调用一致

**Design Deviation:** 原设计 D3 选择 `expo-secure-store`，但项目为 React Native CLI（非 Expo），因此改用已安装的 `AsyncStorage`。风险已在 design.md 中确认（越狱设备可提取 token）。
