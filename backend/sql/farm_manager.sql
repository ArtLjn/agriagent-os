/*
 Navicat Premium Dump SQL

 Source Server         : 阿里云服务器
 Source Server Type    : MySQL
 Source Server Version : 80045 (8.0.45-0ubuntu0.22.04.1)
 Source Host           : 47.98.253.236:3306
 Source Schema         : farm_manager

 Target Server Type    : MySQL
 Target Server Version : 80045 (8.0.45-0ubuntu0.22.04.1)
 File Encoding         : 65001

 Date: 04/06/2026 10:52:44
*/

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for agent_records
-- ----------------------------
DROP TABLE IF EXISTS `agent_records`;
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
  KEY `farm_id` (`farm_id`),
  KEY `conversation_id` (`conversation_id`),
  KEY `cycle_id` (`cycle_id`),
  KEY `ix_agent_records_id` (`id`),
  CONSTRAINT `agent_records_ibfk_1` FOREIGN KEY (`farm_id`) REFERENCES `farms` (`id`),
  CONSTRAINT `agent_records_ibfk_2` FOREIGN KEY (`conversation_id`) REFERENCES `conversations` (`id`),
  CONSTRAINT `agent_records_ibfk_3` FOREIGN KEY (`cycle_id`) REFERENCES `crop_cycles` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=210 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for alembic_version
-- ----------------------------
DROP TABLE IF EXISTS `alembic_version`;
CREATE TABLE `alembic_version` (
  `version_num` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`version_num`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for conversation_messages
-- ----------------------------
DROP TABLE IF EXISTS `conversation_messages`;
CREATE TABLE `conversation_messages` (
  `id` int NOT NULL AUTO_INCREMENT,
  `conversation_id` int NOT NULL,
  `role` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `content` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `meta` text COLLATE utf8mb4_unicode_ci,
  `created_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `conversation_id` (`conversation_id`),
  KEY `ix_conversation_messages_id` (`id`),
  CONSTRAINT `conversation_messages_ibfk_1` FOREIGN KEY (`conversation_id`) REFERENCES `conversations` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=322 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for conversations
-- ----------------------------
DROP TABLE IF EXISTS `conversations`;
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

-- ----------------------------
-- Table structure for cost_categories
-- ----------------------------
DROP TABLE IF EXISTS `cost_categories`;
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
  KEY `ix_cost_categories_id` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=13 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for cost_records
-- ----------------------------
DROP TABLE IF EXISTS `cost_records`;
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
  PRIMARY KEY (`id`),
  KEY `farm_id` (`farm_id`),
  KEY `parent_record_id` (`parent_record_id`),
  KEY `ix_cost_records_id` (`id`),
  CONSTRAINT `cost_records_ibfk_1` FOREIGN KEY (`farm_id`) REFERENCES `farms` (`id`),
  CONSTRAINT `cost_records_ibfk_2` FOREIGN KEY (`parent_record_id`) REFERENCES `cost_records` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=30 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for crop_cycles
-- ----------------------------
DROP TABLE IF EXISTS `crop_cycles`;
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
  KEY `farm_id` (`farm_id`),
  KEY `crop_template_id` (`crop_template_id`),
  KEY `ix_crop_cycles_id` (`id`),
  CONSTRAINT `crop_cycles_ibfk_1` FOREIGN KEY (`farm_id`) REFERENCES `farms` (`id`),
  CONSTRAINT `crop_cycles_ibfk_2` FOREIGN KEY (`crop_template_id`) REFERENCES `crop_templates` (`id`) ON DELETE RESTRICT
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for crop_templates
-- ----------------------------
DROP TABLE IF EXISTS `crop_templates`;
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

-- ----------------------------
-- Table structure for cycle_stages
-- ----------------------------
DROP TABLE IF EXISTS `cycle_stages`;
CREATE TABLE `cycle_stages` (
  `id` int NOT NULL AUTO_INCREMENT,
  `cycle_id` int NOT NULL,
  `name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `start_date` date NOT NULL,
  `end_date` date NOT NULL,
  `order_index` int NOT NULL,
  `duration_days` int NOT NULL,
  `key_tasks` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `is_current` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `cycle_id` (`cycle_id`),
  KEY `ix_cycle_stages_id` (`id`),
  CONSTRAINT `cycle_stages_ibfk_1` FOREIGN KEY (`cycle_id`) REFERENCES `crop_cycles` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=45 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for farm_logs
-- ----------------------------
DROP TABLE IF EXISTS `farm_logs`;
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
  KEY `farm_id` (`farm_id`),
  KEY `cycle_id` (`cycle_id`),
  KEY `ix_farm_logs_id` (`id`),
  CONSTRAINT `farm_logs_ibfk_1` FOREIGN KEY (`farm_id`) REFERENCES `farms` (`id`),
  CONSTRAINT `farm_logs_ibfk_2` FOREIGN KEY (`cycle_id`) REFERENCES `crop_cycles` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for farms
-- ----------------------------
DROP TABLE IF EXISTS `farms`;
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

-- ----------------------------
-- Table structure for feedback_records
-- ----------------------------
DROP TABLE IF EXISTS `feedback_records`;
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
  CONSTRAINT `feedback_records_ibfk_1` FOREIGN KEY (`conversation_message_id`) REFERENCES `conversation_messages` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for growth_stages
-- ----------------------------
DROP TABLE IF EXISTS `growth_stages`;
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

-- ----------------------------
-- Table structure for guardrails_logs
-- ----------------------------
DROP TABLE IF EXISTS `guardrails_logs`;
CREATE TABLE `guardrails_logs` (
  `id` int NOT NULL AUTO_INCREMENT,
  `farm_id` int NOT NULL,
  `trigger_type` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `trigger_detail` text COLLATE utf8mb4_unicode_ci,
  `source_text` text COLLATE utf8mb4_unicode_ci,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for idempotency_keys
-- ----------------------------
DROP TABLE IF EXISTS `idempotency_keys`;
CREATE TABLE `idempotency_keys` (
  `key` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `response` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for simulation_results
-- ----------------------------
DROP TABLE IF EXISTS `simulation_results`;
CREATE TABLE `simulation_results` (
  `id` int NOT NULL AUTO_INCREMENT,
  `run_id` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `farm_id` int NOT NULL,
  `case_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `passed` int NOT NULL,
  `agent_reply` text COLLATE utf8mb4_unicode_ci,
  `errors_json` text COLLATE utf8mb4_unicode_ci,
  `db_diff_json` text COLLATE utf8mb4_unicode_ci,
  `extracted_claims_json` text COLLATE utf8mb4_unicode_ci,
  `latency_ms` int NOT NULL,
  `category` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `user_input` text COLLATE utf8mb4_unicode_ci,
  `pending_action_json` text COLLATE utf8mb4_unicode_ci,
  `expected_db_changes_json` text COLLATE utf8mb4_unicode_ci,
  `created_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `ix_simulation_results_run_id` (`run_id`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for simulation_runs
-- ----------------------------
DROP TABLE IF EXISTS `simulation_runs`;
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
  UNIQUE KEY `ix_simulation_runs_run_id` (`run_id`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for token_daily_stats
-- ----------------------------
DROP TABLE IF EXISTS `token_daily_stats`;
CREATE TABLE `token_daily_stats` (
  `id` int NOT NULL AUTO_INCREMENT,
  `farm_id` int NOT NULL,
  `date` varchar(10) COLLATE utf8mb4_unicode_ci NOT NULL,
  `model` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `call_type` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `prompt_tokens` int DEFAULT NULL,
  `completion_tokens` int DEFAULT NULL,
  `total_tokens` int DEFAULT NULL,
  `request_count` int DEFAULT NULL,
  `estimated_cost_cny` decimal(10,6) DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_token_stats` (`farm_id`,`date`,`model`,`call_type`)
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for trace_records
-- ----------------------------
DROP TABLE IF EXISTS `trace_records`;
CREATE TABLE `trace_records` (
  `id` int NOT NULL AUTO_INCREMENT,
  `request_id` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL,
  `session_id` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `farm_id` int NOT NULL,
  `round_index` int DEFAULT NULL,
  `node_type` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `node_name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `input_data` text COLLATE utf8mb4_unicode_ci,
  `output_data` text COLLATE utf8mb4_unicode_ci,
  `start_time` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `end_time` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `duration_ms` int DEFAULT NULL,
  `token_usage` text COLLATE utf8mb4_unicode_ci,
  `status` varchar(10) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `error_message` text COLLATE utf8mb4_unicode_ci,
  `conversation_message_id` int DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_trace_records_request_id` (`request_id`)
) ENGINE=InnoDB AUTO_INCREMENT=697 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for user_settings
-- ----------------------------
DROP TABLE IF EXISTS `user_settings`;
CREATE TABLE `user_settings` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `default_city` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `default_lat` float DEFAULT NULL,
  `default_lon` float DEFAULT NULL,
  `created_at` datetime DEFAULT (now()),
  `updated_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_user_settings_user_id` (`user_id`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for users
-- ----------------------------
DROP TABLE IF EXISTS `users`;
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

SET FOREIGN_KEY_CHECKS = 1;
