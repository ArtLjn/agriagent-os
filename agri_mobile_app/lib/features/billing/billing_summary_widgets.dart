part of 'billing_screen.dart';

class LedgerSummaryCard extends StatelessWidget {
  const LedgerSummaryCard({super.key, required this.model});

  final BillingViewModel model;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(children: [
          const Expanded(child: Text('年度净收益', style: AppTextStyles.body)),
          Text('${DateTime.now().year} 年', style: AppTextStyles.small),
        ]),
        const SizedBox(height: 12),
        Align(
          alignment: Alignment.centerLeft,
          child: FittedBox(
            fit: BoxFit.scaleDown,
            alignment: Alignment.centerLeft,
            child: Text(
              _displayLedgerMoney(model.netProfitText),
              key: const Key('ledger-yearly-balance'),
              maxLines: 1,
              style: TextStyle(
                color: model.isDeficit ? AppColors.red : AppColors.ink,
                fontSize: 48,
                height: 1.15,
                fontWeight: FontWeight.w600,
                letterSpacing: -1.5,
                fontFeatures: const [FontFeature.tabularFigures()],
              ),
            ),
          ),
        ),
        const SizedBox(height: 8),
        const Text('按已记录的收入与支出汇总', style: AppTextStyles.small),
        const SizedBox(height: 24),
        Container(
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            color: AppColors.blueSoft,
            borderRadius: BorderRadius.circular(20),
          ),
          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Expanded(
                child: _LedgerMetric(
                    label: '收入',
                    value: model.incomeText,
                    icon: LucideIcons.arrowDownLeft,
                    color: AppColors.blue)),
            const SizedBox(width: 24),
            Expanded(
                child: _LedgerMetric(
                    label: '支出',
                    value: model.expenseText,
                    icon: LucideIcons.arrowUpRight,
                    color: AppColors.ink)),
          ]),
        ),
        const SizedBox(height: 20),
        Row(children: [
          const Icon(LucideIcons.handCoins, size: 18, color: AppColors.muted),
          const SizedBox(width: 8),
          const Text('欠款', style: AppTextStyles.small),
          Expanded(
              child: Text(_displayLedgerMoney(model.debtText),
                  maxLines: 1,
                  textAlign: TextAlign.right,
                  overflow: TextOverflow.ellipsis,
                  style: AppTextStyles.listTitle)),
        ]),
      ],
    );
  }
}

class _LedgerMetric extends StatelessWidget {
  const _LedgerMetric(
      {required this.label,
      required this.value,
      required this.icon,
      required this.color});

  final String label;
  final String value;
  final IconData icon;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        Icon(icon, size: 16, color: color),
        const SizedBox(width: 4),
        Flexible(child: Text(label, style: AppTextStyles.small)),
      ]),
      const SizedBox(height: 8),
      FittedBox(
          fit: BoxFit.scaleDown,
          alignment: Alignment.centerLeft,
          child: Text(_displayLedgerMoney(value),
              maxLines: 1,
              style: AppTextStyles.metric.copyWith(
                  fontSize: 24,
                  color: color,
                  fontFeatures: const [FontFeature.tabularFigures()]))),
    ]);
  }
}

class FinanceNoteCard extends StatelessWidget {
  const FinanceNoteCard({super.key, required this.model});

  final BillingViewModel model;

  @override
  Widget build(BuildContext context) {
    // 这段提示来自收支规则，不能标为 AI 分析结果。
    return Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const Icon(LucideIcons.lightbulb, color: AppColors.muted, size: 18),
      const SizedBox(width: 12),
      Expanded(
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('经营提示', style: AppTextStyles.body),
        const SizedBox(height: 6),
        Text(model.insightText ?? '持续记下每笔收支，让经营复盘有据可依。',
            style: AppTextStyles.small.copyWith(height: 1.6)),
      ])),
    ]);
  }
}
