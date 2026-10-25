-- 种植计划聚合执行幂等记录。
-- 必须与业务实体迁移在同一发布窗口执行；应用启动不自动建表。
CREATE TABLE planting_plan_executions (
  id INT NOT NULL AUTO_INCREMENT,
  farm_id INT NOT NULL,
  client_request_id VARCHAR(100) NOT NULL,
  request_fingerprint VARCHAR(80) NOT NULL,
  approval_fingerprint VARCHAR(80) NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'committed',
  crop_template_id INT NULL,
  crop_cycle_id INT NULL,
  planting_unit_id INT NULL,
  result_json JSON NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_planting_plan_executions_farm_request
    (farm_id, client_request_id),
  KEY idx_planting_plan_executions_farm_created
    (farm_id, created_at),
  CONSTRAINT fk_planting_plan_executions_farm
    FOREIGN KEY (farm_id) REFERENCES farms (id) ON DELETE RESTRICT,
  CONSTRAINT fk_planting_plan_executions_template
    FOREIGN KEY (crop_template_id) REFERENCES crop_templates (id)
    ON DELETE SET NULL,
  CONSTRAINT fk_planting_plan_executions_cycle
    FOREIGN KEY (crop_cycle_id) REFERENCES crop_cycles (id)
    ON DELETE SET NULL,
  CONSTRAINT fk_planting_plan_executions_unit
    FOREIGN KEY (planting_unit_id) REFERENCES planting_units (id)
    ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
