import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../shared/widgets/card_panel.dart';
import '../../shared/widgets/section_heading.dart';
import '../../shared/widgets/status_header.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';

class BillingScreen extends StatelessWidget {
  const BillingScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Column(
        children: [
          const StatusHeader(
            title: '账单',
            subtitle: '经营收支、人工、欠款的核心入口',
            trailingIcon: LucideIcons.search,
          ),
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 112),
              child: const Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  FinanceHeroCard(),
                  SizedBox(height: 14),
                  QuickLedgerActions(),
                  SizedBox(height: 14),
                  CostBreakdownCard(),
                  SizedBox(height: 14),
                  RecentLedgerCard(),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class FinanceHeroCard extends StatelessWidget {
  const FinanceHeroCard({super.key});

  @override
  Widget build(BuildContext context) {
    return const CardPanel(
      padding: EdgeInsets.symmetric(horizontal: 18, vertical: 16),
      borderColor: Colors.transparent,
      gradient: LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [Color(0xFF182033), Color(0xFF29436F)],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '本月净支出',
            style: TextStyle(
              color: Color(0xB8FFFFFF),
              fontSize: 12,
              fontWeight: FontWeight.w600,
              letterSpacing: 0,
            ),
          ),
          SizedBox(height: 6),
          Text(
            '¥18,426',
            style: TextStyle(
              color: Colors.white,
              fontSize: 29,
              height: 1,
              fontWeight: FontWeight.w800,
              letterSpacing: 0,
            ),
          ),
          SizedBox(height: 12),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              FinanceMetric(value: '¥12,800', label: '收入'),
              FinanceMetric(value: '¥31,226', label: '支出'),
              FinanceMetric(value: '¥2,160', label: '欠款'),
            ],
          ),
        ],
      ),
    );
  }
}

class FinanceMetric extends StatelessWidget {
  const FinanceMetric({super.key, required this.value, required this.label});

  final String value;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          value,
          style: const TextStyle(
            color: Colors.white,
            fontSize: 14,
            fontWeight: FontWeight.w800,
            letterSpacing: 0,
          ),
        ),
        Text(
          label,
          style: const TextStyle(
            color: Color(0xADFFFFFF),
            fontSize: 11,
            fontWeight: FontWeight.w600,
            letterSpacing: 0,
          ),
        ),
      ],
    );
  }
}

class QuickLedgerActions extends StatelessWidget {
  const QuickLedgerActions({super.key});

  @override
  Widget build(BuildContext context) {
    return const Row(
      children: [
        Expanded(
          child: LedgerAction(
            icon: LucideIcons.arrowDownLeft,
            label: '记收入',
            color: AppColors.green,
            background: AppColors.greenSoft,
          ),
        ),
        SizedBox(width: 8),
        Expanded(
          child: LedgerAction(
            icon: LucideIcons.scanText,
            label: '智能记账',
            color: AppColors.blue,
            background: AppColors.blueSoft,
          ),
        ),
        SizedBox(width: 8),
        Expanded(
          child: LedgerAction(
            icon: LucideIcons.usersRound,
            label: '结人工',
            color: AppColors.teal,
            background: AppColors.tealSoft,
          ),
        ),
      ],
    );
  }
}

class LedgerAction extends StatelessWidget {
  const LedgerAction({
    super.key,
    required this.icon,
    required this.label,
    required this.color,
    required this.background,
  });

  final IconData icon;
  final String label;
  final Color color;
  final Color background;

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(minHeight: 68),
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 10),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.line),
      ),
      child: Column(
        children: [
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              color: background,
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(icon, size: 18, color: color),
          ),
          const SizedBox(height: 6),
          Text(
            label,
            textAlign: TextAlign.center,
            style: const TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w800,
              color: AppColors.ink,
              letterSpacing: 0,
            ),
          ),
        ],
      ),
    );
  }
}

class CostBreakdownCard extends StatelessWidget {
  const CostBreakdownCard({super.key});

  @override
  Widget build(BuildContext context) {
    return const CardPanel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SectionHeading(title: '成本构成', action: '详情'),
          CostBar(
              label: '人工',
              amount: '¥8,620',
              progress: 0.68,
              color: AppColors.teal),
          CostBar(
              label: '农资',
              amount: '¥6,910',
              progress: 0.54,
              color: AppColors.blue),
          CostBar(
              label: '水肥',
              amount: '¥2,430',
              progress: 0.30,
              color: AppColors.cyan),
        ],
      ),
    );
  }
}

class CostBar extends StatelessWidget {
  const CostBar({
    super.key,
    required this.label,
    required this.amount,
    required this.progress,
    required this.color,
  });

  final String label;
  final String amount;
  final double progress;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 12),
      child: Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(label,
                  style: AppTextStyles.body.copyWith(color: AppColors.ink)),
              Text(
                amount,
                style: const TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w800,
                  color: AppColors.ink,
                  letterSpacing: 0,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          ClipRRect(
            borderRadius: BorderRadius.circular(999),
            child: LinearProgressIndicator(
              value: progress,
              minHeight: 6,
              backgroundColor: AppColors.surface2,
              valueColor: AlwaysStoppedAnimation<Color>(color),
            ),
          ),
        ],
      ),
    );
  }
}

class RecentLedgerCard extends StatelessWidget {
  const RecentLedgerCard({super.key});

  @override
  Widget build(BuildContext context) {
    return const CardPanel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SectionHeading(title: '最近流水', action: '筛选'),
          SizedBox(height: 12),
          LedgerRow(
            icon: LucideIcons.usersRound,
            iconColor: AppColors.teal,
            iconBackground: AppColors.tealSoft,
            title: '授粉人工',
            subtitle: '来自作业单 · 今日',
            amount: '-¥860',
          ),
          SizedBox(height: 12),
          LedgerRow(
            icon: LucideIcons.arrowDownLeft,
            iconColor: AppColors.green,
            iconBackground: AppColors.greenSoft,
            title: '西瓜预售定金',
            subtitle: '客户：王姐',
            amount: '+¥3,000',
            amountColor: AppColors.green,
          ),
        ],
      ),
    );
  }
}

class LedgerRow extends StatelessWidget {
  const LedgerRow({
    super.key,
    required this.icon,
    required this.iconColor,
    required this.iconBackground,
    required this.title,
    required this.subtitle,
    required this.amount,
    this.amountColor = AppColors.ink,
  });

  final IconData icon;
  final Color iconColor;
  final Color iconBackground;
  final String title;
  final String subtitle;
  final String amount;
  final Color amountColor;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Row(
          children: [
            Container(
              width: 36,
              height: 36,
              decoration: BoxDecoration(
                color: iconBackground,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(icon, size: 18, color: iconColor),
            ),
            const SizedBox(width: 10),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w800,
                    color: AppColors.ink,
                    letterSpacing: 0,
                  ),
                ),
                Text(subtitle, style: AppTextStyles.small),
              ],
            ),
          ],
        ),
        Text(
          amount,
          style: TextStyle(
            color: amountColor,
            fontSize: 13,
            fontWeight: FontWeight.w800,
            letterSpacing: 0,
          ),
        ),
      ],
    );
  }
}
