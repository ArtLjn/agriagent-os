
/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;
DROP TABLE IF EXISTS `agent_records`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `agent_records` (
  `id` int NOT NULL AUTO_INCREMENT,
  `farm_id` int NOT NULL,
  `user_id` varchar(36) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `conversation_id` int DEFAULT NULL,
  `cycle_id` int DEFAULT NULL,
  `record_type` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `content` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `meta` text COLLATE utf8mb4_unicode_ci,
  `created_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `conversation_id` (`conversation_id`),
  KEY `cycle_id` (`cycle_id`),
  KEY `ix_agent_records_id` (`id`),
  KEY `ix_agent_records_farm_created` (`farm_id`,`created_at`),
  CONSTRAINT `agent_records_ibfk_1` FOREIGN KEY (`farm_id`) REFERENCES `farms` (`id`),
  CONSTRAINT `agent_records_ibfk_2` FOREIGN KEY (`conversation_id`) REFERENCES `conversations` (`id`),
  CONSTRAINT `agent_records_ibfk_3` FOREIGN KEY (`cycle_id`) REFERENCES `crop_cycles` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=210 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `alembic_version`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `alembic_version` (
  `version_num` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`version_num`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `conversation_messages`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `conversation_messages` (
  `id` int NOT NULL AUTO_INCREMENT,
  `conversation_id` int NOT NULL,
  `role` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `content` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `meta` text COLLATE utf8mb4_unicode_ci,
  `created_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `ix_conversation_messages_id` (`id`),
  KEY `ix_conversation_messages_conversation_created` (`conversation_id`,`created_at`),
  CONSTRAINT `conversation_messages_ibfk_1` FOREIGN KEY (`conversation_id`) REFERENCES `conversations` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=322 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `conversations`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `conversations` (
  `id` int NOT NULL AUTO_INCREMENT,
  `farm_id` int NOT NULL,
  `user_id` varchar(36) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `session_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime DEFAULT (now()),
  `last_active_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_conversations_session_id` (`session_id`),
  KEY `ix_conversations_farm_id` (`farm_id`),
  KEY `ix_conversations_id` (`id`),
  CONSTRAINT `conversations_ibfk_1` FOREIGN KEY (`farm_id`) REFERENCES `farms` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=36 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `cost_categories`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `cost_categories` (
  `id` int NOT NULL AUTO_INCREMENT,
  `farm_id` int NOT NULL,
  `name` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `type` varchar(10) COLLATE utf8mb4_unicode_ci NOT NULL,
  `icon` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `sort_order` int NOT NULL,
  `is_default` tinyint(1) NOT NULL,
  `created_at` datetime NOT NULL DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `ix_cost_categories_farm_id` (`farm_id`),
  KEY `ix_cost_categories_id` (`id`),
  CONSTRAINT `fk_cost_categories_farm_id` FOREIGN KEY (`farm_id`) REFERENCES `farms` (`id`) ON DELETE RESTRICT
) ENGINE=InnoDB AUTO_INCREMENT=13 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `cost_records`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `cost_records` (
  `id` int NOT NULL AUTO_INCREMENT,
  `farm_id` int NOT NULL,
  `cycle_id` int DEFAULT NULL,
  `record_type` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `category` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `amount` decimal(10,2) NOT NULL,
  `record_date` date NOT NULL,
  `note` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `record_subtype` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `counterparty` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `due_date` date DEFAULT NULL,
  `settled_at` datetime DEFAULT NULL,
  `parent_record_id` int DEFAULT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT (now()),
  `category_id` int DEFAULT NULL,
  `category_name_snapshot` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `parent_record_id` (`parent_record_id`),
  KEY `ix_cost_records_id` (`id`),
  KEY `ix_cost_records_farm_date_deleted` (`farm_id`,`record_date`,`deleted_at`),
  KEY `ix_cost_records_farm_type_date` (`farm_id`,`record_type`,`record_date`),
  KEY `fk_cost_records_category_id` (`category_id`),
  KEY `fk_cost_records_cycle_id` (`cycle_id`),
  CONSTRAINT `cost_records_ibfk_1` FOREIGN KEY (`farm_id`) REFERENCES `farms` (`id`),
  CONSTRAINT `cost_records_ibfk_2` FOREIGN KEY (`parent_record_id`) REFERENCES `cost_records` (`id`),
  CONSTRAINT `fk_cost_records_category_id` FOREIGN KEY (`category_id`) REFERENCES `cost_categories` (`id`) ON DELETE RESTRICT,
  CONSTRAINT `fk_cost_records_cycle_id` FOREIGN KEY (`cycle_id`) REFERENCES `crop_cycles` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=30 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `crop_cycles`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `crop_cycles` (
  `id` int NOT NULL AUTO_INCREMENT,
  `farm_id` int NOT NULL,
  `name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `crop_template_id` int NOT NULL,
  `start_date` date NOT NULL,
  `field_name` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `status` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `crop_template_id` (`crop_template_id`),
  KEY `ix_crop_cycles_id` (`id`),
  KEY `ix_crop_cycles_farm_status_start` (`farm_id`,`status`,`start_date`),
  CONSTRAINT `crop_cycles_ibfk_1` FOREIGN KEY (`farm_id`) REFERENCES `farms` (`id`),
  CONSTRAINT `crop_cycles_ibfk_2` FOREIGN KEY (`crop_template_id`) REFERENCES `crop_templates` (`id`) ON DELETE RESTRICT
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `crop_templates`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `crop_templates` (
  `id` int NOT NULL AUTO_INCREMENT,
  `farm_id` int NOT NULL,
  `name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `variety` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `farm_id` (`farm_id`),
  KEY `ix_crop_templates_id` (`id`),
  CONSTRAINT `crop_templates_ibfk_1` FOREIGN KEY (`farm_id`) REFERENCES `farms` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=13 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `cycle_stages`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `cycle_stages` (
  `id` int NOT NULL AUTO_INCREMENT,
  `cycle_id` int NOT NULL,
  `name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `start_date` date NOT NULL,
  `end_date` date NOT NULL,
  `order_index` int NOT NULL,
  `duration_days` int NOT NULL,
  `key_tasks` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `is_current` tinyint(1) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `cycle_id` (`cycle_id`),
  KEY `ix_cycle_stages_id` (`id`),
  CONSTRAINT `cycle_stages_ibfk_1` FOREIGN KEY (`cycle_id`) REFERENCES `crop_cycles` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=45 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `farm_logs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `farm_logs` (
  `id` int NOT NULL AUTO_INCREMENT,
  `farm_id` int NOT NULL,
  `cycle_id` int NOT NULL,
  `operation_type` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `operation_date` date NOT NULL,
  `operation_time` datetime DEFAULT NULL,
  `note` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `photo_urls` varchar(2000) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `cycle_id` (`cycle_id`),
  KEY `ix_farm_logs_id` (`id`),
  KEY `ix_farm_logs_farm_operation_date` (`farm_id`,`operation_date`),
  CONSTRAINT `farm_logs_ibfk_1` FOREIGN KEY (`farm_id`) REFERENCES `farms` (`id`),
  CONSTRAINT `farm_logs_ibfk_2` FOREIGN KEY (`cycle_id`) REFERENCES `crop_cycles` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `farms`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `farms` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `location` varchar(200) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `user_id` varchar(36) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime DEFAULT (now()),
  `uid` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_farms_uid` (`uid`),
  UNIQUE KEY `ix_farms_user_id` (`user_id`),
  KEY `ix_farms_id` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `feedback_records`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `feedback_records` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `conversation_message_id` int DEFAULT NULL,
  `rating` varchar(10) COLLATE utf8mb4_unicode_ci NOT NULL,
  `correction` text COLLATE utf8mb4_unicode_ci,
  `created_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `conversation_message_id` (`conversation_message_id`),
  KEY `ix_feedback_records_user_id` (`user_id`),
  KEY `ix_feedback_records_id` (`id`),
  CONSTRAINT `feedback_records_ibfk_1` FOREIGN KEY (`conversation_message_id`) REFERENCES `conversation_messages` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_feedback_records_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `growth_stages`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `growth_stages` (
  `id` int NOT NULL AUTO_INCREMENT,
  `crop_template_id` int NOT NULL,
  `name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `duration_days` int NOT NULL,
  `order_index` int NOT NULL,
  `key_tasks` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `crop_template_id` (`crop_template_id`),
  KEY `ix_growth_stages_id` (`id`),
  CONSTRAINT `growth_stages_ibfk_1` FOREIGN KEY (`crop_template_id`) REFERENCES `crop_templates` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=51 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `guardrails_logs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `guardrails_logs` (
  `id` int NOT NULL AUTO_INCREMENT,
  `farm_id` int NOT NULL,
  `trigger_type` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `trigger_detail` text COLLATE utf8mb4_unicode_ci,
  `source_text` text COLLATE utf8mb4_unicode_ci,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `idempotency_keys`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `idempotency_keys` (
  `key` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `response` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `simulation_results`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `simulation_results` (
  `id` int NOT NULL AUTO_INCREMENT,
  `run_id` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `farm_id` int NOT NULL,
  `case_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `passed` int NOT NULL,
  `agent_reply` text COLLATE utf8mb4_unicode_ci,
  `errors_json` json DEFAULT NULL,
  `db_diff_json` json DEFAULT NULL,
  `extracted_claims_json` json DEFAULT NULL,
  `latency_ms` int NOT NULL,
  `category` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `user_input` text COLLATE utf8mb4_unicode_ci,
  `pending_action_json` json DEFAULT NULL,
  `expected_db_changes_json` json DEFAULT NULL,
  `created_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `ix_simulation_results_run_id` (`run_id`),
  KEY `fk_simulation_results_farm_id` (`farm_id`),
  CONSTRAINT `fk_simulation_results_farm_id` FOREIGN KEY (`farm_id`) REFERENCES `farms` (`id`) ON DELETE RESTRICT
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `simulation_runs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `simulation_runs` (
  `id` int NOT NULL AUTO_INCREMENT,
  `run_id` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `farm_id` int NOT NULL,
  `status` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL,
  `total` int NOT NULL,
  `passed` int NOT NULL,
  `failed` int NOT NULL,
  `profile` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `error` text COLLATE utf8mb4_unicode_ci,
  `created_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_simulation_runs_run_id` (`run_id`),
  KEY `fk_simulation_runs_farm_id` (`farm_id`),
  CONSTRAINT `fk_simulation_runs_farm_id` FOREIGN KEY (`farm_id`) REFERENCES `farms` (`id`) ON DELETE RESTRICT
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `token_daily_stats`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `token_daily_stats` (
  `id` int NOT NULL AUTO_INCREMENT,
  `farm_id` int NOT NULL,
  `date` date NOT NULL,
  `model` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `call_type` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `prompt_tokens` int DEFAULT NULL,
  `completion_tokens` int DEFAULT NULL,
  `total_tokens` int DEFAULT NULL,
  `request_count` int DEFAULT NULL,
  `estimated_cost_cny` decimal(10,6) DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL,
  `user_id` varchar(36) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_token_stats` (`farm_id`,`date`,`model`,`call_type`),
  KEY `ix_token_daily_stats_user_id` (`user_id`),
  CONSTRAINT `fk_token_daily_stats_farm_id` FOREIGN KEY (`farm_id`) REFERENCES `farms` (`id`) ON DELETE RESTRICT,
  CONSTRAINT `fk_token_daily_stats_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `trace_records`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `trace_records` (
  `id` int NOT NULL AUTO_INCREMENT,
  `request_id` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL,
  `session_id` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `farm_id` int NOT NULL,
  `round_index` int DEFAULT NULL,
  `node_type` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `node_name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `input_data` json DEFAULT NULL,
  `output_data` json DEFAULT NULL,
  `start_time` datetime DEFAULT NULL,
  `end_time` datetime DEFAULT NULL,
  `duration_ms` int DEFAULT NULL,
  `token_usage` json DEFAULT NULL,
  `status` varchar(10) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `error_message` text COLLATE utf8mb4_unicode_ci,
  `conversation_message_id` int DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_trace_records_request_id` (`request_id`),
  KEY `ix_trace_records_request_round_id` (`request_id`,`round_index`,`id`),
  KEY `fk_trace_records_farm_id` (`farm_id`),
  KEY `fk_trace_records_message_id` (`conversation_message_id`),
  CONSTRAINT `fk_trace_records_farm_id` FOREIGN KEY (`farm_id`) REFERENCES `farms` (`id`) ON DELETE RESTRICT,
  CONSTRAINT `fk_trace_records_message_id` FOREIGN KEY (`conversation_message_id`) REFERENCES `conversation_messages` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=697 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `user_settings`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `user_settings` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `default_city` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `default_lat` float DEFAULT NULL,
  `default_lon` float DEFAULT NULL,
  `created_at` datetime DEFAULT (now()),
  `updated_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_user_settings_user_id` (`user_id`),
  CONSTRAINT `fk_user_settings_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `users` (
  `id` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `phone` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `password_hash` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `nickname` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `avatar_url` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `role` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime DEFAULT (now()),
  `token_monthly_limit` int DEFAULT NULL,
  `token_weekly_limit` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_users_phone` (`phone`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

