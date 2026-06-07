import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../shared/widgets/card_panel.dart';
import '../../shared/widgets/chip_label.dart';
import '../../shared/widgets/section_heading.dart';
import '../../shared/widgets/status_header.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Column(
        children: [
          const StatusHeader(
            title: '今日概览',
            subtitle: '芽芽汇总了天气、建议、作业和账单',
            trailingIcon: LucideIcons.scanLine,
          ),
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 148),
              child: const Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  HomeDecisionCard(),
                  SizedBox(height: 12),
                  TodayFocusStrip(),
                  SizedBox(height: 12),
                  TodayTasksCard(),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class HomeDecisionCard extends StatelessWidget {
  const HomeDecisionCard({super.key});

  @override
  Widget build(BuildContext context) {
    return CardPanel(
      padding: const EdgeInsets.all(20),
      borderColor: const Color(0x1A4078FF),
      gradient: const LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [Colors.white, Color(0xFFF4F8FF)],
      ),
      child: Stack(
        children: [
          Positioned(
            right: -6,
            top: 28,
            child: Container(
              width: 74,
              height: 74,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: AppColors.blueSoft.withValues(alpha: 0.9),
                boxShadow: const [
                  BoxShadow(
                    color: Color(0x224078FF),
                    blurRadius: 32,
                    offset: Offset(0, 14),
                  ),
                ],
              ),
              child: const Icon(LucideIcons.sparkles, color: AppColors.blue),
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  ChipLabel.blue('芽芽今日汇总'),
                  Text('07:30 更新', style: AppTextStyles.small),
                ],
              ),
              const SizedBox(height: 16),
              const SizedBox(
                width: 266,
                child: Text(
                  '今天先做东棚授粉复核，傍晚前处理降温风险。',
                  style: TextStyle(
                    fontSize: 24,
                    height: 31 / 24,
                    fontWeight: FontWeight.w800,
                    color: AppColors.ink,
                    letterSpacing: 0,
                  ),
                ),
              ),
              const SizedBox(height: 8),
              const Text(
                '已结合今日建议、天气预报、最近作业单和未结人工，给出今天的执行顺序。',
                style: AppTextStyles.body,
              ),
              const SizedBox(height: 16),
              const Row(
                children: [
                  HomeButton(
                      label: '查看建议',
                      icon: LucideIcons.listChecks,
                      primary: true),
                  SizedBox(width: 10),
                  HomeButton(
                      label: '查看天气',
                      icon: LucideIcons.cloudSun,
                      primary: false),
                ],
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class TodayFocusStrip extends StatelessWidget {
  const TodayFocusStrip({super.key});

  @override
  Widget build(BuildContext context) {
    return const Row(
      children: [
        FocusMetric(value: '24℃', label: '当前温度', color: AppColors.blue),
        SizedBox(width: 8),
        FocusMetric(value: '8℃', label: '夜间最低', color: AppColors.amber),
        SizedBox(width: 8),
        FocusMetric(value: '良好', label: '作业窗口', color: AppColors.green),
      ],
    );
  }
}

class FocusMetric extends StatelessWidget {
  const FocusMetric({
    super.key,
    required this.value,
    required this.label,
    required this.color,
  });

  final String value;
  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: CardPanel(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
        shadow: false,
        borderColor: AppColors.lineSoft,
        background: AppColors.elevated,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(value, style: AppTextStyles.metric.copyWith(color: color)),
            const SizedBox(height: 4),
            Text(label, style: AppTextStyles.small),
          ],
        ),
      ),
    );
  }
}

class HomeButton extends StatelessWidget {
  const HomeButton({
    super.key,
    required this.label,
    required this.icon,
    required this.primary,
  });

  final String label;
  final IconData icon;
  final bool primary;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 40,
      constraints: const BoxConstraints(minWidth: 104),
      padding: const EdgeInsets.symmetric(horizontal: 14),
      decoration: BoxDecoration(
        color: primary ? AppColors.navy : Colors.white,
        borderRadius: BorderRadius.circular(14),
        border:
            Border.all(color: primary ? AppColors.navy : AppColors.lineSoft),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, size: 15, color: primary ? Colors.white : AppColors.blue),
          const SizedBox(width: 6),
          Text(
            label,
            style: TextStyle(
              color: primary ? Colors.white : AppColors.blue,
              fontSize: 12,
              fontWeight: FontWeight.w800,
              letterSpacing: 0,
            ),
          ),
        ],
      ),
    );
  }
}

class TodayTasksCard extends StatelessWidget {
  const TodayTasksCard({super.key});

  @override
  Widget build(BuildContext context) {
    return const CardPanel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SectionHeading(title: '今天要处理', action: '全部'),
          SizedBox(height: 14),
          TaskRow(
            icon: LucideIcons.clipboardCheck,
            tone: AppColors.blueSoft,
            color: AppColors.blue,
            title: '东棚 1-6 号授粉复核',
            subtitle: '10:30 · 3 人 · 来自作业单',
            tag: '上午',
          ),
          TaskDivider(),
          TaskRow(
            icon: LucideIcons.triangleAlert,
            tone: AppColors.amberSoft,
            color: AppColors.amber,
            title: '夜间降温防护',
            subtitle: '最低 8℃ · 建议提前覆盖保温',
            tag: '傍晚前',
          ),
          TaskDivider(),
          TaskRow(
            icon: LucideIcons.walletCards,
            tone: AppColors.tealSoft,
            color: AppColors.teal,
            title: '昨日人工工资待确认',
            subtitle: '2 笔 · ¥860 · 可直接结算',
            tag: '待确认',
          ),
        ],
      ),
    );
  }
}

class TaskDivider extends StatelessWidget {
  const TaskDivider({super.key});

  @override
  Widget build(BuildContext context) {
    return const Padding(
      padding: EdgeInsets.symmetric(vertical: 10),
      child: Divider(height: 1, color: AppColors.lineSoft),
    );
  }
}

class TaskRow extends StatelessWidget {
  const TaskRow({
    super.key,
    required this.icon,
    required this.tone,
    required this.color,
    required this.title,
    required this.subtitle,
    required this.tag,
  });

  final IconData icon;
  final Color tone;
  final Color color;
  final String title;
  final String subtitle;
  final String tag;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 38,
          height: 38,
          decoration: BoxDecoration(
            color: tone,
            borderRadius: BorderRadius.circular(14),
          ),
          child: Icon(icon, size: 18, color: color),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: const TextStyle(
                  fontSize: 13,
                  height: 18 / 13,
                  fontWeight: FontWeight.w800,
                  color: AppColors.ink,
                  letterSpacing: 0,
                ),
              ),
              Text(subtitle, style: AppTextStyles.small),
            ],
          ),
        ),
        const SizedBox(width: 8),
        Text(
          tag,
          style: AppTextStyles.small.copyWith(
            color: color,
            fontWeight: FontWeight.w800,
          ),
        ),
      ],
    );
  }
}
