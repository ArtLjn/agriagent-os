import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../data/repositories/billing_repository.dart';
import '../../shared/widgets/card_panel.dart';
import '../../shared/widgets/date_filter_sheet.dart';
import '../../shared/widgets/reference_page.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';
import 'billing_controller.dart';

part 'billing_summary_widgets.dart';

class _LedgerColors {
  const _LedgerColors._();

  static const ink = Color(0xFF132238);
  static const primaryDark = AppColors.blueDark;
  static const income = AppColors.greenDark;
  static const expense = AppColors.amber;
  static const debt = AppColors.blue;
  static const negative = AppColors.red;
  static const background = AppColors.background;
  static const surfaceTint = Color(0xFFFFFFFF);
  static const surfaceWarm = AppColors.surface3;
  static const line = AppColors.line;
  static const lineSoft = AppColors.lineSoft;
  static const amberSoft = AppColors.amberSoft;
  static const blueSoft = AppColors.blueSoft;
  static const greenSoft = AppColors.greenSoft;
  static const muted = AppColors.muted;
}

IconData _transactionIcon(BillingTransactionViewModel transaction) {
  if (transaction.isIncome) return LucideIcons.badgeDollarSign;
  if (transaction.isDebt) return LucideIcons.userRoundCheck;
  final text = '${transaction.title}${transaction.subtitle}';
  if (text.contains('人工') || text.contains('工资')) return LucideIcons.users;
  if (text.contains('肥') || text.contains('农资')) return LucideIcons.wheat;
  if (text.contains('其他')) return LucideIcons.receiptText;
  return LucideIcons.walletCards;
}

Color _transactionIconColor(BillingTransactionViewModel transaction) {
  if (transaction.isIncome) return _LedgerColors.income;
  if (transaction.isDebt) return _LedgerColors.debt;
  return _LedgerColors.expense;
}

Color _transactionIconBackground(BillingTransactionViewModel transaction) {
  if (transaction.isIncome) return _LedgerColors.greenSoft;
  if (transaction.isDebt) return _LedgerColors.blueSoft;
  return const Color(0xFFFFF7EC);
}

Color _transactionChipColor(BillingTransactionViewModel transaction) {
  if (transaction.isIncome) return _LedgerColors.income;
  if (transaction.isDebt) return _LedgerColors.debt;
  return _LedgerColors.expense;
}

Color _transactionChipBackground(BillingTransactionViewModel transaction) {
  if (transaction.isIncome) return _LedgerColors.greenSoft;
  if (transaction.isDebt) return _LedgerColors.blueSoft;
  return _LedgerColors.amberSoft;
}

class _LedgerSectionCard extends StatelessWidget {
  const _LedgerSectionCard({
    required this.child,
    this.padding = const EdgeInsets.all(18),
    this.radius = 22,
  });

  final Widget child;
  final EdgeInsets padding;
  final double radius;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: _LedgerColors.surfaceTint,
        borderRadius: BorderRadius.circular(radius),
        border: Border.all(color: _LedgerColors.line),
        boxShadow: const [
          BoxShadow(
            color: Color(0x08000000),
            blurRadius: 18,
            offset: Offset(0, 6),
          ),
        ],
      ),
      child: Padding(padding: padding, child: child),
    );
  }
}

class _LedgerRoundIcon extends StatelessWidget {
  const _LedgerRoundIcon({
    required this.icon,
    required this.color,
    required this.background,
    this.size = 42,
    this.iconSize = 19,
  });

  final IconData icon;
  final Color color;
  final Color background;
  final double size;
  final double iconSize;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: background,
        shape: BoxShape.circle,
        border: Border.all(color: Colors.white.withValues(alpha: 0.76)),
        boxShadow: const [
          BoxShadow(
            color: Color(0x081473FF),
            blurRadius: 12,
            offset: Offset(0, 5),
          ),
        ],
      ),
      child: Icon(icon, size: iconSize, color: color),
    );
  }
}

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
          bottomPadding: 200,
          children: [
            const SizedBox(height: 14),
            if (snapshot.connectionState != ConnectionState.done &&
                model == null)
              const _BillingStateCard(text: '加载中...')
            else if (snapshot.hasError && model == null)
              const _BillingStateCard(text: '数据加载失败，请稍后重试')
            else ...[
              LedgerSummaryCard(model: model!),
              const SizedBox(height: 14),
              AiFinanceInsightCard(model: model),
              const SizedBox(height: 14),
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
    return _LedgerSectionCard(
      padding: const EdgeInsets.fromLTRB(18, 18, 18, 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  '最近交易',
                  style: AppTextStyles.dateTitle.copyWith(
                    color: _LedgerColors.ink,
                    fontSize: 19,
                  ),
                ),
              ),
              if (onViewAll != null)
                GestureDetector(
                  onTap: onViewAll,
                  behavior: HitTestBehavior.opaque,
                  child: Container(
                    height: 32,
                    padding: const EdgeInsets.only(left: 12, right: 8),
                    decoration: BoxDecoration(
                      color: AppColors.surface3,
                      borderRadius: BorderRadius.circular(999),
                      border: Border.all(color: _LedgerColors.line),
                    ),
                    child: Row(
                      children: [
                        Text(
                          '查看全部',
                          style: AppTextStyles.small.copyWith(
                            color: _LedgerColors.ink,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                        const SizedBox(width: 3),
                        const Icon(
                          LucideIcons.chevronRight,
                          size: 15,
                          color: _LedgerColors.muted,
                        ),
                      ],
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 12),
          if (transactions.isEmpty)
            const _EmptyLine(text: '暂无交易')
          else
            for (var index = 0;
                index < visibleTransactions.length;
                index++) ...[
              TransactionRow(
                icon: _transactionIcon(visibleTransactions[index]),
                iconColor: _transactionIconColor(visibleTransactions[index]),
                iconBackground:
                    _transactionIconBackground(visibleTransactions[index]),
                title: visibleTransactions[index].title,
                subtitle: visibleTransactions[index].subtitle,
                amount: visibleTransactions[index].amountText,
                amountColor: visibleTransactions[index].isIncome
                    ? _LedgerColors.income
                    : _LedgerColors.negative,
                trendUp: visibleTransactions[index].isIncome,
                chipText: visibleTransactions[index].isDebt
                    ? '欠款'
                    : (visibleTransactions[index].isIncome ? '收入' : '支出'),
                chipColor: _transactionChipColor(visibleTransactions[index]),
                chipBackground:
                    _transactionChipBackground(visibleTransactions[index]),
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
    required this.trendUp,
    this.chipText,
    this.chipColor,
    this.chipBackground,
  });

  final IconData icon;
  final Color iconColor;
  final Color iconBackground;
  final String title;
  final String subtitle;
  final String amount;
  final Color amountColor;
  final bool trendUp;
  final String? chipText;
  final Color? chipColor;
  final Color? chipBackground;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 64,
      child: Row(
        children: [
          _LedgerRoundIcon(
            icon: icon,
            color: iconColor,
            background: iconBackground,
            size: 40,
            iconSize: 18,
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Flexible(
                      child: Text(
                        title,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: AppTextStyles.listTitle.copyWith(
                          color: _LedgerColors.ink,
                          fontSize: 16,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ),
                    if (chipText != null) ...[
                      const SizedBox(width: 8),
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 7,
                          vertical: 2,
                        ),
                        decoration: BoxDecoration(
                          color: chipBackground ?? AppColors.surface3,
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Text(
                          chipText!,
                          style: AppTextStyles.small.copyWith(
                            color: chipColor ?? AppColors.muted,
                            fontSize: 10.5,
                            fontWeight: FontWeight.w700,
                            height: 1.3,
                          ),
                        ),
                      ),
                    ],
                  ],
                ),
                const SizedBox(height: 4),
                Text(
                  subtitle,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppTextStyles.small.copyWith(
                    color: _LedgerColors.muted,
                    fontSize: 12.5,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 10),
          Flexible(
            child: FittedBox(
              fit: BoxFit.scaleDown,
              alignment: Alignment.centerRight,
              child: Row(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.center,
                children: [
                  Text(
                    amount,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: AppTextStyles.listTitle.copyWith(
                      color: amountColor,
                      fontSize: 20,
                      fontWeight: FontWeight.w800,
                      fontFeatures: const [FontFeature.tabularFigures()],
                      letterSpacing: -0.3,
                    ),
                  ),
                ],
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
  DateTime? _customStart;
  DateTime? _customEnd;

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
      DateRangePreset.custom => (
          start: _customStart ?? DateTime(1900),
          end: _customEnd ?? DateTime(2999),
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
      customStart: _customStart,
      customEnd: _customEnd,
    );
    if (selected == null) return;
    setState(() {
      _dateFilter = selected.preset;
      _selectedMonth = DateTime(
        selected.visibleMonth.year,
        selected.visibleMonth.month,
      );
      _customStart = selected.customStart;
      _customEnd = selected.customEnd;
    });
  }

  String get _periodTitle {
    if (_dateFilter == DateRangePreset.allTime) return '全部时间';
    if (_dateFilter == DateRangePreset.custom && _hasCustomRange) {
      return _customRangeText;
    }
    if (_dateFilter == DateRangePreset.currentMonth ||
        _dateFilter == DateRangePreset.previousMonth) {
      return '${_baseMonth.year}年${_baseMonth.month}月';
    }
    return _dateFilter.label;
  }

  String get _periodLabel {
    if (_dateFilter == DateRangePreset.custom && _hasCustomRange) {
      return _customRangeText;
    }
    return _dateFilter.label;
  }

  bool get _hasCustomRange => _customStart != null && _customEnd != null;

  String get _customRangeText {
    if (_customStart == null || _customEnd == null) return '自定义';
    String fmt(DateTime d) =>
        '${d.year}.${d.month.toString().padLeft(2, '0')}.${d.day.toString().padLeft(2, '0')}';
    return '${fmt(_customStart!)} - ${fmt(_customEnd!)}';
  }

  @override
  Widget build(BuildContext context) {
    final transactions = _transactions;
    return Scaffold(
      backgroundColor: _LedgerColors.background,
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
              color: AppColors.ink,
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
    return _LedgerSectionCard(
      padding: const EdgeInsets.fromLTRB(16, 14, 12, 14),
      radius: 20,
      child: IntrinsicHeight(
        child: Row(
          children: [
            Expanded(
              child: _SummaryMetricCell(
                label: '时间范围',
                value: periodLabel,
                valueColor: _LedgerColors.ink,
                fontSize: 15,
              ),
            ),
            const _MetricDivider(height: 38),
            Expanded(
              child: _SummaryMetricCell(
                label: '支出',
                value: expenseText,
                valueColor: _LedgerColors.expense,
              ),
            ),
            const _MetricDivider(height: 38),
            Expanded(
              child: _SummaryMetricCell(
                label: '收入',
                value: incomeText,
                valueColor: _LedgerColors.income,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SummaryMetricCell extends StatelessWidget {
  const _SummaryMetricCell({
    required this.label,
    required this.value,
    required this.valueColor,
    this.fontSize = 17,
  });

  final String label;
  final String value;
  final Color valueColor;
  final double fontSize;

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      crossAxisAlignment: CrossAxisAlignment.center,
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          label,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: AppTextStyles.small.copyWith(
            color: AppColors.muted,
            fontSize: 11.5,
            fontWeight: FontWeight.w700,
            letterSpacing: 0.2,
          ),
        ),
        const SizedBox(height: 4),
        FittedBox(
          fit: BoxFit.scaleDown,
          alignment: Alignment.center,
          child: Text(
            value,
            maxLines: 1,
            softWrap: false,
            textAlign: TextAlign.center,
            style: AppTextStyles.sectionTitle.copyWith(
              color: valueColor,
              fontSize: fontSize,
              fontWeight: FontWeight.w800,
              fontFeatures: const [FontFeature.tabularFigures()],
              letterSpacing: -0.2,
            ),
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
      radius: 16,
      borderColor: _LedgerColors.line,
      background: _LedgerColors.surfaceWarm,
      shadow: true,
      padding: const EdgeInsets.all(5),
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
          color: selected ? _LedgerColors.primaryDark : Colors.transparent,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Text(
          text,
          style: AppTextStyles.body.copyWith(
            color: selected ? Colors.white : AppColors.muted,
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
    return _LedgerSectionCard(
      radius: 20,
      padding: const EdgeInsets.fromLTRB(16, 16, 10, 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.only(right: 8),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    widget.title,
                    style: AppTextStyles.dateTitle.copyWith(
                      color: _LedgerColors.ink,
                      fontSize: 20,
                    ),
                  ),
                ),
                Text(
                  '${widget.transactions.length} 笔',
                  style: AppTextStyles.small.copyWith(
                    color: AppColors.muted,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 4),
          Padding(
            padding: const EdgeInsets.only(right: 8),
            child: Text(
              '点按查看账单详情',
              style: AppTextStyles.small.copyWith(
                color: AppColors.subtle,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
          const SizedBox(height: 12),
          if (widget.transactions.isEmpty)
            const _EmptyLine(text: '暂无交易')
          else if (widget.transactions.length <= 6)
            Column(
              children: [
                for (var index = 0;
                    index < widget.transactions.length;
                    index++) ...[
                  _TransactionDetailRow(
                    transaction: widget.transactions[index],
                    onTap: () => _showTransactionDetail(
                      context,
                      widget.transactions[index],
                    ),
                  ),
                  if (index != widget.transactions.length - 1)
                    const SizedBox(height: 8),
                ],
              ],
            )
          else
            SizedBox(
              height: listHeight,
              child: Scrollbar(
                controller: _controller,
                thumbVisibility: true,
                child: ListView.separated(
                  controller: _controller,
                  padding: EdgeInsets.zero,
                  itemCount: widget.transactions.length,
                  itemBuilder: (context, index) {
                    final transaction = widget.transactions[index];
                    return _TransactionDetailRow(
                      transaction: transaction,
                      onTap: () => _showTransactionDetail(context, transaction),
                    );
                  },
                  separatorBuilder: (context, index) => const SizedBox(
                    height: 8,
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _TransactionDetailRow extends StatelessWidget {
  const _TransactionDetailRow({
    required this.transaction,
    required this.onTap,
  });

  final BillingTransactionViewModel transaction;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final amountColor =
        transaction.isIncome ? _LedgerColors.income : _LedgerColors.negative;
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: Container(
        padding: const EdgeInsets.fromLTRB(10, 9, 10, 9),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: AppColors.lineSoft),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            _LedgerRoundIcon(
              icon: _transactionIcon(transaction),
              color: _transactionIconColor(transaction),
              background: _transactionIconBackground(transaction),
              size: 38,
              iconSize: 18,
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.center,
                    children: [
                      Expanded(
                        child: Text(
                          transaction.title,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: AppTextStyles.sectionTitle.copyWith(
                            color: _LedgerColors.ink,
                            fontSize: 16,
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      ConstrainedBox(
                        constraints: const BoxConstraints(maxWidth: 116),
                        child: FittedBox(
                          fit: BoxFit.scaleDown,
                          alignment: Alignment.centerRight,
                          child: Text(
                            transaction.amountText,
                            maxLines: 1,
                            softWrap: false,
                            style: AppTextStyles.sectionTitle.copyWith(
                              color: amountColor,
                              fontSize: 17,
                              fontFeatures: const [
                                FontFeature.tabularFigures(),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 3),
                  Text(
                    '${transaction.dateText} · ${transaction.typeText} · ${transaction.counterpartyText}',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: AppTextStyles.small.copyWith(
                      color: AppColors.muted,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          '来源：${transaction.sourceText}',
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: AppTextStyles.small.copyWith(
                            color: AppColors.subtle,
                            fontSize: 11,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                      const SizedBox(width: 6),
                      const Icon(
                        LucideIcons.chevronRight,
                        size: 15,
                        color: AppColors.subtle,
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

void _showTransactionDetail(
  BuildContext context,
  BillingTransactionViewModel transaction,
) {
  final amountColor =
      transaction.isIncome ? _LedgerColors.income : _LedgerColors.negative;
  showModalBottomSheet<void>(
    context: context,
    showDragHandle: true,
    backgroundColor: AppColors.surface,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
    ),
    builder: (context) {
      return SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  _LedgerRoundIcon(
                    icon: _transactionIcon(transaction),
                    color: _transactionIconColor(transaction),
                    background: _transactionIconBackground(transaction),
                    size: 46,
                    iconSize: 21,
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      transaction.title,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: AppTextStyles.dateTitle.copyWith(
                        color: _LedgerColors.ink,
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Text(
                    transaction.amountText,
                    style: AppTextStyles.dateTitle.copyWith(
                      color: amountColor,
                      fontFeatures: const [FontFeature.tabularFigures()],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 18),
              _DetailField(label: '账单类型', value: transaction.typeText),
              _DetailField(label: '发生日期', value: transaction.dateText),
              _DetailField(label: '分类', value: transaction.categoryText),
              _DetailField(label: '对象', value: transaction.counterpartyText),
              _DetailField(label: '来源', value: transaction.sourceText),
              _DetailField(label: '备注', value: transaction.noteText),
            ],
          ),
        ),
      );
    },
  );
}

class _DetailField extends StatelessWidget {
  const _DetailField({
    required this.label,
    required this.value,
  });

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 76,
            child: Text(
              label,
              style: AppTextStyles.body.copyWith(
                color: AppColors.muted,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: AppTextStyles.body.copyWith(
                color: _LedgerColors.ink,
                fontWeight: FontWeight.w700,
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

class _IndentedDivider extends StatelessWidget {
  const _IndentedDivider();

  @override
  Widget build(BuildContext context) {
    return const Padding(
      padding: EdgeInsets.only(left: 58),
      child: Divider(height: 1, color: _LedgerColors.lineSoft),
    );
  }
}
