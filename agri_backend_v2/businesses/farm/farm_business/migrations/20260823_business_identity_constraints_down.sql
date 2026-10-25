-- 回滚仅删除本次新增的索引，不删除或合并业务数据。
SET @schema_name = DATABASE();

SELECT COUNT(*) INTO @unit_index_exists
FROM information_schema.statistics
WHERE table_schema = @schema_name
  AND table_name = 'planting_units'
  AND index_name = 'uq_planting_units_farm_cycle_name';

SET @sql = IF(
  @unit_index_exists > 0,
  'ALTER TABLE planting_units DROP INDEX uq_planting_units_farm_cycle_name',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT COUNT(*) INTO @phone_index_exists
FROM information_schema.statistics
WHERE table_schema = @schema_name
  AND table_name = 'workers'
  AND index_name = 'uq_workers_farm_phone';

SET @sql = IF(
  @phone_index_exists > 0,
  'ALTER TABLE workers DROP INDEX uq_workers_farm_phone',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
