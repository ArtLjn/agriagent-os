-- 种植计划聚合执行幂等记录。
-- 必须与业务实体迁移在同一发布窗口执行；应用启动不自动建表。
CREATE TABLE planting_plan_executions (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  farm_id BIGINT NOT NULL,
  client_request_id VARCHAR(64) NOT NULL,
  request_fingerprint VARCHAR(80) NOT NULL,
  approval_fingerprint VARCHAR(80) NOT NULL,
  status VARCHAR(20) NOT NULL,
  crop_template_id BIGINT NULL,
  crop_cycle_id BIGINT NULL,
  planting_unit_id BIGINT NULL,
  result_json JSON NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NULL,
  UNIQUE KEY uq_planting_plan_farm_request (farm_id, client_request_id),
  KEY idx_planting_plan_farm_created (farm_id, created_at)
);
