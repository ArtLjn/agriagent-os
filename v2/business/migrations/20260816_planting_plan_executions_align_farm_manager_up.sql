-- 将已按早期 v2 迁移创建的表对齐到 v2/sql/farm_manager.sql。
-- 兼容曾使用 cycle_id 的表，并保留已有执行记录。

SET @schema_name = DATABASE();

SET @has_old_cycle_id = (
  SELECT COUNT(*)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @schema_name
    AND TABLE_NAME = 'planting_plan_executions'
    AND COLUMN_NAME = 'cycle_id'
);
SET @has_crop_cycle_id = (
  SELECT COUNT(*)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @schema_name
    AND TABLE_NAME = 'planting_plan_executions'
    AND COLUMN_NAME = 'crop_cycle_id'
);

SET @sql = IF(
  @has_old_cycle_id = 1 AND @has_crop_cycle_id = 0,
  'ALTER TABLE planting_plan_executions CHANGE COLUMN cycle_id crop_cycle_id INT NULL',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = IF(
  @has_old_cycle_id = 1 AND @has_crop_cycle_id = 1,
  'UPDATE planting_plan_executions SET crop_cycle_id = COALESCE(crop_cycle_id, cycle_id)',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = IF(
  @has_old_cycle_id = 1 AND @has_crop_cycle_id = 1,
  'ALTER TABLE planting_plan_executions DROP COLUMN cycle_id',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_crop_cycle_id = (
  SELECT COUNT(*)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @schema_name
    AND TABLE_NAME = 'planting_plan_executions'
    AND COLUMN_NAME = 'crop_cycle_id'
);
SET @sql = IF(
  @has_crop_cycle_id = 0,
  'ALTER TABLE planting_plan_executions ADD COLUMN crop_cycle_id INT NULL AFTER crop_template_id',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

ALTER TABLE planting_plan_executions
  MODIFY COLUMN id INT NOT NULL AUTO_INCREMENT,
  MODIFY COLUMN farm_id INT NOT NULL,
  MODIFY COLUMN client_request_id VARCHAR(100) NOT NULL,
  MODIFY COLUMN request_fingerprint VARCHAR(80) NOT NULL,
  MODIFY COLUMN approval_fingerprint VARCHAR(80) NOT NULL,
  MODIFY COLUMN status VARCHAR(20) NOT NULL DEFAULT 'committed',
  MODIFY COLUMN crop_template_id INT NULL,
  MODIFY COLUMN crop_cycle_id INT NULL,
  MODIFY COLUMN planting_unit_id INT NULL,
  MODIFY COLUMN created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  MODIFY COLUMN updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    ON UPDATE CURRENT_TIMESTAMP;

SET @has_old_unique = (
  SELECT COUNT(*)
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = @schema_name
    AND TABLE_NAME = 'planting_plan_executions'
    AND INDEX_NAME = 'uq_planting_plan_farm_request'
);
SET @has_new_unique = (
  SELECT COUNT(*)
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = @schema_name
    AND TABLE_NAME = 'planting_plan_executions'
    AND INDEX_NAME = 'uq_planting_plan_executions_farm_request'
);
SET @sql = IF(
  @has_old_unique = 1 AND @has_new_unique = 0,
  'ALTER TABLE planting_plan_executions RENAME INDEX uq_planting_plan_farm_request TO uq_planting_plan_executions_farm_request',
  IF(@has_old_unique = 1 AND @has_new_unique = 1,
     'ALTER TABLE planting_plan_executions DROP INDEX uq_planting_plan_farm_request',
     IF(@has_old_unique = 0 AND @has_new_unique = 0,
        'ALTER TABLE planting_plan_executions ADD UNIQUE KEY uq_planting_plan_executions_farm_request (farm_id, client_request_id)',
        'SELECT 1'))
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_old_index = (
  SELECT COUNT(*)
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = @schema_name
    AND TABLE_NAME = 'planting_plan_executions'
    AND INDEX_NAME = 'idx_planting_plan_farm_created'
);
SET @has_new_index = (
  SELECT COUNT(*)
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = @schema_name
    AND TABLE_NAME = 'planting_plan_executions'
    AND INDEX_NAME = 'idx_planting_plan_executions_farm_created'
);
SET @sql = IF(
  @has_old_index = 1 AND @has_new_index = 0,
  'ALTER TABLE planting_plan_executions RENAME INDEX idx_planting_plan_farm_created TO idx_planting_plan_executions_farm_created',
  IF(@has_old_index = 1 AND @has_new_index = 1,
     'ALTER TABLE planting_plan_executions DROP INDEX idx_planting_plan_farm_created',
     IF(@has_old_index = 0 AND @has_new_index = 0,
        'ALTER TABLE planting_plan_executions ADD KEY idx_planting_plan_executions_farm_created (farm_id, created_at)',
        'SELECT 1'))
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = IF(
  NOT EXISTS (
    SELECT 1
    FROM information_schema.REFERENTIAL_CONSTRAINTS
    WHERE CONSTRAINT_SCHEMA = @schema_name
      AND TABLE_NAME = 'planting_plan_executions'
      AND CONSTRAINT_NAME = 'fk_planting_plan_executions_farm'
  ),
  'ALTER TABLE planting_plan_executions ADD CONSTRAINT fk_planting_plan_executions_farm FOREIGN KEY (farm_id) REFERENCES farms (id) ON DELETE RESTRICT',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = IF(
  NOT EXISTS (
    SELECT 1
    FROM information_schema.REFERENTIAL_CONSTRAINTS
    WHERE CONSTRAINT_SCHEMA = @schema_name
      AND TABLE_NAME = 'planting_plan_executions'
      AND CONSTRAINT_NAME = 'fk_planting_plan_executions_template'
  ),
  'ALTER TABLE planting_plan_executions ADD CONSTRAINT fk_planting_plan_executions_template FOREIGN KEY (crop_template_id) REFERENCES crop_templates (id) ON DELETE SET NULL',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = IF(
  NOT EXISTS (
    SELECT 1
    FROM information_schema.REFERENTIAL_CONSTRAINTS
    WHERE CONSTRAINT_SCHEMA = @schema_name
      AND TABLE_NAME = 'planting_plan_executions'
      AND CONSTRAINT_NAME = 'fk_planting_plan_executions_cycle'
  ),
  'ALTER TABLE planting_plan_executions ADD CONSTRAINT fk_planting_plan_executions_cycle FOREIGN KEY (crop_cycle_id) REFERENCES crop_cycles (id) ON DELETE SET NULL',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = IF(
  NOT EXISTS (
    SELECT 1
    FROM information_schema.REFERENTIAL_CONSTRAINTS
    WHERE CONSTRAINT_SCHEMA = @schema_name
      AND TABLE_NAME = 'planting_plan_executions'
      AND CONSTRAINT_NAME = 'fk_planting_plan_executions_unit'
  ),
  'ALTER TABLE planting_plan_executions ADD CONSTRAINT fk_planting_plan_executions_unit FOREIGN KEY (planting_unit_id) REFERENCES planting_units (id) ON DELETE SET NULL',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
