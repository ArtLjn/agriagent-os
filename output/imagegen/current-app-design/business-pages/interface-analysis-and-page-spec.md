# 业务补全页面接口分析与设计规格

## 后端接口现状

- 智能填写聚合入口：`GET /smart-fill/scenarios`、`POST /smart-fill/parse`。
- 聚合入口只负责解析自然语言并返回 `draft`，不会直接落库。
- 当前已注册智能解析场景：
  - `ledger.record`：记账草稿，兼容旧入口 `POST /costs/parse`。
  - `crop.template`：作物模板草稿，兼容旧入口 `POST /crops/templates/parse`。
  - `crop.cycle`：茬口草稿，兼容旧入口 `POST /cycles/parse`。
- 移动端 `RecordFlowController.parse()` 目前固定传 `ledger.record`，因此记录页只跑通了记账智能填写。
- 移动端保存逻辑已预留多场景分发：记账、赊账、农事日志、作业单、工资，但智能解析侧尚未覆盖 `farm.log`、`work_order.create`、`wage.record`。

## 可直接对接的手动接口

- 手动记账：`POST /costs`
  - 字段：`record_type`、`category`、`amount`、`record_date`、`cycle_id`、`note`、`record_subtype`、`counterparty`、`due_date`。
- 茬口列表：`GET /cycles`
- 创建/编辑茬口：`POST /cycles`、`PUT /cycles/{cycle_id}`
  - 字段：`name`、`crop_template_id`、`start_date`、`field_name`、`total_area_mu`、`season`、`batch_note`。
- 作物模板列表：`GET /crops/templates`
- 创建/编辑作物模板：`POST /crops/templates`、`PUT /crops/templates/{template_id}`
  - 字段：`name`、`variety`、`stages[]`，阶段包含 `name`、`duration_days`、`order_index`、`key_tasks`。
- 工人列表：`GET /planting/workers/summary`
- 新增/编辑工人：`POST /planting/workers`、`PUT /planting/workers/{worker_id}`
  - 字段：`name`、`phone`、`default_pay_type`、`default_unit_price`、`note`、`status`。
- 记农事/作业单：`POST /planting/work-orders`
  - 字段：`cycle_id`、`operation_type`、`operation_date`、`scope_type`、`unit_ids`、`note`、`photo_urls`、`labor_entries[]`。
- 记工资：`POST /planting/labor/wages`
  - 字段：`cycle_id`、`operation_type`、`worker_id` 或 `worker_name`、`pay_type`、`quantity`、`unit_price`、`paid_amount`、`work_date`、`client_request_id`。

## 设计边界

- 记录页二级入口优先走手动表单，确保当前接口可落库。
- 智能填写按钮只标注在已支持解析的页面：记账、茬口、作物模板。
- 农事作业和工资页面保留“从一句话生成草稿”的入口样式，但在实现时应等后端补齐 `work_order.create`、`wage.record` 智能场景后再开放。
- 列表页强调“可筛选、可新建、可继续处理”，不做纯展示页。

## 页面清单

1. `ledger-manual-create`：记账手动填写操作页。
2. `farm-cycle-list`：农事茬口列表页。
3. `farm-cycle-form`：记录农事茬口操作页。
4. `crop-template-list`：作物模板列表页。
5. `crop-template-form`：作物模板操作页。
6. `worker-list`：工人列表页。
7. `worker-form`：新增工人操作页。

## 全局视觉规格

- 画布：`1024x2224`，对应 Flutter `430x932` 逻辑像素。
- 背景：`#F7F9FC`，顶部轻微白色过渡。
- 卡片：白色，圆角 `18-20px`，边框 `#E8ECF2`，轻阴影。
- 主色：蓝 `#2F73F6`，绿色 `#35C879`，橙色 `#FF9F1C`，紫色 `#7C5CFF`。
- 字体：平台中文无衬线，标题 `22-28px` 加粗，正文 `14-16px`。
- 顶部栏：返回按钮 + 页面标题 + 右侧筛选/更多/智能图标。
- 底部操作：表单页使用固定底部按钮；列表页保留底部 Tab。
