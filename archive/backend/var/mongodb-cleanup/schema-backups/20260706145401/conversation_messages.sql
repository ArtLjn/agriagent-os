CREATE TABLE `conversation_messages` (
  `id` int NOT NULL AUTO_INCREMENT,
  `conversation_id` int NOT NULL,
  `role` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `content` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `meta` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `created_at` datetime DEFAULT (now()),
  `turn_id` int DEFAULT NULL,
  `content_hash` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `meta_json` json DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_conversation_messages_id` (`id`),
  KEY `ix_conversation_messages_conversation_created` (`conversation_id`,`created_at`),
  KEY `ix_conversation_messages_turn_id` (`turn_id`),
  CONSTRAINT `conversation_messages_ibfk_1` FOREIGN KEY (`conversation_id`) REFERENCES `conversations` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=1212 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
