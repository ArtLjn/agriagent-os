CREATE TABLE `agent_records` (
  `id` int NOT NULL AUTO_INCREMENT,
  `farm_id` int NOT NULL,
  `user_id` varchar(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `conversation_id` int DEFAULT NULL,
  `cycle_id` int DEFAULT NULL,
  `record_type` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `content` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `meta` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `created_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `conversation_id` (`conversation_id`),
  KEY `cycle_id` (`cycle_id`),
  KEY `ix_agent_records_id` (`id`),
  KEY `ix_agent_records_farm_created` (`farm_id`,`created_at`),
  CONSTRAINT `agent_records_ibfk_1` FOREIGN KEY (`farm_id`) REFERENCES `farms` (`id`),
  CONSTRAINT `agent_records_ibfk_2` FOREIGN KEY (`conversation_id`) REFERENCES `conversations` (`id`),
  CONSTRAINT `agent_records_ibfk_3` FOREIGN KEY (`cycle_id`) REFERENCES `crop_cycles` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=862 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
