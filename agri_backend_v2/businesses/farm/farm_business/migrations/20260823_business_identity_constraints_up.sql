-- 业务身份边界：电话是农场内工人的唯一标识，种植单元名称在农场+茬口内唯一。
-- 发布前先查看以下审计结果；存在重复数据时必须人工处理，迁移不会自动合并或覆盖记录。
SELECT farm_id, phone, COUNT(*) AS duplicate_count
FROM workers
WHERE phone IS NOT NULL
GROUP BY farm_id, phone
HAVING COUNT(*) > 1;

SELECT farm_id, cycle_id, name, COUNT(*) AS duplicate_count
FROM planting_units
GROUP BY farm_id, cycle_id, name
HAVING COUNT(*) > 1;

SET @schema_name = DATABASE();

SELECT COUNT(*) INTO @phone_index_exists
FROM information_schema.statistics
WHERE table_schema = @schema_name
  AND table_name = 'workers'
  AND index_name = 'uq_workers_farm_phone';

SET @sql = IF(
  @phone_index_exists = 0,
  'ALTER TABLE workers ADD UNIQUE KEY uq_workers_farm_phone (farm_id, phone)',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT COUNT(*) INTO @unit_index_exists
FROM information_schema.statistics
WHERE table_schema = @schema_name
  AND table_name = 'planting_units'
  AND index_name = 'uq_planting_units_farm_cycle_name';

SET @sql = IF(
  @unit_index_exists = 0,
  'ALTER TABLE planting_units ADD UNIQUE KEY uq_planting_units_farm_cycle_name (farm_id, cycle_id, name)',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
