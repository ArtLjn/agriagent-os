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
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 160),
              child: const Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  FinanceHeroCard(),
                  SizedBox(height: 12),
                  QuickLedgerActions(),
                  SizedBox(height: 12),
                  CostBreakdownCard(),
                  SizedBox(height: 12),
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
    return CardPanel(
      padding: const EdgeInsets.all(20),
      borderColor: AppColors.lineSoft,
      background: AppColors.surface,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                '本月净支出',
                style: TextStyle(
                  color: AppColors.muted,
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  letterSpacing: 0,
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: AppColors.greenSoft,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  '较上月 -8%',
                  style: TextStyle(
                    color: AppColors.green,
                    fontSize: 11,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 0,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            '¥18,426',
            style: TextStyle(
              color: AppColors.ink,
              fontSize: 32,
              fontWeight: FontWeight.w800,
              letterSpacing: -0.5,
            ),
          ),
          const SizedBox(height: 20),
          const Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              FinanceMetric(value: '¥12,800', label: '收入', color: AppColors.green),
              FinanceMetric(value: '¥31,226', label: '支出', color: AppColors.ink),
              FinanceMetric(value: '¥2,160', label: '欠款', color: AppColors.amber),
            ],
          ),
        ],
      ),
    );
  }
}

class FinanceMetric extends StatelessWidget {
  const FinanceMetric({
    super.key,
    required this.value,
    required this.label,
    this.color = AppColors.ink,
  });

  final String value;
  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          value,
          style: TextStyle(
            color: color,
            fontSize: 15,
            fontWeight: FontWeight.w800,
            letterSpacing: 0,
          ),
        ),
        const SizedBox(height: 3),
        Text(
          label,
          style: TextStyle(
            color: AppColors.muted,
            fontSize: 12,
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
            emphasized: true,
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
    this.emphasized = false,
  });

  final IconData icon;
  final String label;
  final Color color;
  final Color background;
  final bool emphasized;

  @override
  Widget build(BuildContext context) {
    return CardPanel(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 16),
      shadow: emphasized,
      borderColor: emphasized ? const Color(0x224078FF) : AppColors.lineSoft,
      background: Colors.white,
      radius: 16,
      child: Column(
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: background,
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(icon, size: 20, color: color),
          ),
          const SizedBox(height: 10),
          Text(
            label,
            textAlign: TextAlign.center,
            style: const TextStyle(
              fontSize: 13,
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
      radius: 16,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SectionHeading(title: '成本构成', action: '详情'),
          SizedBox(height: 14),
          CostDonutSummary(),
        ],
      ),
    );
  }
}

class CostDonutSummary extends StatelessWidget {
  const CostDonutSummary({super.key});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        const SizedBox(
          width: 84,
          height: 84,
          child: CustomPaint(painter: CostDonutPainter()),
        ),
        const SizedBox(width: 18),
        Expanded(
          child: Column(
            children: const [
              CostLegend(
                  label: '人工',
                  amount: '¥8,620',
                  percent: '42%',
                  color: AppColors.blue),
              SizedBox(height: 7),
              CostLegend(
                  label: '农资',
                  amount: '¥6,910',
                  percent: '33%',
                  color: AppColors.teal),
              SizedBox(height: 7),
              CostLegend(
                  label: '水肥',
                  amount: '¥2,430',
                  percent: '12%',
                  color: AppColors.cyan),
              SizedBox(height: 7),
              CostLegend(
                  label: '其他',
                  amount: '¥2,566',
                  percent: '13%',
                  color: AppColors.subtle),
            ],
          ),
        ),
      ],
    );
  }
}

class CostLegend extends StatelessWidget {
  const CostLegend({
    super.key,
    required this.label,
    required this.amount,
    required this.percent,
    required this.color,
  });

  final String label;
  final String amount;
  final String percent;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 8,
          height: 8,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        ),
        const SizedBox(width: 10),
        SizedBox(
          width: 36,
          child: Text(
            label,
            style: AppTextStyles.small.copyWith(
              color: AppColors.ink,
              fontWeight: FontWeight.w700,
            ),
          ),
        ),
        const Spacer(),
        Text(
          amount,
          style: AppTextStyles.small.copyWith(
            color: AppColors.ink,
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(width: 12),
        SizedBox(
          width: 36,
          child: Text(
            percent,
            textAlign: TextAlign.right,
            style: AppTextStyles.small.copyWith(color: AppColors.subtle),
          ),
        ),
      ],
    );
  }
}

class CostDonutPainter extends CustomPainter {
  const CostDonutPainter();

  @override
  void paint(Canvas canvas, Size size) {
    final rect = Offset.zero & size;
    final stroke = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 16
      ..strokeCap = StrokeCap.butt;

    const colors = [
      AppColors.blue,
      AppColors.teal,
      AppColors.cyan,
      AppColors.subtle,
    ];
    const values = [0.42, 0.33, 0.12, 0.13];
    var start = -1.5708;
    for (var i = 0; i < values.length; i++) {
      stroke.color = colors[i];
      final sweep = values[i] * 6.28318;
      canvas.drawArc(rect.deflate(8), start, sweep, false, stroke);
      start += sweep;
    }
  }

  @override
  bool shouldRepaint(covariant CostDonutPainter oldDelegate) => false;
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
      padding: const EdgeInsets.only(top: 14),
      child: Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                children: [
                  Container(
                    width: 8,
                    height: 8,
                    decoration:
                        BoxDecoration(color: color, shape: BoxShape.circle),
                  ),
                  const SizedBox(width: 8),
                  Text(label,
                      style: AppTextStyles.body.copyWith(color: AppColors.ink)),
                ],
              ),
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
              minHeight: 7,
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
      radius: 16,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SectionHeading(title: '最近流水', action: '筛选'),
          SizedBox(height: 14),
          LedgerRow(
            icon: LucideIcons.usersRound,
            iconColor: AppColors.teal,
            iconBackground: AppColors.tealSoft,
            title: '授粉人工',
            subtitle: '来自作业单 · 今日',
            amount: '-¥860',
            amountColor: AppColors.amber,
          ),
          Divider(height: 1, color: AppColors.lineSoft),
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
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 14),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Row(
            children: [
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  color: iconBackground,
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Icon(icon, size: 20, color: iconColor),
              ),
              const SizedBox(width: 14),
              Column(
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
                  const SizedBox(height: 2),
                  Text(subtitle, style: AppTextStyles.small),
                ],
              ),
            ],
          ),
          Text(
            amount,
            style: TextStyle(
              color: amountColor,
              fontSize: 14,
              fontWeight: FontWeight.w800,
              letterSpacing: 0,
            ),
          ),
        ],
      ),
    );
  }
}
