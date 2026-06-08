import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../shared/widgets/app_icon_tile.dart';
import '../../shared/widgets/card_panel.dart';
import '../../shared/widgets/chip_label.dart';
import '../../shared/widgets/section_heading.dart';
import '../../shared/widgets/status_header.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';

class WorkbenchScreen extends StatelessWidget {
  const WorkbenchScreen({super.key});

  static const commonTools = [
    ToolSpec('新建作业', LucideIcons.filePlus2),
    ToolSpec('种植批次', LucideIcons.layers),
    ToolSpec('工人工资', LucideIcons.usersRound),
    ToolSpec('快速记账', LucideIcons.receipt),
    ToolSpec('欠款管理', LucideIcons.handCoins),
    ToolSpec('农事日志', LucideIcons.notebookTabs),
    ToolSpec('天气预报', LucideIcons.cloudSun),
    ToolSpec('经营报告', LucideIcons.fileText),
  ];

  static const productionTools = [
    ToolSpec('作物模板', LucideIcons.sprout),
    ToolSpec('种植单元', LucideIcons.map),
    ToolSpec('作业类型', LucideIcons.listChecks),
    ToolSpec('近期作业', LucideIcons.calendarDays),
  ];

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Column(
        children: [
          const StatusHeader(
            title: '工作台',
            subtitle: '平台所有功能的快捷入口',
            trailingIcon: LucideIcons.plus,
          ),
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 160),
              child: const Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  ToolsCard(),
                  SizedBox(height: 12),
                  ActiveCyclesCard(),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class ToolsCard extends StatelessWidget {
  const ToolsCard({super.key});

  @override
  Widget build(BuildContext context) {
    return CardPanel(
      padding: const EdgeInsets.fromLTRB(16, 18, 16, 18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SectionHeading(title: '常用功能', action: '编辑'),
          const SizedBox(height: 14),
          _ToolGrid(tools: WorkbenchScreen.commonTools),
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 14),
            child: Divider(height: 1, color: AppColors.lineSoft),
          ),
          SectionHeading(title: '生产管理'),
          const SizedBox(height: 12),
          _ToolGrid(tools: WorkbenchScreen.productionTools),
        ],
      ),
    );
  }
}

class _ToolGrid extends StatelessWidget {
  const _ToolGrid({required this.tools});

  final List<ToolSpec> tools;

  @override
  Widget build(BuildContext context) {
    return GridView.count(
      crossAxisCount: 4,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      mainAxisSpacing: 8,
      crossAxisSpacing: 4,
      childAspectRatio: 0.88,
      children: tools
          .map(
            (tool) => AppIconTile(
              icon: tool.icon,
              label: tool.label,
              tone: IconTone.blue,
            ),
          )
          .toList(),
    );
  }
}

class ActiveCyclesCard extends StatelessWidget {
  const ActiveCyclesCard({super.key});

  @override
  Widget build(BuildContext context) {
    return const CardPanel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SectionHeading(title: '进行中的批次', action: '管理'),
          SizedBox(height: 12),
          CycleProgressCard(
            title: '春茬西瓜 · A 批',
            stage: '授粉期',
            meta: '28 亩 · 12 个种植单元',
            action: '今日复核',
            progress: 0.76,
          ),
          SizedBox(height: 12),
          CycleProgressCard(
            title: '番茄试种 · B 批',
            stage: '缓苗期',
            meta: '6 亩 · 3 个种植单元',
            action: '观察温差',
            progress: 0.38,
          ),
        ],
      ),
    );
  }
}

class CycleProgressCard extends StatelessWidget {
  const CycleProgressCard({
    super.key,
    required this.title,
    required this.stage,
    required this.meta,
    required this.action,
    required this.progress,
  });

  final String title;
  final String stage;
  final String meta;
  final String action;
  final double progress;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.surface3,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppColors.lineSoft),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: const TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w800,
                        color: AppColors.ink,
                        letterSpacing: 0,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(meta, style: AppTextStyles.small),
                  ],
                ),
              ),
              ChipLabel(
                text: stage,
                background: AppColors.greenSoft,
                foreground: AppColors.green,
              ),
            ],
          ),
          const SizedBox(height: 10),
          ClipRRect(
            borderRadius: BorderRadius.circular(999),
            child: LinearProgressIndicator(
              value: progress,
              minHeight: 7,
              backgroundColor: const Color(0xFFE2E9F2),
              valueColor: const AlwaysStoppedAnimation<Color>(
                AppColors.blue,
              ),
            ),
          ),
          const SizedBox(height: 8),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                '${(progress * 100).round()}% 已推进',
                style: AppTextStyles.small.copyWith(color: AppColors.subtle),
              ),
              Text(
                action,
                style: AppTextStyles.small.copyWith(
                  color: AppColors.blue,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class ToolSpec {
  const ToolSpec(this.label, this.icon);

  final String label;
  final IconData icon;
}
