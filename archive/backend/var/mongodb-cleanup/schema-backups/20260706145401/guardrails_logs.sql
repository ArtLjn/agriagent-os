CREATE TABLE `guardrails_logs` (
  `id` int NOT NULL AUTO_INCREMENT,
  `farm_id` int NOT NULL,
  `trigger_type` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `trigger_detail` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `source_text` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
