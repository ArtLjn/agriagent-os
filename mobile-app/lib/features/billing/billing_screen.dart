import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../data/repositories/billing_repository.dart';
import '../../shared/assets/app_assets.dart';
import '../../shared/widgets/card_panel.dart';
import '../../shared/widgets/reference_page.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';
import 'billing_controller.dart';

part 'billing_summary_widgets.dart';

class BillingScreen extends StatelessWidget {
  const BillingScreen({super.key, required this.repository});

  final BillingRepository repository;

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<BillingViewModel>(
      future: BillingController(repository: repository).load(),
      builder: (context, snapshot) {
        final model = snapshot.data;
        return SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(20, 20, 20, 118),
            child: Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 430),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const ReferenceHeader(
                      showLogo: false,
                      trailing:
                          HeaderIconButton(icon: LucideIcons.calendarDays),
                    ),
                    const SizedBox(height: 20),
                    if (snapshot.connectionState != ConnectionState.done &&
                        model == null)
                      const _BillingStateCard(text: '加载中...')
                    else if (snapshot.hasError && model == null)
                      const _BillingStateCard(text: '数据加载失败，请稍后重试')
                    else ...[
                      LedgerSummaryCard(model: model!),
                      const SizedBox(height: 12),
                      AiFinanceInsightCard(model: model),
                      const SizedBox(height: 12),
                      TransactionListCard(transactions: model.transactions),
                      const SizedBox(height: 12),
                      ReceivableReminderCard(receivables: model.receivables),
                      const SizedBox(height: 14),
                      const _ManualLedgerButton(),
                    ],
                  ],
                ),
              ),
            ),
          ),
        );
      },
    );
  }
}

class _BillingStateCard extends StatelessWidget {
  const _BillingStateCard({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    return CardPanel(
      padding: const EdgeInsets.all(18),
      child: Text(text, style: AppTextStyles.body),
    );
  }
}

class TransactionListCard extends StatelessWidget {
  const TransactionListCard({super.key, required this.transactions});

  final List<BillingTransactionViewModel> transactions;

  @override
  Widget build(BuildContext context) {
    return CardPanel(
      radius: 18,
      borderColor: AppColors.line,
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('最近交易', style: AppTextStyles.dateTitle),
          const SizedBox(height: 10),
          if (transactions.isEmpty)
            const _EmptyLine(text: '暂无交易')
          else
            for (var index = 0; index < transactions.length; index++) ...[
              TransactionRow(
                icon: transactions[index].isIncome
                    ? LucideIcons.badgeDollarSign
                    : LucideIcons.shoppingCart,
                iconColor: transactions[index].isIncome
                    ? const Color(0xFF08A66A)
                    : const Color(0xFFF97316),
                iconBackground: transactions[index].isIncome
                    ? const Color(0xFFE9F8F0)
                    : const Color(0xFFFFF3E8),
                title: transactions[index].title,
                subtitle: transactions[index].subtitle,
                amount: transactions[index].amountText,
                amountColor: transactions[index].isIncome
                    ? const Color(0xFF08A66A)
                    : const Color(0xFFF04438),
              ),
              if (index != transactions.length - 1) const _IndentedDivider(),
            ],
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
  const ReceivableReminderCard({super.key, required this.receivables});

  final List<BillingReceivableViewModel> receivables;

  @override
  Widget build(BuildContext context) {
    final receivable = receivables.isEmpty ? null : receivables.first;
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
                  receivable?.counterparty ?? '暂无待收款',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppTextStyles.body.copyWith(
                    color: AppColors.ink2,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 1),
                Text(
                  receivable?.amountText ?? '¥0',
                  style: AppTextStyles.sectionTitle.copyWith(
                    color: const Color(0xFFF05A24),
                    fontSize: 20,
                    fontFeatures: const [FontFeature.tabularFigures()],
                  ),
                ),
              ],
            ),
          ),
          if (receivable != null)
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

class _EmptyLine extends StatelessWidget {
  const _EmptyLine({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 52,
      child: Align(
        alignment: Alignment.centerLeft,
        child: Text(text,
            style: AppTextStyles.body.copyWith(color: AppColors.subtle)),
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
