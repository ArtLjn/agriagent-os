import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../shared/assets/app_assets.dart';
import '../../shared/widgets/card_panel.dart';
import '../../shared/widgets/reference_page.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';

part 'billing_summary_widgets.dart';

class BillingScreen extends StatelessWidget {
  const BillingScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(20, 20, 20, 118),
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 430),
            child: const Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                ReferenceHeader(
                  showLogo: false,
                  trailing: HeaderIconButton(icon: LucideIcons.calendarDays),
                ),
                SizedBox(height: 20),
                LedgerSummaryCard(),
                SizedBox(height: 12),
                AiFinanceInsightCard(),
                SizedBox(height: 12),
                TransactionListCard(),
                SizedBox(height: 12),
                ReceivableReminderCard(),
                SizedBox(height: 14),
                _ManualLedgerButton(),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class TransactionListCard extends StatelessWidget {
  const TransactionListCard({super.key});

  @override
  Widget build(BuildContext context) {
    return const CardPanel(
      radius: 18,
      borderColor: AppColors.line,
      padding: EdgeInsets.fromLTRB(16, 16, 16, 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('最近交易', style: AppTextStyles.dateTitle),
          SizedBox(height: 10),
          TransactionRow(
            icon: LucideIcons.shoppingCart,
            iconColor: Color(0xFFF97316),
            iconBackground: Color(0xFFFFF3E8),
            title: '饲料采购',
            subtitle: '今天 08:30 · 现金',
            amount: '-1,200',
            amountColor: Color(0xFFF04438),
          ),
          _IndentedDivider(),
          TransactionRow(
            icon: LucideIcons.badgeDollarSign,
            iconColor: Color(0xFF08A66A),
            iconBackground: Color(0xFFE9F8F0),
            title: '牛只销售',
            subtitle: '昨天 14:20 · 银行卡',
            amount: '+8,000',
            amountColor: Color(0xFF08A66A),
          ),
          _IndentedDivider(),
          TransactionRow(
            icon: LucideIcons.userRound,
            iconColor: Color(0xFF1473FF),
            iconBackground: Color(0xFFEAF3FF),
            title: '人工工资',
            subtitle: '5月16日 · 现金',
            amount: '-1,500',
            amountColor: Color(0xFFF04438),
          ),
          _IndentedDivider(),
          TransactionRow(
            icon: LucideIcons.zap,
            iconColor: AppColors.purple,
            iconBackground: AppColors.purpleSoft,
            title: '水电费',
            subtitle: '5月15日 · 微信',
            amount: '-320',
            amountColor: Color(0xFFF04438),
          ),
        ],
      ),
    );
  }
}

class TransactionRow extends StatelessWidget {
  const TransactionRow({
    super.key,
    required this.icon,
    required this.iconColor,
    required this.iconBackground,
    required this.title,
    required this.subtitle,
    required this.amount,
    required this.amountColor,
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
    return SizedBox(
      height: 68,
      child: Row(
        children: [
          IconBadge(
            icon: icon,
            color: iconColor,
            background: iconBackground,
            size: 44,
            iconSize: 22,
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppTextStyles.listTitle.copyWith(
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  subtitle,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppTextStyles.small.copyWith(
                    color: AppColors.subtle,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 12),
          Text(
            amount,
            style: AppTextStyles.listTitle.copyWith(
              color: amountColor,
              fontSize: 17,
              fontWeight: FontWeight.w800,
              fontFeatures: const [FontFeature.tabularFigures()],
            ),
          ),
        ],
      ),
    );
  }
}

class ReceivableReminderCard extends StatelessWidget {
  const ReceivableReminderCard({super.key});

  @override
  Widget build(BuildContext context) {
    return CardPanel(
      radius: 18,
      borderColor: AppColors.line,
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 14),
      child: Row(
        children: [
          const IconBadge(
            icon: LucideIcons.userRound,
            color: Color(0xFF08A66A),
            background: Color(0xFFE9F8F0),
            size: 44,
            iconSize: 22,
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('待收款提醒', style: AppTextStyles.sectionTitle),
                const SizedBox(height: 5),
                Text(
                  '刘老板',
                  style: AppTextStyles.body.copyWith(
                    color: AppColors.ink2,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 1),
                Text(
                  '¥2,800',
                  style: AppTextStyles.sectionTitle.copyWith(
                    color: const Color(0xFFF05A24),
                    fontSize: 20,
                    fontFeatures: const [FontFeature.tabularFigures()],
                  ),
                ),
              ],
            ),
          ),
          Container(
            height: 40,
            padding: const EdgeInsets.symmetric(horizontal: 17),
            decoration: BoxDecoration(
              color: AppColors.surface,
              borderRadius: BorderRadius.circular(999),
              border: Border.all(color: const Color(0xFFD8E2EC)),
            ),
            child: Row(
              children: [
                const Icon(LucideIcons.phone,
                    size: 18, color: Color(0xFF08A66A)),
                const SizedBox(width: 6),
                Text(
                  '拨打',
                  style: AppTextStyles.body.copyWith(
                    color: const Color(0xFF08A66A),
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _ManualLedgerButton extends StatelessWidget {
  const _ManualLedgerButton();

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 56,
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.centerLeft,
          end: Alignment.centerRight,
          colors: [Color(0xFF12B886), Color(0xFF1473FF)],
        ),
        borderRadius: BorderRadius.circular(16),
        boxShadow: const [
          BoxShadow(
            color: Color(0x1A18A679),
            blurRadius: 16,
            offset: Offset(0, 7),
          ),
        ],
      ),
      child: Center(
        child: Text(
          '手动记一笔',
          style: AppTextStyles.sectionTitle.copyWith(
            color: Colors.white,
            fontSize: 18,
          ),
        ),
      ),
    );
  }
}

class _IndentedDivider extends StatelessWidget {
  const _IndentedDivider();

  @override
  Widget build(BuildContext context) {
    return const Padding(
      padding: EdgeInsets.only(left: 58),
      child: Divider(height: 1, color: AppColors.lineSoft),
    );
  }
}
