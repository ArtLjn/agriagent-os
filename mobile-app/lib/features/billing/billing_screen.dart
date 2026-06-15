import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../data/repositories/billing_repository.dart';
import '../../shared/assets/app_assets.dart';
import '../../shared/widgets/card_panel.dart';
import '../../shared/widgets/date_filter_sheet.dart';
import '../../shared/widgets/reference_page.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';
import 'billing_controller.dart';

part 'billing_summary_widgets.dart';

class BillingScreen extends StatefulWidget {
  const BillingScreen({
    super.key,
    required this.repository,
    this.refreshKey = 0,
  });

  final BillingRepository repository;
  final int refreshKey;

  @override
  State<BillingScreen> createState() => _BillingScreenState();
}

class _BillingScreenState extends State<BillingScreen> {
  late Future<BillingViewModel> _future = _load();

  @override
  void didUpdateWidget(covariant BillingScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.refreshKey != widget.refreshKey ||
        oldWidget.repository != widget.repository) {
      _future = _load();
    }
  }

  Future<BillingViewModel> _load() {
    return BillingController(repository: widget.repository).load();
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<BillingViewModel>(
      future: _future,
      builder: (context, snapshot) {
        final model = snapshot.data;
        return ReferencePage(
          headerTrailing:
              const HeaderIconButton(icon: LucideIcons.calendarDays),
          bottomPadding: 118,
          children: [
            const SizedBox(height: 14),
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
              TransactionListCard(
                transactions: model.transactions,
                onViewAll: model.transactions.length > 5
                    ? () {
                        Navigator.of(context).push(
                          MaterialPageRoute<void>(
                            builder: (_) => AllTransactionsScreen(model: model),
                          ),
                        );
                      }
                    : null,
              ),
              const SizedBox(height: 12),
              ReceivableReminderCard(receivables: model.receivables),
              const SizedBox(height: 14),
              const _ManualLedgerButton(),
            ],
          ],
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
  const TransactionListCard({
    super.key,
    required this.transactions,
    this.previewLimit = 5,
    this.onViewAll,
  });

  final List<BillingTransactionViewModel> transactions;
  final int? previewLimit;
  final VoidCallback? onViewAll;

  @override
  Widget build(BuildContext context) {
    final visibleTransactions = previewLimit == null
        ? transactions
        : transactions.take(previewLimit!).toList();
    return CardPanel(
      radius: 18,
      borderColor: AppColors.line,
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Expanded(
                child: Text('最近交易', style: AppTextStyles.dateTitle),
              ),
              if (onViewAll != null)
                TextButton(
                  onPressed: onViewAll,
                  style: TextButton.styleFrom(
                    minimumSize: const Size(0, 36),
                    padding: const EdgeInsets.symmetric(horizontal: 8),
                    tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  ),
                  child: Text(
                    '查看全部',
                    style: AppTextStyles.small.copyWith(
                      color: AppColors.blue,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 10),
          if (transactions.isEmpty)
            const _EmptyLine(text: '暂无交易')
          else
            for (var index = 0;
                index < visibleTransactions.length;
                index++) ...[
              TransactionRow(
                icon: visibleTransactions[index].isIncome
                    ? LucideIcons.badgeDollarSign
                    : LucideIcons.shoppingCart,
                iconColor: visibleTransactions[index].isIncome
                    ? const Color(0xFF08A66A)
                    : const Color(0xFFF97316),
                iconBackground: visibleTransactions[index].isIncome
                    ? const Color(0xFFE9F8F0)
                    : const Color(0xFFFFF3E8),
                title: visibleTransactions[index].title,
                subtitle: visibleTransactions[index].subtitle,
                amount: visibleTransactions[index].amountText,
                amountColor: visibleTransactions[index].isIncome
                    ? const Color(0xFF08A66A)
                    : const Color(0xFFF04438),
              ),
              if (index != visibleTransactions.length - 1)
                const _IndentedDivider(),
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
          Flexible(
            child: FittedBox(
              fit: BoxFit.scaleDown,
              alignment: Alignment.centerRight,
              child: Text(
                amount,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: AppTextStyles.listTitle.copyWith(
                  color: amountColor,
                  fontSize: 17,
                  fontWeight: FontWeight.w800,
                  fontFeatures: const [FontFeature.tabularFigures()],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

enum _TransactionTab {
  all,
  expense,
  income,
  debt,
}

class AllTransactionsScreen extends StatefulWidget {
  const AllTransactionsScreen({super.key, required this.model});

  final BillingViewModel model;

  @override
  State<AllTransactionsScreen> createState() => _AllTransactionsScreenState();
}

class _AllTransactionsScreenState extends State<AllTransactionsScreen> {
  _TransactionTab _tab = _TransactionTab.all;
  DateRangePreset _dateFilter = DateRangePreset.currentMonth;
  DateTime? _selectedMonth;

  List<BillingTransactionViewModel> get _transactions {
    return widget.model.transactions.where((transaction) {
      return _matchesDate(transaction) && _matchesTab(transaction);
    }).toList();
  }

  DateTime get _baseMonth {
    final selected = _selectedMonth;
    if (selected != null) return DateTime(selected.year, selected.month);
    final dated = widget.model.transactions
        .map((transaction) => transaction.recordDate)
        .whereType<DateTime>()
        .toList();
    if (dated.isEmpty) return DateTime.now();
    dated.sort((a, b) => b.compareTo(a));
    return dated.first;
  }

  bool _matchesDate(BillingTransactionViewModel transaction) {
    if (_dateFilter == DateRangePreset.allTime) return true;
    final date = transaction.recordDate;
    if (date == null) return false;
    final range = _activeDateRange;
    return !date.isBefore(range.start) && !date.isAfter(range.end);
  }

  ({DateTime start, DateTime end}) get _activeDateRange {
    final base = DateTime(_baseMonth.year, _baseMonth.month);
    return switch (_dateFilter) {
      DateRangePreset.currentMonth => (
          start: DateTime(base.year, base.month),
          end: DateTime(base.year, base.month + 1, 0),
        ),
      DateRangePreset.previousMonth => (
          start: DateTime(base.year, base.month),
          end: DateTime(base.year, base.month + 1, 0),
        ),
      DateRangePreset.last7Days => (
          start: DateTime(base.year, base.month, _baseMonth.day)
              .subtract(const Duration(days: 6)),
          end: DateTime(base.year, base.month, _baseMonth.day),
        ),
      DateRangePreset.last30Days => (
          start: DateTime(base.year, base.month, _baseMonth.day)
              .subtract(const Duration(days: 29)),
          end: DateTime(base.year, base.month, _baseMonth.day),
        ),
      DateRangePreset.currentYear => (
          start: DateTime(base.year),
          end: DateTime(base.year, 12, 31),
        ),
      DateRangePreset.allTime => (
          start: DateTime(1900),
          end: DateTime(2999),
        ),
    };
  }

  bool _matchesTab(BillingTransactionViewModel transaction) {
    return switch (_tab) {
      _TransactionTab.all => true,
      _TransactionTab.expense => !transaction.isIncome && !transaction.isDebt,
      _TransactionTab.income => transaction.isIncome,
      _TransactionTab.debt => transaction.isDebt,
    };
  }

  void _setTab(_TransactionTab tab) {
    setState(() => _tab = tab);
  }

  Future<void> _pickDateFilter() async {
    final selected = await showDateFilterSheet(
      context: context,
      selected: _dateFilter,
      visibleMonth: _baseMonth,
    );
    if (selected == null) return;
    setState(() {
      _dateFilter = selected.preset;
      _selectedMonth = DateTime(
        selected.visibleMonth.year,
        selected.visibleMonth.month,
      );
    });
  }

  String get _periodTitle {
    if (_dateFilter == DateRangePreset.allTime) return '全部时间';
    if (_dateFilter == DateRangePreset.currentMonth ||
        _dateFilter == DateRangePreset.previousMonth) {
      return '${_baseMonth.year}年${_baseMonth.month}月';
    }
    return _dateFilter.label;
  }

  String get _periodLabel {
    return _dateFilter.label;
  }

  @override
  Widget build(BuildContext context) {
    final transactions = _transactions;
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 118),
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 430),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  _AllTransactionsHeader(
                    onBack: Navigator.of(context).pop,
                    onPickDate: _pickDateFilter,
                  ),
                  const SizedBox(height: 16),
                  _TransactionSummaryStrip(
                    periodLabel: _periodLabel,
                    incomeText: _sumText(transactions, income: true),
                    expenseText: _sumText(transactions, income: false),
                  ),
                  const SizedBox(height: 12),
                  _TransactionFilterBar(selected: _tab, onChanged: _setTab),
                  const SizedBox(height: 12),
                  _AllTransactionsListCard(
                    title: _periodTitle,
                    transactions: transactions,
                  ),
                  const SizedBox(height: 14),
                  const _ManualLedgerButton(),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  String _sumText(
    List<BillingTransactionViewModel> transactions, {
    required bool income,
  }) {
    final total = transactions
        .where((transaction) => income
            ? transaction.isIncome
            : !transaction.isIncome && !transaction.isDebt)
        .fold<num>(0, (sum, transaction) => sum + transaction.amount);
    return _compactTransactionMoney(total);
  }
}

class _AllTransactionsHeader extends StatelessWidget {
  const _AllTransactionsHeader({
    required this.onBack,
    required this.onPickDate,
  });

  final VoidCallback onBack;
  final VoidCallback onPickDate;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 48,
      child: Row(
        children: [
          SizedBox(
            width: 44,
            height: 44,
            child: IconButton(
              onPressed: onBack,
              icon: const Icon(LucideIcons.chevronLeft),
              color: AppColors.ink,
              iconSize: 24,
              padding: EdgeInsets.zero,
            ),
          ),
          const SizedBox(width: 10),
          const Expanded(
            child: Text('全部交易', style: AppTextStyles.title),
          ),
          SizedBox(
            width: 44,
            height: 44,
            child: IconButton(
              key: const Key('transaction-date-filter'),
              onPressed: onPickDate,
              icon: const Icon(LucideIcons.calendarDays),
              color: AppColors.blue,
              iconSize: 24,
              padding: EdgeInsets.zero,
            ),
          ),
        ],
      ),
    );
  }
}

class _TransactionSummaryStrip extends StatelessWidget {
  const _TransactionSummaryStrip({
    required this.periodLabel,
    required this.expenseText,
    required this.incomeText,
  });

  final String periodLabel;
  final String expenseText;
  final String incomeText;

  @override
  Widget build(BuildContext context) {
    return CardPanel(
      radius: 18,
      borderColor: AppColors.line,
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
      child: Row(
        children: [
          Expanded(
            child: _SummaryMetricChip(
              icon: LucideIcons.calendarDays,
              label: periodLabel,
              value: '',
              color: AppColors.blue,
              background: const Color(0xFFEAF3FF),
            ),
          ),
          const _MetricDivider(),
          Expanded(
            child: _SummaryMetricChip(
              icon: LucideIcons.walletCards,
              label: '支出',
              value: expenseText,
              color: const Color(0xFFF05A24),
              background: const Color(0xFFFFF3E8),
            ),
          ),
          const _MetricDivider(),
          Expanded(
            child: _SummaryMetricChip(
              icon: LucideIcons.badgeDollarSign,
              label: '收入',
              value: incomeText,
              color: const Color(0xFF08A66A),
              background: const Color(0xFFE9F8F0),
            ),
          ),
        ],
      ),
    );
  }
}

class _SummaryMetricChip extends StatelessWidget {
  const _SummaryMetricChip({
    required this.icon,
    required this.label,
    required this.value,
    required this.color,
    required this.background,
  });

  final IconData icon;
  final String label;
  final String value;
  final Color color;
  final Color background;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        IconBadge(
          icon: icon,
          color: color,
          background: background,
          size: 38,
          iconSize: 20,
        ),
        const SizedBox(width: 10),
        Flexible(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                label,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: AppTextStyles.small.copyWith(
                  color: AppColors.muted,
                  fontWeight: FontWeight.w700,
                ),
              ),
              if (value.isNotEmpty)
                FittedBox(
                  fit: BoxFit.scaleDown,
                  alignment: Alignment.centerLeft,
                  child: Text(
                    value,
                    maxLines: 1,
                    softWrap: false,
                    style: AppTextStyles.listTitle.copyWith(
                      color: color,
                      fontSize: 17,
                      fontFeatures: const [FontFeature.tabularFigures()],
                    ),
                  ),
                ),
            ],
          ),
        ),
      ],
    );
  }
}

class _TransactionFilterBar extends StatelessWidget {
  const _TransactionFilterBar({
    required this.selected,
    required this.onChanged,
  });

  final _TransactionTab selected;
  final ValueChanged<_TransactionTab> onChanged;

  @override
  Widget build(BuildContext context) {
    return CardPanel(
      radius: 18,
      borderColor: AppColors.line,
      padding: const EdgeInsets.all(6),
      child: Row(
        children: [
          Expanded(
            child: _FilterChipLabel(
              key: const Key('transaction-filter-all'),
              text: '全部',
              selected: selected == _TransactionTab.all,
              onTap: () => onChanged(_TransactionTab.all),
            ),
          ),
          Expanded(
            child: _FilterChipLabel(
              key: const Key('transaction-filter-expense'),
              text: '支出',
              selected: selected == _TransactionTab.expense,
              onTap: () => onChanged(_TransactionTab.expense),
            ),
          ),
          Expanded(
            child: _FilterChipLabel(
              key: const Key('transaction-filter-income'),
              text: '收入',
              selected: selected == _TransactionTab.income,
              onTap: () => onChanged(_TransactionTab.income),
            ),
          ),
          Expanded(
            child: _FilterChipLabel(
              key: const Key('transaction-filter-debt'),
              text: '欠款',
              selected: selected == _TransactionTab.debt,
              onTap: () => onChanged(_TransactionTab.debt),
            ),
          ),
        ],
      ),
    );
  }
}

class _FilterChipLabel extends StatelessWidget {
  const _FilterChipLabel({
    super.key,
    required this.text,
    required this.onTap,
    this.selected = false,
  });

  final String text;
  final VoidCallback onTap;
  final bool selected;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(14),
      child: Container(
        height: 42,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: selected ? const Color(0xFFEAF3FF) : Colors.transparent,
          borderRadius: BorderRadius.circular(14),
        ),
        child: Text(
          text,
          style: AppTextStyles.body.copyWith(
            color: selected ? AppColors.blue : AppColors.muted,
            fontWeight: FontWeight.w800,
          ),
        ),
      ),
    );
  }
}

class _AllTransactionsListCard extends StatefulWidget {
  const _AllTransactionsListCard({
    required this.title,
    required this.transactions,
  });

  final String title;
  final List<BillingTransactionViewModel> transactions;

  @override
  State<_AllTransactionsListCard> createState() =>
      _AllTransactionsListCardState();
}

class _AllTransactionsListCardState extends State<_AllTransactionsListCard> {
  final ScrollController _controller = ScrollController();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    const listHeight = 430.0;
    return CardPanel(
      radius: 18,
      borderColor: AppColors.line,
      padding: const EdgeInsets.fromLTRB(16, 16, 10, 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.only(right: 6),
            child: Text(widget.title, style: AppTextStyles.dateTitle),
          ),
          const SizedBox(height: 10),
          if (widget.transactions.isEmpty)
            const _EmptyLine(text: '暂无交易')
          else
            SizedBox(
              height: listHeight,
              child: Scrollbar(
                controller: _controller,
                thumbVisibility: widget.transactions.length > 6,
                child: ListView.separated(
                  controller: _controller,
                  padding: EdgeInsets.zero,
                  itemCount: widget.transactions.length,
                  itemBuilder: (context, index) {
                    final transaction = widget.transactions[index];
                    return TransactionRow(
                      icon: transaction.isIncome
                          ? LucideIcons.badgeDollarSign
                          : LucideIcons.shoppingCart,
                      iconColor: transaction.isIncome
                          ? const Color(0xFF08A66A)
                          : const Color(0xFFF97316),
                      iconBackground: transaction.isIncome
                          ? const Color(0xFFE9F8F0)
                          : const Color(0xFFFFF3E8),
                      title: transaction.title,
                      subtitle: transaction.subtitle,
                      amount: transaction.amountText,
                      amountColor: transaction.isIncome
                          ? const Color(0xFF08A66A)
                          : const Color(0xFFF04438),
                    );
                  },
                  separatorBuilder: (context, index) =>
                      const _IndentedDivider(),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

String _compactTransactionMoney(num value) {
  final abs = value.abs();
  final prefix = value < 0 ? '-¥' : '¥';
  if (abs < 100000) {
    if (abs == abs.roundToDouble()) return '$prefix${abs.toInt()}';
    return '$prefix${abs.toStringAsFixed(2)}';
  }
  final unit = abs >= 100000000 ? '亿' : '万';
  final divisor = unit == '亿' ? 100000000 : 10000;
  final fixed = (abs / divisor).toStringAsFixed(1);
  final text =
      fixed.endsWith('.0') ? fixed.substring(0, fixed.length - 2) : fixed;
  return '$prefix$text$unit';
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
