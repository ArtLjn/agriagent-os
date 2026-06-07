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
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 112),
              child: const Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  HomeHeroCard(),
                  SizedBox(height: 14),
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

class HomeHeroCard extends StatelessWidget {
  const HomeHeroCard({super.key});

  @override
  Widget build(BuildContext context) {
    return CardPanel(
      padding: const EdgeInsets.all(18),
      borderColor: const Color(0x294078FF),
      gradient: const LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [Colors.white, Color(0xFFF5F9FF)],
      ),
      child: Stack(
        children: [
          Positioned(
            right: 0,
            top: 52,
            child: Container(
              width: 62,
              height: 62,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(24),
                gradient: const LinearGradient(
                  colors: [Colors.white, Color(0xFFE9F2FF)],
                ),
                boxShadow: const [
                  BoxShadow(
                    color: Color(0x384078FF),
                    blurRadius: 38,
                    offset: Offset(0, 18),
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
              const SizedBox(height: 18),
              const SizedBox(
                width: 248,
                child: Text(
                  '今天先做东棚授粉复核，傍晚前处理降温风险。',
                  style: TextStyle(
                    fontSize: 23,
                    height: 31 / 23,
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
                  WeatherItem(
                      value: '24℃', label: '当前温度', color: AppColors.blue),
                  SizedBox(width: 8),
                  WeatherItem(
                      value: '8℃', label: '夜间最低', color: AppColors.amber),
                  SizedBox(width: 8),
                  WeatherItem(
                      value: '良好', label: '作业窗口', color: AppColors.green),
                ],
              ),
              const SizedBox(height: 16),
              const Row(
                children: [
                  HomeButton(label: '查看建议', primary: true),
                  SizedBox(width: 10),
                  HomeButton(label: '查看天气', primary: false),
                ],
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class WeatherItem extends StatelessWidget {
  const WeatherItem({
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
      child: Container(
        height: 62,
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(
          color: Colors.white.withValues(alpha: 0.78),
          borderRadius: BorderRadius.circular(15),
          border: Border.all(color: const Color(0x144078FF)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              value,
              style: TextStyle(
                fontSize: 18,
                height: 1,
                fontWeight: FontWeight.w800,
                color: color,
                letterSpacing: 0,
              ),
            ),
            const SizedBox(height: 4),
            Text(label, style: AppTextStyles.small),
          ],
        ),
      ),
    );
  }
}

class HomeButton extends StatelessWidget {
  const HomeButton({super.key, required this.label, required this.primary});

  final String label;
  final bool primary;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 38,
      constraints: const BoxConstraints(minWidth: 92),
      padding: const EdgeInsets.symmetric(horizontal: 14),
      decoration: BoxDecoration(
        color: primary ? AppColors.navy : Colors.white,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Center(
        child: Text(
          label,
          style: TextStyle(
            color: primary ? Colors.white : AppColors.blue,
            fontSize: 12,
            fontWeight: FontWeight.w800,
            letterSpacing: 0,
          ),
        ),
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
          SizedBox(height: 12),
          TaskRow(
            icon: LucideIcons.clipboardCheck,
            tone: AppColors.blueSoft,
            color: AppColors.blue,
            title: '东棚 1-6 号授粉复核',
            subtitle: '10:30 · 3 人 · 来自作业单',
          ),
          SizedBox(height: 12),
          TaskRow(
            icon: LucideIcons.triangleAlert,
            tone: AppColors.amberSoft,
            color: AppColors.amber,
            title: '夜间降温防护',
            subtitle: '最低 8℃ · 建议提前覆盖保温',
          ),
          SizedBox(height: 12),
          TaskRow(
            icon: LucideIcons.walletCards,
            tone: AppColors.tealSoft,
            color: AppColors.teal,
            title: '昨日人工工资待确认',
            subtitle: '2 笔 · ¥860 · 可直接结算',
          ),
        ],
      ),
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
  });

  final IconData icon;
  final Color tone;
  final Color color;
  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 36,
          height: 36,
          decoration: BoxDecoration(
            color: tone,
            borderRadius: BorderRadius.circular(12),
          ),
          child: Icon(icon, size: 18, color: color),
        ),
        const SizedBox(width: 10),
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
      ],
    );
  }
}
