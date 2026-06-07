import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../shared/widgets/card_panel.dart';
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
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 160),
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
      padding: const EdgeInsets.all(18),
      borderColor: Colors.transparent,
      radius: 16,
      gradient: const LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [AppColors.navy, AppColors.navy3],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                '芽芽今日汇总',
                style: TextStyle(
                  color: Color(0xC7FFFFFF),
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 0,
                ),
              ),
              Text(
                '07:30 更新',
                style: TextStyle(
                  color: Color(0x99FFFFFF),
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 0,
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              const Expanded(
                child: Text(
                  '今天先做东棚授粉复核，\n傍晚前处理降温风险。',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 22,
                    height: 30 / 22,
                    fontWeight: FontWeight.w900,
                    letterSpacing: 0,
                  ),
                ),
              ),
              Container(
                width: 34,
                height: 34,
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.14),
                  borderRadius: BorderRadius.circular(17),
                ),
                child: const Icon(
                  LucideIcons.arrowRight,
                  size: 18,
                  color: Colors.white,
                ),
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
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
        shadow: true,
        borderColor: Colors.transparent,
        background: Colors.white,
        radius: 16,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: AppTextStyles.small,
            ),
            const SizedBox(height: 6),
            Row(
              children: [
                Text(value, style: AppTextStyles.metric.copyWith(color: color)),
                const SizedBox(width: 6),
                if (value == '24℃')
                  const Icon(LucideIcons.sunMedium,
                      size: 14, color: AppColors.subtle)
                else if (value == '8℃')
                  const Icon(LucideIcons.moon,
                      size: 14, color: AppColors.subtle)
                else
                  Container(
                    width: 6,
                    height: 6,
                    decoration: const BoxDecoration(
                      color: AppColors.green,
                      shape: BoxShape.circle,
                    ),
                  ),
              ],
            ),
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
          SectionHeading(title: '今天要处理  3'),
          SizedBox(height: 14),
          TaskRow(
            icon: LucideIcons.clipboardCheck,
            tone: AppColors.blueSoft,
            color: AppColors.blue,
            title: '东棚 1-6 号授粉复核',
            subtitle: '10:30  ·  3 人',
            tag: '作业',
            tagMuted: true,
          ),
          TaskDivider(),
          TaskRow(
            icon: LucideIcons.triangleAlert,
            tone: AppColors.amberSoft,
            color: AppColors.amber,
            title: '夜间降温防护',
            subtitle: '最低 8℃，傍晚前',
            tag: '风险',
            tagMuted: false,
          ),
          TaskDivider(),
          TaskRow(
            icon: LucideIcons.walletCards,
            tone: AppColors.tealSoft,
            color: AppColors.teal,
            title: '昨日人工工资待确认',
            subtitle: '2 笔 · ¥860 · 可直接结算',
            tag: '账单',
            tagMuted: true,
          ),
          SizedBox(height: 14),
          _ViewAllTasksRow(),
        ],
      ),
    );
  }
}

class _ViewAllTasksRow extends StatelessWidget {
  const _ViewAllTasksRow();

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Text(
          '查看全部任务',
          style: AppTextStyles.small.copyWith(
            color: AppColors.muted,
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(width: 4),
        const Icon(
          LucideIcons.chevronRight,
          size: 14,
          color: AppColors.muted,
        ),
      ],
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
    this.tagMuted = false,
  });

  final IconData icon;
  final Color tone;
  final Color color;
  final String title;
  final String subtitle;
  final String tag;
  final bool tagMuted;

  @override
  Widget build(BuildContext context) {
    final tagBg = tagMuted ? AppColors.surface3 : tone;
    final tagFg = tagMuted ? AppColors.muted : color;
    return Row(
      children: [
        Container(
          width: 38,
          height: 38,
          decoration: BoxDecoration(
            color: tone,
            borderRadius: BorderRadius.circular(10),
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
                  fontSize: 14,
                  height: 20 / 14,
                  fontWeight: FontWeight.w800,
                  color: AppColors.ink,
                  letterSpacing: 0,
                ),
              ),
              const SizedBox(height: 2),
              Text(subtitle, style: AppTextStyles.small),
            ],
          ),
        ),
        const SizedBox(width: 8),
        Container(
          height: 24,
          padding: const EdgeInsets.symmetric(horizontal: 9),
          decoration: BoxDecoration(
            color: tagBg,
            borderRadius: BorderRadius.circular(8),
          ),
          child: Center(
            child: Text(
              tag,
              style: AppTextStyles.small.copyWith(
                color: tagFg,
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
        ),
      ],
    );
  }
}
