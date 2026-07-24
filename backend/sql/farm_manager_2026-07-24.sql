# ************************************************************
# Sequel Ace SQL dump
# 版本号： 20102
#
# https://sequel-ace.com/
# https://github.com/Sequel-Ace/Sequel-Ace
#
# 数据库: farm_manager
# 生成时间: 2026-07-24 06:40:08 +0000
# ************************************************************


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
SET NAMES utf8mb4;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE='NO_AUTO_VALUE_ON_ZERO', SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;


# 转储表 agent_data_flywheel_labels
# ------------------------------------------------------------

DROP TABLE IF EXISTS `agent_data_flywheel_labels`;

CREATE TABLE `agent_data_flywheel_labels` (
  `id` int NOT NULL AUTO_INCREMENT,
  `farm_id` int NOT NULL,
  `sample_id` varchar(160) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `sample_type` varchar(40) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `session_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `turn_id` int DEFAULT NULL,
  `request_id` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `label` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `comment` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `annotator_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'open',
  PRIMARY KEY (`id`),
  KEY `ix_agent_data_flywheel_labels_farm_id` (`farm_id`),
  KEY `ix_agent_data_flywheel_labels_sample_id` (`sample_id`),
  KEY `ix_agent_data_flywheel_labels_sample_type` (`sample_type`),
  KEY `ix_agent_data_flywheel_labels_session_id` (`session_id`),
  KEY `ix_agent_data_flywheel_labels_turn_id` (`turn_id`),
  KEY `ix_agent_data_flywheel_labels_request_id` (`request_id`),
  KEY `ix_agent_data_flywheel_labels_label` (`label`),
  KEY `ix_agent_data_flywheel_labels_annotator_id` (`annotator_id`),
  KEY `ix_agent_data_flywheel_labels_created_at` (`created_at`),
  KEY `ix_agent_data_flywheel_labels_status` (`status`),
  CONSTRAINT `agent_data_flywheel_labels_ibfk_1` FOREIGN KEY (`farm_id`) REFERENCES `farms` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;



# 转储表 agent_pending_plan_steps
# ------------------------------------------------------------

DROP TABLE IF EXISTS `agent_pending_plan_steps`;

CREATE TABLE `agent_pending_plan_steps` (
  `id` int NOT NULL AUTO_INCREMENT,
  `plan_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `step_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `step_index` int NOT NULL,
  `tool_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `params` json NOT NULL,
  `depends_on` json NOT NULL,
  `confirmation_state` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `execution_status` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `result_payload` json DEFAULT NULL,
  `error_payload` json DEFAULT NULL,
  `created_at` datetime DEFAULT (now()),
  `updated_at` datetime DEFAULT (now()),
  `skill_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `params_json` json DEFAULT NULL,
  `status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'pending',
  `requires_confirmation` tinyint(1) NOT NULL DEFAULT '1',
  `confirmation_text` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `result_json` json DEFAULT NULL,
  `error_message` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  PRIMARY KEY (`id`),
  KEY `ix_agent_pending_plan_steps_id` (`id`),
  KEY `ix_agent_pending_plan_steps_plan_id` (`plan_id`),
  KEY `ix_agent_pending_plan_steps_skill_name` (`skill_name`),
  KEY `ix_agent_pending_plan_steps_status` (`status`),
  CONSTRAINT `agent_pending_plan_steps_ibfk_1` FOREIGN KEY (`plan_id`) REFERENCES `agent_pending_plans` (`plan_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;



# 转储表 agent_pending_plans
# ------------------------------------------------------------

DROP TABLE IF EXISTS `agent_pending_plans`;

CREATE TABLE `agent_pending_plans` (
  `id` int NOT NULL AUTO_INCREMENT,
  `plan_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `farm_id` int NOT NULL,
  `session_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `status` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `current_step_index` int NOT NULL,
  `raw_user_input` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `router_decision` json NOT NULL,
  `expires_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT (now()),
  `updated_at` datetime DEFAULT (now()),
  `router_decision_json` json DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_agent_pending_plans_plan_id` (`plan_id`),
  KEY `ix_agent_pending_plans_id` (`id`),
  KEY `ix_agent_pending_plans_farm_id` (`farm_id`),
  KEY `ix_agent_pending_plans_session_id` (`session_id`),
  KEY `ix_agent_pending_plans_status` (`status`),
  KEY `ix_agent_pending_plans_expires_at` (`expires_at`),
  CONSTRAINT `agent_pending_plans_ibfk_1` FOREIGN KEY (`farm_id`) REFERENCES `farms` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;



# 转储表 agent_task_states
# ------------------------------------------------------------

DROP TABLE IF EXISTS `agent_task_states`;

CREATE TABLE `agent_task_states` (
  `id` int NOT NULL AUTO_INCREMENT,
  `task_id` varchar(64) COLLATE utf8mb4_general_ci NOT NULL,
  `farm_id` int NOT NULL,
  `user_id` varchar(64) COLLATE utf8mb4_general_ci NOT NULL,
  `session_id` varchar(64) COLLATE utf8mb4_general_ci NOT NULL,
  `task_type` varchar(64) COLLATE utf8mb4_general_ci NOT NULL,
  `goal` text COLLATE utf8mb4_general_ci NOT NULL,
  `entities_json` json NOT NULL,
  `observations_json` json NOT NULL,
  `missing_information_json` json NOT NULL,
  `next_action` text COLLATE utf8mb4_general_ci,
  `status` varchar(20) COLLATE utf8mb4_general_ci NOT NULL DEFAULT 'active',
  `expires_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT (now()),
  `updated_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_agent_task_states_task_id` (`task_id`),
  KEY `ix_agent_task_states_task_id` (`task_id`),
  KEY `ix_agent_task_states_farm_id` (`farm_id`),
  KEY `ix_agent_task_states_user_id` (`user_id`),
  KEY `ix_agent_task_states_session_id` (`session_id`),
  KEY `ix_agent_task_states_task_type` (`task_type`),
  KEY `ix_agent_task_states_status` (`status`),
  KEY `ix_agent_task_states_expires_at` (`expires_at`),
  KEY `ix_agent_task_states_active_lookup` (`farm_id`,`user_id`,`session_id`,`status`,`updated_at`),
  CONSTRAINT `agent_task_states_ibfk_1` FOREIGN KEY (`farm_id`) REFERENCES `farms` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;



# 转储表 agent_turns
# ------------------------------------------------------------

DROP TABLE IF EXISTS `agent_turns`;

CREATE TABLE `agent_turns` (
  `id` int NOT NULL AUTO_INCREMENT,
  `farm_id` int NOT NULL,
  `session_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `conversation_id` int DEFAULT NULL,
  `request_id` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `user_message_id` int DEFAULT NULL,
  `assistant_message_id` int DEFAULT NULL,
  `input_preview` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `reply_preview` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `intent_count` int DEFAULT NULL,
  `selected_tools_count` int DEFAULT NULL,
  `tool_calls_count` int DEFAULT NULL,
  `token_total` int DEFAULT NULL,
  `latency_ms` int DEFAULT NULL,
  `status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'success',
  `pending_plan_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `event_file` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `event_seq_start` int DEFAULT NULL,
  `event_seq_end` int DEFAULT NULL,
  `event_write_status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'not_started',
  `created_at` datetime DEFAULT NULL,
  `rule_score` float NOT NULL DEFAULT '0',
  `rule_hits` json DEFAULT NULL,
  `risk_score` float NOT NULL DEFAULT '0',
  `risk_dominant_signal` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `risk_severity` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `judge_bad_prob` float DEFAULT NULL,
  `judge_issue_type` varchar(80) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `judge_suggested_label` varchar(80) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `user_message_id` (`user_message_id`),
  KEY `assistant_message_id` (`assistant_message_id`),
  KEY `ix_agent_turns_farm_id` (`farm_id`),
  KEY `ix_agent_turns_session_id` (`session_id`),
  KEY `ix_agent_turns_request_id` (`request_id`),
  KEY `ix_agent_turns_conversation_id` (`conversation_id`),
  KEY `ix_agent_turns_created_at` (`created_at`),
  KEY `ix_agent_turns_pending_plan_id` (`pending_plan_id`),
  KEY `ix_agent_turns_risk_score` (`risk_score`),
  KEY `ix_agent_turns_risk_dominant_signal` (`risk_dominant_signal`),
  KEY `ix_agent_turns_risk_severity` (`risk_severity`),
  KEY `ix_agent_turns_judge_issue_type` (`judge_issue_type`),
  CONSTRAINT `agent_turns_ibfk_1` FOREIGN KEY (`farm_id`) REFERENCES `farms` (`id`),
  CONSTRAINT `agent_turns_ibfk_2` FOREIGN KEY (`conversation_id`) REFERENCES `conversations` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;



# 转储表 alembic_version
# ------------------------------------------------------------

DROP TABLE IF EXISTS `alembic_version`;

CREATE TABLE `alembic_version` (
  `version_num` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`version_num`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;



# 转储表 conversations
# ------------------------------------------------------------

DROP TABLE IF EXISTS `conversations`;

CREATE TABLE `conversations` (
  `id` int NOT NULL AUTO_INCREMENT,
  `farm_id` int NOT NULL,
  `user_id` varchar(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `session_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime DEFAULT (now()),
  `last_active_at` datetime DEFAULT (now()),
  `summary` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `summary_updated_at` datetime DEFAULT NULL,
  `last_turn_id` int DEFAULT NULL,
  `last_event_seq` int DEFAULT NULL,
  `meta_json` json DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_conversations_session_id` (`session_id`),
  KEY `ix_conversations_farm_id` (`farm_id`),
  KEY `ix_conversations_id` (`id`),
  CONSTRAINT `conversations_ibfk_1` FOREIGN KEY (`farm_id`) REFERENCES `farms` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;



# 转储表 cost_categories
# ------------------------------------------------------------

DROP TABLE IF EXISTS `cost_categories`;

CREATE TABLE `cost_categories` (
  `id` int NOT NULL AUTO_INCREMENT,
  `farm_id` int NOT NULL,
  `name` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `type` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `icon` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `sort_order` int NOT NULL,
  `is_default` tinyint(1) NOT NULL,
  `created_at` datetime NOT NULL DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `ix_cost_categories_farm_id` (`farm_id`),
  KEY `ix_cost_categories_id` (`id`),
  CONSTRAINT `fk_cost_categories_farm_id` FOREIGN KEY (`farm_id`) REFERENCES `farms` (`id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;



# 转储表 cost_records
# ------------------------------------------------------------

DROP TABLE IF EXISTS `cost_records`;

CREATE TABLE `cost_records` (
  `id` int NOT NULL AUTO_INCREMENT,
  `farm_id` int NOT NULL,
  `cycle_id` int DEFAULT NULL,
  `record_type` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `category` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `amount` decimal(10,2) NOT NULL,
  `record_date` date NOT NULL,
  `note` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `record_subtype` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `counterparty` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `due_date` date DEFAULT NULL,
  `settled_at` datetime DEFAULT NULL,
  `parent_record_id` int DEFAULT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT (now()),
  `category_id` int DEFAULT NULL,
  `category_name_snapshot` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `source_type` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `source_id` int DEFAULT NULL,
  `source_active_key` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `settled_amount` decimal(10,2) NOT NULL DEFAULT '0.00',
  `settlement_status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'settled',
  `recorded_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_cost_records_active_source` (`farm_id`,`source_type`,`source_id`,`source_active_key`),
  KEY `parent_record_id` (`parent_record_id`),
  KEY `ix_cost_records_id` (`id`),
  KEY `ix_cost_records_farm_date_deleted` (`farm_id`,`record_date`,`deleted_at`),
  KEY `ix_cost_records_farm_type_date` (`farm_id`,`record_type`,`record_date`),
  KEY `fk_cost_records_category_id` (`category_id`),
  KEY `fk_cost_records_cycle_id` (`cycle_id`),
  KEY `ix_cost_records_source` (`source_type`,`source_id`),
  CONSTRAINT `cost_records_ibfk_1` FOREIGN KEY (`farm_id`) REFERENCES `farms` (`id`),
  CONSTRAINT `cost_records_ibfk_2` FOREIGN KEY (`parent_record_id`) REFERENCES `cost_records` (`id`),
  CONSTRAINT `fk_cost_records_category_id` FOREIGN KEY (`category_id`) REFERENCES `cost_categories` (`id`) ON DELETE RESTRICT,
  CONSTRAINT `fk_cost_records_cycle_id` FOREIGN KEY (`cycle_id`) REFERENCES `crop_cycles` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;



# 转储表 crop_cycles
# ------------------------------------------------------------

DROP TABLE IF EXISTS `crop_cycles`;

CREATE TABLE `crop_cycles` (
  `id` int NOT NULL AUTO_INCREMENT,
  `farm_id` int NOT NULL,
  `name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `crop_template_id` int NOT NULL,
  `start_date` date NOT NULL,
  `field_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime DEFAULT (now()),
  `total_area_mu` decimal(10,2) DEFAULT NULL,
  `season` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `batch_note` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `crop_template_id` (`crop_template_id`),
  KEY `ix_crop_cycles_id` (`id`),
  KEY `ix_crop_cycles_farm_status_start` (`farm_id`,`status`,`start_date`),
  CONSTRAINT `crop_cycles_ibfk_1` FOREIGN KEY (`farm_id`) REFERENCES `farms` (`id`),
  CONSTRAINT `crop_cycles_ibfk_2` FOREIGN KEY (`crop_template_id`) REFERENCES `crop_templates` (`id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;



# 转储表 crop_templates
# ------------------------------------------------------------

DROP TABLE IF EXISTS `crop_templates`;

CREATE TABLE `crop_templates` (
  `id` int NOT NULL AUTO_INCREMENT,
  `farm_id` int DEFAULT NULL,
  `name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `variety` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime DEFAULT (now()),
  `category` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `farm_id` (`farm_id`),
  KEY `ix_crop_templates_id` (`id`),
  KEY `ix_crop_templates_farm_name_variety` (`farm_id`,`name`,`variety`),
  CONSTRAINT `crop_templates_ibfk_1` FOREIGN KEY (`farm_id`) REFERENCES `farms` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;



# 转储表 cycle_stages
# ------------------------------------------------------------

DROP TABLE IF EXISTS `cycle_stages`;

CREATE TABLE `cycle_stages` (
  `id` int NOT NULL AUTO_INCREMENT,
  `cycle_id` int NOT NULL,
  `name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `start_date` date NOT NULL,
  `end_date` date NOT NULL,
  `order_index` int NOT NULL,
  `duration_days` int NOT NULL,
  `key_tasks` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `is_current` tinyint(1) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `cycle_id` (`cycle_id`),
  KEY `ix_cycle_stages_id` (`id`),
  CONSTRAINT `cycle_stages_ibfk_1` FOREIGN KEY (`cycle_id`) REFERENCES `crop_cycles` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;



# 转储表 farm_logs
# ------------------------------------------------------------

DROP TABLE IF EXISTS `farm_logs`;

CREATE TABLE `farm_logs` (
  `id` int NOT NULL AUTO_INCREMENT,
  `farm_id` int NOT NULL,
  `cycle_id` int NOT NULL,
  `operation_type` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `operation_date` date NOT NULL,
  `operation_time` datetime DEFAULT NULL,
  `note` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `photo_urls` varchar(2000) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `cycle_id` (`cycle_id`),
  KEY `ix_farm_logs_id` (`id`),
  KEY `ix_farm_logs_farm_operation_date` (`farm_id`,`operation_date`),
  CONSTRAINT `farm_logs_ibfk_1` FOREIGN KEY (`farm_id`) REFERENCES `farms` (`id`),
  CONSTRAINT `farm_logs_ibfk_2` FOREIGN KEY (`cycle_id`) REFERENCES `crop_cycles` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;



# 转储表 farms
# ------------------------------------------------------------

DROP TABLE IF EXISTS `farms`;

CREATE TABLE `farms` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `location` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `user_id` varchar(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime DEFAULT (now()),
  `uid` varchar(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_farms_uid` (`uid`),
  UNIQUE KEY `ix_farms_user_id` (`user_id`),
  KEY `ix_farms_id` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;



# 转储表 feedback_records
# ------------------------------------------------------------

DROP TABLE IF EXISTS `feedback_records`;

CREATE TABLE `feedback_records` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` varchar(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `conversation_message_id` int DEFAULT NULL,
  `rating` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `correction` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `created_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `conversation_message_id` (`conversation_message_id`),
  KEY `ix_feedback_records_user_id` (`user_id`),
  KEY `ix_feedback_records_id` (`id`),
  CONSTRAINT `fk_feedback_records_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;



# 转储表 growth_stages
# ------------------------------------------------------------

DROP TABLE IF EXISTS `growth_stages`;

CREATE TABLE `growth_stages` (
  `id` int NOT NULL AUTO_INCREMENT,
  `crop_template_id` int NOT NULL,
  `name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `duration_days` int NOT NULL,
  `order_index` int NOT NULL,
  `key_tasks` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `crop_template_id` (`crop_template_id`),
  KEY `ix_growth_stages_id` (`id`),
  CONSTRAINT `growth_stages_ibfk_1` FOREIGN KEY (`crop_template_id`) REFERENCES `crop_templates` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;



# 转储表 idempotency_keys
# ------------------------------------------------------------

DROP TABLE IF EXISTS `idempotency_keys`;

CREATE TABLE `idempotency_keys` (
  `key` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `response` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;



# 转储表 labor_entries
# ------------------------------------------------------------

DROP TABLE IF EXISTS `labor_entries`;

CREATE TABLE `labor_entries` (
  `id` int NOT NULL AUTO_INCREMENT,
  `farm_id` int NOT NULL,
  `work_order_id` int NOT NULL,
  `worker_id` int NOT NULL,
  `pay_type` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'daily',
  `quantity` decimal(10,2) NOT NULL DEFAULT '1.00',
  `unit_price` decimal(10,2) NOT NULL,
  `payable_amount` decimal(10,2) NOT NULL,
  `paid_amount` decimal(10,2) NOT NULL DEFAULT '0.00',
  `unpaid_amount` decimal(10,2) NOT NULL DEFAULT '0.00',
  `settlement_status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'unpaid',
  `note` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime DEFAULT (now()),
  `updated_at` datetime DEFAULT NULL,
  `client_request_id` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_labor_entries_farm_client_request` (`farm_id`,`client_request_id`),
  KEY `worker_id` (`worker_id`),
  KEY `work_order_id` (`work_order_id`),
  CONSTRAINT `labor_entries_ibfk_1` FOREIGN KEY (`farm_id`) REFERENCES `farms` (`id`),
  CONSTRAINT `labor_entries_ibfk_2` FOREIGN KEY (`worker_id`) REFERENCES `workers` (`id`),
  CONSTRAINT `labor_entries_ibfk_3` FOREIGN KEY (`work_order_id`) REFERENCES `operation_work_orders` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;



# 转储表 memory_records
# ------------------------------------------------------------

DROP TABLE IF EXISTS `memory_records`;

CREATE TABLE `memory_records` (
  `id` int NOT NULL AUTO_INCREMENT,
  `memory_id` varchar(64) COLLATE utf8mb4_general_ci NOT NULL,
  `farm_id` int NOT NULL,
  `user_id` varchar(64) COLLATE utf8mb4_general_ci NOT NULL,
  `type` varchar(32) COLLATE utf8mb4_general_ci NOT NULL,
  `content` text COLLATE utf8mb4_general_ci NOT NULL,
  `status` varchar(20) COLLATE utf8mb4_general_ci NOT NULL DEFAULT 'confirmed',
  `source` varchar(32) COLLATE utf8mb4_general_ci NOT NULL DEFAULT 'user_explicit',
  `importance` float NOT NULL DEFAULT '0.8',
  `confidence` float NOT NULL DEFAULT '1',
  `superseded_by_id` varchar(64) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `created_at` datetime DEFAULT (now()),
  `updated_at` datetime DEFAULT (now()),
  `archived_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_memory_records_memory_id` (`memory_id`),
  KEY `ix_memory_records_memory_id` (`memory_id`),
  KEY `ix_memory_records_farm_id` (`farm_id`),
  KEY `ix_memory_records_user_id` (`user_id`),
  KEY `ix_memory_records_type` (`type`),
  KEY `ix_memory_records_status` (`status`),
  KEY `ix_memory_records_source` (`source`),
  KEY `ix_memory_records_context_lookup` (`farm_id`,`user_id`,`status`,`importance`,`updated_at`),
  CONSTRAINT `memory_records_ibfk_1` FOREIGN KEY (`farm_id`) REFERENCES `farms` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;



# 转储表 mongo_compensation_tasks
# ------------------------------------------------------------

DROP TABLE IF EXISTS `mongo_compensation_tasks`;

CREATE TABLE `mongo_compensation_tasks` (
  `id` int NOT NULL AUTO_INCREMENT,
  `object_type` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `farm_id` int NOT NULL,
  `business_id` varchar(160) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `mysql_id` int DEFAULT NULL,
  `operation` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `attempts` int NOT NULL,
  `last_error` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `next_retry_at` datetime DEFAULT NULL,
  `completed_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_mongo_compensation_tasks_status_next_retry` (`status`,`next_retry_at`),
  KEY `ix_mongo_compensation_tasks_object_business` (`object_type`,`farm_id`,`business_id`),
  KEY `ix_mongo_compensation_tasks_mysql_id` (`mysql_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;



# 转储表 operation_work_order_units
# ------------------------------------------------------------

DROP TABLE IF EXISTS `operation_work_order_units`;

CREATE TABLE `operation_work_order_units` (
  `id` int NOT NULL AUTO_INCREMENT,
  `work_order_id` int NOT NULL,
  `unit_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_operation_work_order_units_order_unit` (`work_order_id`,`unit_id`),
  KEY `unit_id` (`unit_id`),
  CONSTRAINT `operation_work_order_units_ibfk_1` FOREIGN KEY (`unit_id`) REFERENCES `planting_units` (`id`) ON DELETE CASCADE,
  CONSTRAINT `operation_work_order_units_ibfk_2` FOREIGN KEY (`work_order_id`) REFERENCES `operation_work_orders` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;



# 转储表 operation_work_orders
# ------------------------------------------------------------

DROP TABLE IF EXISTS `operation_work_orders`;

CREATE TABLE `operation_work_orders` (
  `id` int NOT NULL AUTO_INCREMENT,
  `farm_id` int NOT NULL,
  `cycle_id` int DEFAULT NULL,
  `operation_type` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `operation_date` date NOT NULL,
  `scope_type` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'cycle',
  `note` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `photo_urls` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `source_type` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `source_id` int DEFAULT NULL,
  `labor_cost_record_id` int DEFAULT NULL,
  `created_at` datetime DEFAULT (now()),
  `updated_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `cycle_id` (`cycle_id`),
  KEY `farm_id` (`farm_id`),
  KEY `labor_cost_record_id` (`labor_cost_record_id`),
  CONSTRAINT `operation_work_orders_ibfk_1` FOREIGN KEY (`cycle_id`) REFERENCES `crop_cycles` (`id`),
  CONSTRAINT `operation_work_orders_ibfk_2` FOREIGN KEY (`farm_id`) REFERENCES `farms` (`id`),
  CONSTRAINT `operation_work_orders_ibfk_3` FOREIGN KEY (`labor_cost_record_id`) REFERENCES `cost_records` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;



# 转储表 planting_units
# ------------------------------------------------------------

DROP TABLE IF EXISTS `planting_units`;

CREATE TABLE `planting_units` (
  `id` int NOT NULL AUTO_INCREMENT,
  `farm_id` int NOT NULL,
  `cycle_id` int NOT NULL,
  `name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `area_mu` decimal(10,2) DEFAULT NULL,
  `planted_date` date DEFAULT NULL,
  `status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'active',
  `note` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime DEFAULT (now()),
  `updated_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `cycle_id` (`cycle_id`),
  KEY `farm_id` (`farm_id`),
  CONSTRAINT `planting_units_ibfk_1` FOREIGN KEY (`cycle_id`) REFERENCES `crop_cycles` (`id`) ON DELETE CASCADE,
  CONSTRAINT `planting_units_ibfk_2` FOREIGN KEY (`farm_id`) REFERENCES `farms` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;



# 转储表 simulation_results
# ------------------------------------------------------------

DROP TABLE IF EXISTS `simulation_results`;

CREATE TABLE `simulation_results` (
  `id` int NOT NULL AUTO_INCREMENT,
  `run_id` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `farm_id` int NOT NULL,
  `case_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `passed` int NOT NULL,
  `agent_reply` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `errors_json` json DEFAULT NULL,
  `db_diff_json` json DEFAULT NULL,
  `extracted_claims_json` json DEFAULT NULL,
  `latency_ms` int NOT NULL,
  `category` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `user_input` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `pending_action_json` json DEFAULT NULL,
  `expected_db_changes_json` json DEFAULT NULL,
  `created_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `ix_simulation_results_run_id` (`run_id`),
  KEY `fk_simulation_results_farm_id` (`farm_id`),
  CONSTRAINT `fk_simulation_results_farm_id` FOREIGN KEY (`farm_id`) REFERENCES `farms` (`id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;



# 转储表 simulation_runs
# ------------------------------------------------------------

DROP TABLE IF EXISTS `simulation_runs`;

CREATE TABLE `simulation_runs` (
  `id` int NOT NULL AUTO_INCREMENT,
  `run_id` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `farm_id` int NOT NULL,
  `status` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `total` int NOT NULL,
  `passed` int NOT NULL,
  `failed` int NOT NULL,
  `profile` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `error` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `created_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_simulation_runs_run_id` (`run_id`),
  KEY `fk_simulation_runs_farm_id` (`farm_id`),
  CONSTRAINT `fk_simulation_runs_farm_id` FOREIGN KEY (`farm_id`) REFERENCES `farms` (`id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;



# 转储表 token_daily_stats
# ------------------------------------------------------------

DROP TABLE IF EXISTS `token_daily_stats`;

CREATE TABLE `token_daily_stats` (
  `id` int NOT NULL AUTO_INCREMENT,
  `farm_id` int NOT NULL,
  `date` date NOT NULL,
  `model` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `call_type` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `prompt_tokens` int DEFAULT NULL,
  `completion_tokens` int DEFAULT NULL,
  `total_tokens` int DEFAULT NULL,
  `request_count` int DEFAULT NULL,
  `estimated_cost_cny` decimal(10,6) DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL,
  `user_id` varchar(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_token_stats` (`farm_id`,`date`,`model`,`call_type`),
  KEY `ix_token_daily_stats_user_id` (`user_id`),
  CONSTRAINT `fk_token_daily_stats_farm_id` FOREIGN KEY (`farm_id`) REFERENCES `farms` (`id`) ON DELETE RESTRICT,
  CONSTRAINT `fk_token_daily_stats_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;



# 转储表 user_settings
# ------------------------------------------------------------

DROP TABLE IF EXISTS `user_settings`;

CREATE TABLE `user_settings` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` varchar(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `default_city` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `default_lat` float DEFAULT NULL,
  `default_lon` float DEFAULT NULL,
  `created_at` datetime DEFAULT (now()),
  `updated_at` datetime DEFAULT NULL,
  `assistant_role` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'warm',
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_user_settings_user_id` (`user_id`),
  CONSTRAINT `fk_user_settings_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;



# 转储表 users
# ------------------------------------------------------------

DROP TABLE IF EXISTS `users`;

CREATE TABLE `users` (
  `id` varchar(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `phone` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `password_hash` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `nickname` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `avatar_url` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `role` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime DEFAULT (now()),
  `token_monthly_limit` int DEFAULT NULL,
  `token_weekly_limit` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_users_phone` (`phone`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;



# 转储表 workers
# ------------------------------------------------------------

DROP TABLE IF EXISTS `workers`;

CREATE TABLE `workers` (
  `id` int NOT NULL AUTO_INCREMENT,
  `farm_id` int NOT NULL,
  `name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `phone` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `default_pay_type` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'daily',
  `default_unit_price` decimal(10,2) DEFAULT NULL,
  `note` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'active',
  `created_at` datetime DEFAULT (now()),
  `updated_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `farm_id` (`farm_id`),
  CONSTRAINT `workers_ibfk_1` FOREIGN KEY (`farm_id`) REFERENCES `farms` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;




/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;
/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
