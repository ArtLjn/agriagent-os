-- 回滚字段命名对齐，保留 planting_plan_executions 中已有数据。
-- 生产环境回滚前必须先回滚应用代码，避免 ORM 继续读取 crop_cycle_id。

SET @schema_name = DATABASE();
SET @has_crop_cycle_id = (
  SELECT COUNT(*)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @schema_name
    AND TABLE_NAME = 'planting_plan_executions'
    AND COLUMN_NAME = 'crop_cycle_id'
);
SET @has_old_cycle_id = (
  SELECT COUNT(*)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @schema_name
    AND TABLE_NAME = 'planting_plan_executions'
    AND COLUMN_NAME = 'cycle_id'
);

SET @sql = IF(
  @has_crop_cycle_id = 1 AND @has_old_cycle_id = 0,
  'ALTER TABLE planting_plan_executions CHANGE COLUMN crop_cycle_id cycle_id INT NULL',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
