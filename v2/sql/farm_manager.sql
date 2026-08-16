-- Farm Manager v2 Business canonical schema
--
-- 用途：新环境初始化 / 生成基线迁移。
-- 生产环境禁止直接执行 DROP TABLE 或用本文件覆盖已有数据库；生产变更必须使用版本化增量迁移。
-- 范围：Business REST、Business MCP 及业务 Service。
-- 不包含：Agent MongoDB collections、Redis 状态、数据飞轮和仿真评测遗留表。

SET NAMES utf8mb4;
SET time_zone = '+00:00';

CREATE TABLE users (
  id VARCHAR(36) NOT NULL,
  phone VARCHAR(20) NOT NULL,
  password_hash VARCHAR(128) NOT NULL,
  nickname VARCHAR(50) NOT NULL DEFAULT '农友',
  avatar_url VARCHAR(500) NULL,
  role VARCHAR(20) NOT NULL DEFAULT 'user',
  status VARCHAR(20) NOT NULL DEFAULT 'active',
  token_monthly_limit INT NULL,
  token_weekly_limit INT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_users_phone (phone)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE farms (
  id INT NOT NULL AUTO_INCREMENT,
  uid VARCHAR(36) NOT NULL,
  name VARCHAR(100) NOT NULL,
  location VARCHAR(200) NULL,
  user_id VARCHAR(36) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_farms_uid (uid),
  UNIQUE KEY uq_farms_user_id (user_id),
  CONSTRAINT fk_farms_user
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE user_settings (
  id INT NOT NULL AUTO_INCREMENT,
  user_id VARCHAR(36) NOT NULL,
  default_city VARCHAR(50) NULL,
  default_lat FLOAT NULL,
  default_lon FLOAT NULL,
  assistant_role VARCHAR(20) NOT NULL DEFAULT 'warm',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_user_settings_user_id (user_id),
  CONSTRAINT fk_user_settings_user
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE crop_templates (
  id INT NOT NULL AUTO_INCREMENT,
  farm_id INT NULL,
  name VARCHAR(100) NOT NULL,
  variety VARCHAR(100) NULL,
  category VARCHAR(50) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_crop_templates_farm_id (farm_id),
  KEY idx_crop_templates_farm_name_variety (farm_id, name, variety),
  CONSTRAINT fk_crop_templates_farm
    FOREIGN KEY (farm_id) REFERENCES farms (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE growth_stages (
  id INT NOT NULL AUTO_INCREMENT,
  crop_template_id INT NOT NULL,
  name VARCHAR(100) NOT NULL,
  duration_days INT NOT NULL,
  order_index INT NOT NULL,
  key_tasks VARCHAR(500) NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_growth_stages_template_order
    (crop_template_id, order_index),
  KEY idx_growth_stages_template_id (crop_template_id),
  CONSTRAINT fk_growth_stages_template
    FOREIGN KEY (crop_template_id) REFERENCES crop_templates (id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE crop_cycles (
  id INT NOT NULL AUTO_INCREMENT,
  farm_id INT NOT NULL,
  name VARCHAR(100) NOT NULL,
  crop_template_id INT NOT NULL,
  start_date DATE NOT NULL,
  field_name VARCHAR(100) NULL,
  total_area_mu DECIMAL(10,2) NULL,
  season VARCHAR(50) NULL,
  batch_note VARCHAR(500) NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'active',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_crop_cycles_farm_status_start
    (farm_id, status, start_date),
  KEY idx_crop_cycles_template_id (crop_template_id),
  CONSTRAINT fk_crop_cycles_farm
    FOREIGN KEY (farm_id) REFERENCES farms (id) ON DELETE RESTRICT,
  CONSTRAINT fk_crop_cycles_template
    FOREIGN KEY (crop_template_id) REFERENCES crop_templates (id)
    ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE cycle_stages (
  id INT NOT NULL AUTO_INCREMENT,
  cycle_id INT NOT NULL,
  name VARCHAR(100) NOT NULL,
  start_date DATE NOT NULL,
  end_date DATE NOT NULL,
  order_index INT NOT NULL,
  duration_days INT NOT NULL,
  key_tasks VARCHAR(500) NULL,
  is_current TINYINT(1) NOT NULL DEFAULT 0,
  PRIMARY KEY (id),
  UNIQUE KEY uq_cycle_stages_cycle_order (cycle_id, order_index),
  KEY idx_cycle_stages_cycle_id (cycle_id),
  CONSTRAINT fk_cycle_stages_cycle
    FOREIGN KEY (cycle_id) REFERENCES crop_cycles (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE planting_units (
  id INT NOT NULL AUTO_INCREMENT,
  farm_id INT NOT NULL,
  cycle_id INT NOT NULL,
  name VARCHAR(100) NOT NULL,
  area_mu DECIMAL(10,2) NULL,
  planted_date DATE NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'active',
  note VARCHAR(500) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_planting_units_farm_id (farm_id),
  KEY idx_planting_units_cycle_id (cycle_id),
  CONSTRAINT fk_planting_units_farm
    FOREIGN KEY (farm_id) REFERENCES farms (id) ON DELETE RESTRICT,
  CONSTRAINT fk_planting_units_cycle
    FOREIGN KEY (cycle_id) REFERENCES crop_cycles (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE workers (
  id INT NOT NULL AUTO_INCREMENT,
  farm_id INT NOT NULL,
  name VARCHAR(100) NOT NULL,
  phone VARCHAR(30) NULL,
  default_pay_type VARCHAR(20) NOT NULL DEFAULT 'daily',
  default_unit_price DECIMAL(10,2) NULL,
  note VARCHAR(500) NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'active',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_workers_farm_status (farm_id, status),
  CONSTRAINT fk_workers_farm
    FOREIGN KEY (farm_id) REFERENCES farms (id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE operation_work_orders (
  id INT NOT NULL AUTO_INCREMENT,
  farm_id INT NOT NULL,
  cycle_id INT NULL,
  operation_type VARCHAR(50) NOT NULL,
  operation_date DATE NOT NULL,
  scope_type VARCHAR(20) NOT NULL DEFAULT 'cycle',
  note VARCHAR(500) NULL,
  photo_urls TEXT NULL,
  source_type VARCHAR(50) NULL,
  source_id INT NULL,
  labor_cost_record_id INT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_operation_work_orders_farm_date
    (farm_id, operation_date),
  KEY idx_operation_work_orders_cycle_id (cycle_id),
  KEY idx_operation_work_orders_labor_cost (labor_cost_record_id),
  CONSTRAINT fk_operation_work_orders_farm
    FOREIGN KEY (farm_id) REFERENCES farms (id) ON DELETE RESTRICT,
  CONSTRAINT fk_operation_work_orders_cycle
    FOREIGN KEY (cycle_id) REFERENCES crop_cycles (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE farm_logs (
  id INT NOT NULL AUTO_INCREMENT,
  farm_id INT NOT NULL,
  cycle_id INT NOT NULL,
  work_order_id INT NULL,
  operation_type VARCHAR(50) NOT NULL,
  operation_date DATE NOT NULL,
  operation_time DATETIME NULL,
  note VARCHAR(500) NULL,
  photo_urls VARCHAR(2000) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_farm_logs_farm_date (farm_id, operation_date),
  KEY idx_farm_logs_cycle_id (cycle_id),
  KEY idx_farm_logs_work_order_id (work_order_id),
  CONSTRAINT fk_farm_logs_farm
    FOREIGN KEY (farm_id) REFERENCES farms (id) ON DELETE RESTRICT,
  CONSTRAINT fk_farm_logs_cycle
    FOREIGN KEY (cycle_id) REFERENCES crop_cycles (id) ON DELETE CASCADE,
  CONSTRAINT fk_farm_logs_work_order
    FOREIGN KEY (work_order_id) REFERENCES operation_work_orders (id)
    ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE farm_log_workers (
  id INT NOT NULL AUTO_INCREMENT,
  farm_log_id INT NOT NULL,
  worker_id INT NOT NULL,
  role VARCHAR(50) NULL,
  note VARCHAR(500) NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_farm_log_workers_log_worker (farm_log_id, worker_id),
  KEY idx_farm_log_workers_worker_id (worker_id),
  CONSTRAINT fk_farm_log_workers_log
    FOREIGN KEY (farm_log_id) REFERENCES farm_logs (id) ON DELETE CASCADE,
  CONSTRAINT fk_farm_log_workers_worker
    FOREIGN KEY (worker_id) REFERENCES workers (id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE operation_work_order_units (
  id INT NOT NULL AUTO_INCREMENT,
  work_order_id INT NOT NULL,
  unit_id INT NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_operation_work_order_units_order_unit
    (work_order_id, unit_id),
  KEY idx_operation_work_order_units_unit_id (unit_id),
  CONSTRAINT fk_operation_work_order_units_order
    FOREIGN KEY (work_order_id) REFERENCES operation_work_orders (id)
    ON DELETE CASCADE,
  CONSTRAINT fk_operation_work_order_units_unit
    FOREIGN KEY (unit_id) REFERENCES planting_units (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE labor_entries (
  id INT NOT NULL AUTO_INCREMENT,
  farm_id INT NOT NULL,
  work_order_id INT NOT NULL,
  worker_id INT NOT NULL,
  pay_type VARCHAR(20) NOT NULL DEFAULT 'daily',
  quantity DECIMAL(10,2) NOT NULL DEFAULT 1.00,
  unit_price DECIMAL(10,2) NOT NULL,
  payable_amount DECIMAL(10,2) NOT NULL,
  paid_amount DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  unpaid_amount DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  settlement_status VARCHAR(20) NOT NULL DEFAULT 'unpaid',
  client_request_id VARCHAR(100) NULL,
  note VARCHAR(500) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_labor_entries_farm_client_request
    (farm_id, client_request_id),
  KEY idx_labor_entries_work_order_id (work_order_id),
  KEY idx_labor_entries_worker_status (worker_id, settlement_status),
  CONSTRAINT fk_labor_entries_farm
    FOREIGN KEY (farm_id) REFERENCES farms (id) ON DELETE RESTRICT,
  CONSTRAINT fk_labor_entries_work_order
    FOREIGN KEY (work_order_id) REFERENCES operation_work_orders (id)
    ON DELETE CASCADE,
  CONSTRAINT fk_labor_entries_worker
    FOREIGN KEY (worker_id) REFERENCES workers (id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE cost_categories (
  id INT NOT NULL AUTO_INCREMENT,
  farm_id INT NOT NULL,
  name VARCHAR(50) NOT NULL,
  type VARCHAR(10) NOT NULL,
  icon VARCHAR(50) NOT NULL DEFAULT 'tag',
  sort_order INT NOT NULL DEFAULT 0,
  is_default TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_cost_categories_farm_type_name (farm_id, type, name),
  KEY idx_cost_categories_farm_id (farm_id),
  CONSTRAINT fk_cost_categories_farm
    FOREIGN KEY (farm_id) REFERENCES farms (id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE cost_records (
  id INT NOT NULL AUTO_INCREMENT,
  farm_id INT NOT NULL,
  cycle_id INT NULL,
  record_type VARCHAR(20) NOT NULL,
  category VARCHAR(50) NOT NULL,
  category_id INT NULL,
  category_name_snapshot VARCHAR(50) NULL,
  amount DECIMAL(10,2) NOT NULL,
  settled_amount DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  settlement_status VARCHAR(20) NOT NULL DEFAULT 'settled',
  record_date DATE NOT NULL,
  recorded_at DATETIME NULL,
  note VARCHAR(500) NULL,
  record_subtype VARCHAR(50) NULL,
  counterparty VARCHAR(100) NULL,
  due_date DATE NULL,
  settled_at DATETIME NULL,
  parent_record_id INT NULL,
  source_type VARCHAR(50) NULL,
  source_id INT NULL,
  source_active_key VARCHAR(20) NULL,
  deleted_at DATETIME NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_cost_records_active_source
    (farm_id, source_type, source_id, source_active_key),
  KEY idx_cost_records_farm_date_deleted
    (farm_id, record_date, deleted_at),
  KEY idx_cost_records_farm_type_date
    (farm_id, record_type, record_date),
  KEY idx_cost_records_category_id (category_id),
  KEY idx_cost_records_cycle_id (cycle_id),
  KEY idx_cost_records_parent_id (parent_record_id),
  CONSTRAINT fk_cost_records_farm
    FOREIGN KEY (farm_id) REFERENCES farms (id) ON DELETE RESTRICT,
  CONSTRAINT fk_cost_records_cycle
    FOREIGN KEY (cycle_id) REFERENCES crop_cycles (id) ON DELETE SET NULL,
  CONSTRAINT fk_cost_records_category
    FOREIGN KEY (category_id) REFERENCES cost_categories (id)
    ON DELETE RESTRICT,
  CONSTRAINT fk_cost_records_parent
    FOREIGN KEY (parent_record_id) REFERENCES cost_records (id)
    ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

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

CREATE TABLE token_daily_stats (
  id INT NOT NULL AUTO_INCREMENT,
  farm_id INT NOT NULL,
  user_id VARCHAR(36) NULL,
  stat_date DATE NOT NULL,
  service_name VARCHAR(30) NOT NULL DEFAULT 'agent',
  model VARCHAR(100) NOT NULL,
  call_type VARCHAR(30) NOT NULL,
  user_scope_key VARCHAR(36)
    GENERATED ALWAYS AS (COALESCE(user_id, '')) STORED,
  prompt_tokens INT NOT NULL DEFAULT 0,
  completion_tokens INT NOT NULL DEFAULT 0,
  total_tokens INT NOT NULL DEFAULT 0,
  request_count INT NOT NULL DEFAULT 0,
  estimated_cost_cny DECIMAL(10,6) NOT NULL DEFAULT 0.000000,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_token_daily_stats_scope
    (farm_id, user_scope_key, stat_date, service_name, model, call_type),
  KEY idx_token_daily_stats_farm_date (farm_id, stat_date),
  KEY idx_token_daily_stats_user_date (user_id, stat_date),
  CONSTRAINT fk_token_daily_stats_farm
    FOREIGN KEY (farm_id) REFERENCES farms (id) ON DELETE RESTRICT,
  CONSTRAINT fk_token_daily_stats_user
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE operation_work_orders
  ADD CONSTRAINT fk_operation_work_orders_labor_cost
  FOREIGN KEY (labor_cost_record_id) REFERENCES cost_records (id)
  ON DELETE SET NULL;
