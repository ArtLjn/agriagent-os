/*
 Navicat Premium Dump SQL

 Source Server         : 腾讯云服务器
 Source Server Type    : MySQL
 Source Server Version : 80046 (8.0.46-0ubuntu0.22.04.2)
 Source Host           : 43.155.217.74:3306
 Source Schema         : farm_manager

 Target Server Type    : MySQL
 Target Server Version : 80046 (8.0.46-0ubuntu0.22.04.2)
 File Encoding         : 65001

 Date: 20/06/2026 14:16:20
*/

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for agent_case_drafts
-- ----------------------------
DROP TABLE IF EXISTS `agent_case_drafts`;
CREATE TABLE `agent_case_drafts` (
  `id` int NOT NULL AUTO_INCREMENT,
  `farm_id` int NOT NULL,
  `draft_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `source_sample_id` varchar(160) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `target_type` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'draft',
  `case_json` json NOT NULL,
  `created_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_agent_case_drafts_draft_id` (`draft_id`),
  KEY `ix_agent_case_drafts_farm_id` (`farm_id`),
  KEY `ix_agent_case_drafts_source_sample_id` (`source_sample_id`),
  KEY `ix_agent_case_drafts_target_type` (`target_type`),
  KEY `ix_agent_case_drafts_status` (`status`),
  KEY `ix_agent_case_drafts_created_by` (`created_by`),
  KEY `ix_agent_case_drafts_created_at` (`created_at`),
  CONSTRAINT `agent_case_drafts_ibfk_1` FOREIGN KEY (`farm_id`) REFERENCES `farms` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for agent_data_flywheel_labels
-- ----------------------------
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
) ENGINE=InnoDB AUTO_INCREMENT=29 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for agent_data_flywheel_prelabels
-- ----------------------------
DROP TABLE IF EXISTS `agent_data_flywheel_prelabels`;
CREATE TABLE `agent_data_flywheel_prelabels` (
  `id` int NOT NULL AUTO_INCREMENT,
  `farm_id` int NOT NULL,
  `sample_id` varchar(160) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `sample_type` varchar(40) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `session_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `turn_id` int DEFAULT NULL,
  `request_id` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `source` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'llm_judge',
  `status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'pending',
  `labels` json NOT NULL,
  `root_cause` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `severity` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `confidence` float NOT NULL DEFAULT '0',
  `reason` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `recommended_fix` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `judge_model` varchar(80) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `prompt_version` varchar(80) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `raw_response` json DEFAULT NULL,
  `accepted_label_ids` json DEFAULT NULL,
  `reviewed_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `reviewed_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_agent_data_flywheel_prelabels_farm_id` (`farm_id`),
  KEY `ix_agent_data_flywheel_prelabels_sample_id` (`sample_id`),
  KEY `ix_agent_data_flywheel_prelabels_sample_type` (`sample_type`),
  KEY `ix_agent_data_flywheel_prelabels_session_id` (`session_id`),
  KEY `ix_agent_data_flywheel_prelabels_turn_id` (`turn_id`),
  KEY `ix_agent_data_flywheel_prelabels_request_id` (`request_id`),
  KEY `ix_agent_data_flywheel_prelabels_source` (`source`),
  KEY `ix_agent_data_flywheel_prelabels_status` (`status`),
  KEY `ix_agent_data_flywheel_prelabels_severity` (`severity`),
  KEY `ix_agent_data_flywheel_prelabels_judge_model` (`judge_model`),
  KEY `ix_agent_data_flywheel_prelabels_prompt_version` (`prompt_version`),
  KEY `ix_agent_data_flywheel_prelabels_reviewed_by` (`reviewed_by`),
  KEY `ix_agent_data_flywheel_prelabels_reviewed_at` (`reviewed_at`),
  KEY `ix_agent_data_flywheel_prelabels_created_at` (`created_at`),
  CONSTRAINT `agent_data_flywheel_prelabels_ibfk_1` FOREIGN KEY (`farm_id`) REFERENCES `farms` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=45 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for agent_pending_plan_steps
-- ----------------------------
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
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for agent_pending_plans
-- ----------------------------
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
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for agent_records
-- ----------------------------
DROP TABLE IF EXISTS `agent_records`;
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
) ENGINE=InnoDB AUTO_INCREMENT=782 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for agent_repair_packs
-- ----------------------------
DROP TABLE IF EXISTS `agent_repair_packs`;
CREATE TABLE `agent_repair_packs` (
  `id` int NOT NULL AUTO_INCREMENT,
  `farm_id` int NOT NULL,
  `pack_id` varchar(80) NOT NULL,
  `fix_target` varchar(40) NOT NULL,
  `labels` json NOT NULL,
  `source_sample_ids` json NOT NULL,
  `source_label_ids` json NOT NULL,
  `status` varchar(20) NOT NULL DEFAULT 'draft',
  `export_path` text,
  `manifest_json` json DEFAULT NULL,
  `export_error` text,
  `repair_note` text,
  `verification_summary` json DEFAULT NULL,
  `created_by` varchar(64) DEFAULT NULL,
  `resolved_by` varchar(64) DEFAULT NULL,
  `resolved_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_agent_repair_packs_pack_id` (`pack_id`),
  KEY `ix_agent_repair_packs_farm_id` (`farm_id`),
  KEY `ix_agent_repair_packs_fix_target` (`fix_target`),
  KEY `ix_agent_repair_packs_status` (`status`),
  KEY `ix_agent_repair_packs_created_by` (`created_by`),
  KEY `ix_agent_repair_packs_resolved_by` (`resolved_by`),
  KEY `ix_agent_repair_packs_resolved_at` (`resolved_at`),
  KEY `ix_agent_repair_packs_created_at` (`created_at`),
  CONSTRAINT `agent_repair_packs_ibfk_1` FOREIGN KEY (`farm_id`) REFERENCES `farms` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ----------------------------
-- Table structure for agent_turns
-- ----------------------------
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
  PRIMARY KEY (`id`),
  KEY `user_message_id` (`user_message_id`),
  KEY `assistant_message_id` (`assistant_message_id`),
  KEY `ix_agent_turns_farm_id` (`farm_id`),
  KEY `ix_agent_turns_session_id` (`session_id`),
  KEY `ix_agent_turns_request_id` (`request_id`),
  KEY `ix_agent_turns_conversation_id` (`conversation_id`),
  KEY `ix_agent_turns_created_at` (`created_at`),
  KEY `ix_agent_turns_pending_plan_id` (`pending_plan_id`),
  CONSTRAINT `agent_turns_ibfk_1` FOREIGN KEY (`farm_id`) REFERENCES `farms` (`id`),
  CONSTRAINT `agent_turns_ibfk_2` FOREIGN KEY (`conversation_id`) REFERENCES `conversations` (`id`) ON DELETE CASCADE,
  CONSTRAINT `agent_turns_ibfk_3` FOREIGN KEY (`user_message_id`) REFERENCES `conversation_messages` (`id`) ON DELETE SET NULL,
  CONSTRAINT `agent_turns_ibfk_4` FOREIGN KEY (`assistant_message_id`) REFERENCES `conversation_messages` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=136 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for alembic_version
-- ----------------------------
DROP TABLE IF EXISTS `alembic_version`;
CREATE TABLE `alembic_version` (
  `version_num` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`version_num`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for conversation_messages
-- ----------------------------
DROP TABLE IF EXISTS `conversation_messages`;
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
) ENGINE=InnoDB AUTO_INCREMENT=1066 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for conversations
-- ----------------------------
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
) ENGINE=InnoDB AUTO_INCREMENT=159 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for cost_categories
-- ----------------------------
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
) ENGINE=InnoDB AUTO_INCREMENT=26 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for cost_records
-- ----------------------------
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
) ENGINE=InnoDB AUTO_INCREMENT=81 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for crop_cycles
-- ----------------------------
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
) ENGINE=InnoDB AUTO_INCREMENT=23 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for crop_templates
-- ----------------------------
DROP TABLE IF EXISTS `crop_templates`;
CREATE TABLE `crop_templates` (
  `id` int NOT NULL AUTO_INCREMENT,
  `farm_id` int DEFAULT NULL,
  `name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `variety` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime DEFAULT (now()),
  `category` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `farm_id` (`farm_id`),
  KEY `ix_crop_templates_id` (`id`),
  KEY `ix_crop_templates_farm_name_variety` (`farm_id`,`name`,`variety`),
  CONSTRAINT `crop_templates_ibfk_1` FOREIGN KEY (`farm_id`) REFERENCES `farms` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=31 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for cycle_stages
-- ----------------------------
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
) ENGINE=InnoDB AUTO_INCREMENT=123 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for farm_logs
-- ----------------------------
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
) ENGINE=InnoDB AUTO_INCREMENT=12 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for farms
-- ----------------------------
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
) ENGINE=InnoDB AUTO_INCREMENT=987658 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for feedback_records
-- ----------------------------
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
  CONSTRAINT `feedback_records_ibfk_1` FOREIGN KEY (`conversation_message_id`) REFERENCES `conversation_messages` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_feedback_records_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for growth_stages
-- ----------------------------
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
) ENGINE=InnoDB AUTO_INCREMENT=134 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for guardrails_logs
-- ----------------------------
DROP TABLE IF EXISTS `guardrails_logs`;
CREATE TABLE `guardrails_logs` (
  `id` int NOT NULL AUTO_INCREMENT,
  `farm_id` int NOT NULL,
  `trigger_type` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `trigger_detail` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `source_text` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for idempotency_keys
-- ----------------------------
DROP TABLE IF EXISTS `idempotency_keys`;
CREATE TABLE `idempotency_keys` (
  `key` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `response` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for labor_entries
-- ----------------------------
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
) ENGINE=InnoDB AUTO_INCREMENT=16 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for operation_work_order_units
-- ----------------------------
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
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for operation_work_orders
-- ----------------------------
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
) ENGINE=InnoDB AUTO_INCREMENT=17 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for planting_units
-- ----------------------------
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
) ENGINE=InnoDB AUTO_INCREMENT=20 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for simulation_results
-- ----------------------------
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
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for simulation_runs
-- ----------------------------
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
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for token_daily_stats
-- ----------------------------
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
) ENGINE=InnoDB AUTO_INCREMENT=97 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for trace_records
-- ----------------------------
DROP TABLE IF EXISTS `trace_records`;
CREATE TABLE `trace_records` (
  `id` int NOT NULL AUTO_INCREMENT,
  `request_id` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `session_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `farm_id` int NOT NULL,
  `round_index` int DEFAULT NULL,
  `node_type` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `node_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `input_data` json DEFAULT NULL,
  `output_data` json DEFAULT NULL,
  `start_time` datetime DEFAULT NULL,
  `end_time` datetime DEFAULT NULL,
  `duration_ms` int DEFAULT NULL,
  `token_usage` json DEFAULT NULL,
  `status` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `error_message` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `conversation_message_id` int DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_trace_records_request_id` (`request_id`),
  KEY `ix_trace_records_request_round_id` (`request_id`,`round_index`,`id`),
  KEY `fk_trace_records_farm_id` (`farm_id`),
  KEY `fk_trace_records_message_id` (`conversation_message_id`),
  CONSTRAINT `fk_trace_records_farm_id` FOREIGN KEY (`farm_id`) REFERENCES `farms` (`id`) ON DELETE RESTRICT,
  CONSTRAINT `fk_trace_records_message_id` FOREIGN KEY (`conversation_message_id`) REFERENCES `conversation_messages` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=3658 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for user_settings
-- ----------------------------
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
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table structure for users
-- ----------------------------
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

-- ----------------------------
-- Table structure for workers
-- ----------------------------
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
) ENGINE=InnoDB AUTO_INCREMENT=22 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET FOREIGN_KEY_CHECKS = 1;
