import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../data/repositories/billing_repository.dart';
import '../../shared/widgets/animated_press.dart';
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
  static const income = AppColors.greenDark;
  static const expense = AppColors.amber;
  static const debt = AppColors.blue;
  static const negative = AppColors.red;
  static const surfaceTint = Color(0xFFFFFFFF);
  static const line = AppColors.line;
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

class BillingScreen extends StatefulWidget {
  const BillingScreen({
    super.key,
    required this.repository,
    this.refreshKey = 0,
    this.onCreateRecord,
  });

  final BillingRepository repository;
  final int refreshKey;
  final VoidCallback? onCreateRecord;

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
                            builder: (_) => AllTransactionsScreen(
                              model: model,
                              onCreateRecord: widget.onCreateRecord,
                            ),
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

class _BillingCreateFab extends StatelessWidget {
  const _BillingCreateFab({required this.onTap});

  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.centerRight,
      child: AnimatedPress(
        scale: 0.92,
        onTap: onTap,
        child: Container(
          width: 56,
          height: 56,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: AppColors.ink,
            shape: BoxShape.circle,
            boxShadow: [
              BoxShadow(
                color: AppColors.ink.withValues(alpha: 0.22),
                blurRadius: 18,
                offset: const Offset(0, 8),
              ),
            ],
          ),
          child: const Icon(
            LucideIcons.plus,
            color: Colors.white,
            size: 24,
          ),
        ),
      ),
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
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 32),
              child: Center(
                child: Text(
                  '暂无交易',
                  style: TextStyle(
                    color: AppColors.muted,
                    fontSize: 13,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ),
            )
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
              ),
              if (index != visibleTransactions.length - 1)
                const Padding(
                  padding: EdgeInsets.only(left: 50),
                  child: Divider(height: 1, color: AppColors.lineSoft),
                ),
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
      height: 60,
      child: Row(
        children: [
          Container(
            width: 36,
            height: 36,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: AppColors.surface2,
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(icon, size: 16, color: AppColors.ink2),
          ),
          const SizedBox(width: 12),
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
                        style: const TextStyle(
                          color: AppColors.ink,
                          fontSize: 15,
                          fontWeight: FontWeight.w700,
                          letterSpacing: -0.1,
                          height: 1.2,
                        ),
                      ),
                    ),
                    if (chipText != null) ...[
                      const SizedBox(width: 6),
                      Text(
                        '· $chipText',
                        style: TextStyle(
                          color: chipColor ?? AppColors.muted,
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ],
                ),
                const SizedBox(height: 3),
                Text(
                  subtitle,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: AppColors.subtle,
                    fontSize: 12,
                    fontWeight: FontWeight.w500,
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
              child: Text(
                amount,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  color: amountColor,
                  fontSize: 17,
                  fontWeight: FontWeight.w800,
                  fontFeatures: const [FontFeature.tabularFigures()],
                  letterSpacing: -0.3,
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
  const AllTransactionsScreen({
    super.key,
    required this.model,
    this.onCreateRecord,
  });

  final BillingViewModel model;
  final VoidCallback? onCreateRecord;

  @override
  State<AllTransactionsScreen> createState() => _AllTransactionsScreenState();
}

class _AllTransactionsScreenState extends State<AllTransactionsScreen> {
  _TransactionTab _tab = _TransactionTab.all;
  DateRangePreset _dateFilter = DateRangePreset.currentMonth;
  DateTime? _selectedMonth;
  DateTime? _customStart;
  DateTime? _customEnd;
  final TextEditingController _searchController = TextEditingController();
  String _searchKeyword = '';

  @override
  void initState() {
    super.initState();
    _searchController.addListener(() {
      final value = _searchController.text;
      if (value != _searchKeyword) {
        setState(() => _searchKeyword = value);
      }
    });
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  List<BillingTransactionViewModel> get _transactions {
    return widget.model.transactions.where((transaction) {
      return _matchesDate(transaction) &&
          _matchesTab(transaction) &&
          _matchesSearch(transaction);
    }).toList();
  }

  bool _matchesSearch(BillingTransactionViewModel transaction) {
    final keyword = _searchKeyword.trim().toLowerCase();
    if (keyword.isEmpty) return true;
    final haystack = [
      transaction.title,
      transaction.subtitle,
      transaction.counterpartyText,
      transaction.categoryText,
      transaction.sourceText,
      transaction.noteText,
    ].map((value) => value.toLowerCase()).join(' ');
    return haystack.contains(keyword);
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
      return _customRangeFull;
    }
    if (_dateFilter == DateRangePreset.currentMonth ||
        _dateFilter == DateRangePreset.previousMonth) {
      return '${_baseMonth.year}年${_baseMonth.month}月';
    }
    return _dateFilter.label;
  }

  String get _monthLabel {
    if (_dateFilter == DateRangePreset.currentMonth ||
        _dateFilter == DateRangePreset.previousMonth) {
      return '${_baseMonth.year}年${_baseMonth.month}月';
    }
    return _periodTitle;
  }

  bool get _hasCustomRange => _customStart != null && _customEnd != null;

  String _fmtFull(DateTime d) =>
      '${d.year}.${d.month.toString().padLeft(2, '0')}.${d.day.toString().padLeft(2, '0')}';

  String _fmtMonthDay(DateTime d) =>
      '${d.month.toString().padLeft(2, '0')}.${d.day.toString().padLeft(2, '0')}';

  /// 完整日期范围，用于列表卡标题（更详细）
  String get _customRangeFull {
    if (_customStart == null || _customEnd == null) return '自定义';
    if (_sameDate(_customStart!, _customEnd!)) return _fmtFull(_customStart!);
    if (_customStart!.year != _customEnd!.year) {
      return '${_fmtFull(_customStart!)} - ${_fmtFull(_customEnd!)}';
    }
    if (_customStart!.month != _customEnd!.month) {
      return '${_fmtFull(_customStart!)} - ${_fmtMonthDay(_customEnd!)}';
    }
    return '${_fmtFull(_customStart!)} - ${_customEnd!.day.toString().padLeft(2, '0')}';
  }

  bool _sameDate(DateTime a, DateTime b) =>
      a.year == b.year && a.month == b.month && a.day == b.day;

  @override
  Widget build(BuildContext context) {
    final transactions = _transactions;
    final incomeCount =
        transactions.where((transaction) => transaction.isIncome).length;
    final expenseCount = transactions
        .where((transaction) => !transaction.isIncome && !transaction.isDebt)
        .length;
    final incomeTotal = _sumAmount(transactions, income: true);
    final expenseTotal = _sumAmount(transactions, income: false);
    final balanceTotal = incomeTotal - expenseTotal;
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _AllTransactionsHeader(
              onBack: Navigator.of(context).pop,
              onPickDate: _pickDateFilter,
            ),
            _SearchSortBar(
              searchController: _searchController,
              onSort: _pickDateFilter,
              onClearSearch: () => setState(() => _searchController.clear()),
            ),
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.fromLTRB(20, 12, 20, 120),
                child: Center(
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 430),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        _AliStyleSummary(
                          periodLabel: _monthLabel,
                          balanceText: _ledgerMoney(balanceTotal, round: true),
                          incomeText: _sumText(transactions, income: true),
                          incomeCount: incomeCount,
                          expenseText: _sumText(transactions, income: false),
                          expenseCount: expenseCount,
                        ),
                        const SizedBox(height: 20),
                        _AliStyleFilterBar(
                          selected: _tab,
                          countText: '共${transactions.length}笔',
                          onChanged: _setTab,
                        ),
                        const SizedBox(height: 12),
                        if (transactions.isEmpty)
                          const Padding(
                            padding: EdgeInsets.symmetric(vertical: 40),
                            child: Center(
                              child: Text(
                                '暂无交易',
                                style: TextStyle(
                                  color: AppColors.muted,
                                  fontSize: 13,
                                  fontWeight: FontWeight.w500,
                                ),
                              ),
                            ),
                          )
                        else
                          _AliStyleGroupedList(transactions: transactions),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
      floatingActionButton: widget.onCreateRecord != null
          ? Padding(
              padding: const EdgeInsets.only(right: 4, bottom: 8),
              child: _BillingCreateFab(onTap: widget.onCreateRecord!),
            )
          : null,
      floatingActionButtonLocation: FloatingActionButtonLocation.endFloat,
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
    return _ledgerMoney(total, round: true);
  }

  num _sumAmount(
    List<BillingTransactionViewModel> transactions, {
    required bool income,
  }) {
    return transactions
        .where((transaction) => income
            ? transaction.isIncome
            : !transaction.isIncome && !transaction.isDebt)
        .fold<num>(0, (sum, transaction) => sum + transaction.amount);
  }
}

class _AliStyleSummary extends StatelessWidget {
  const _AliStyleSummary({
    required this.periodLabel,
    required this.balanceText,
    required this.incomeText,
    required this.incomeCount,
    required this.expenseText,
    required this.expenseCount,
  });

  final String periodLabel;
  final String balanceText;
  final String incomeText;
  final int incomeCount;
  final String expenseText;
  final int expenseCount;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(24, 24, 24, 20),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: AppColors.lineSoft),
      ),
      child: Column(
        children: [
          Text(
            '$periodLabel · 结余',
            style: const TextStyle(
              color: AppColors.muted,
              fontSize: 12.5,
              fontWeight: FontWeight.w500,
              letterSpacing: 0.1,
            ),
          ),
          const SizedBox(height: 10),
          FittedBox(
            fit: BoxFit.scaleDown,
            alignment: Alignment.center,
            child: Text(
              balanceText,
              maxLines: 1,
              softWrap: false,
              textAlign: TextAlign.center,
              style: TextStyle(
                color: AppColors.ink,
                fontSize: 36,
                fontWeight: FontWeight.w900,
                letterSpacing: -0.5,
                height: 1.1,
                fontFeatures: const [FontFeature.tabularFigures()],
              ),
            ),
          ),
          const SizedBox(height: 20),
          Container(
            height: 1,
            color: AppColors.lineSoft,
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: _AliMetric(
                  icon: LucideIcons.arrowDownToLine,
                  label: '收入',
                  value: incomeText,
                  countText: '$incomeCount笔',
                  color: AppColors.greenDark,
                ),
              ),
              Container(
                width: 1,
                height: 36,
                color: AppColors.lineSoft,
              ),
              Expanded(
                child: _AliMetric(
                  icon: LucideIcons.arrowUpFromLine,
                  label: '支出',
                  value: expenseText,
                  countText: '$expenseCount笔',
                  color: AppColors.ink,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _AliMetric extends StatelessWidget {
  const _AliMetric({
    required this.icon,
    required this.label,
    required this.value,
    required this.countText,
    required this.color,
  });

  final IconData icon;
  final String label;
  final String value;
  final String countText;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, size: 12, color: color),
            const SizedBox(width: 4),
            Text(
              label,
              style: TextStyle(
                color: color,
                fontSize: 12,
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
        ),
        const SizedBox(height: 6),
        FittedBox(
          fit: BoxFit.scaleDown,
          alignment: Alignment.center,
          child: Text(
            value,
            maxLines: 1,
            style: TextStyle(
              color: color,
              fontSize: 17,
              fontWeight: FontWeight.w800,
              letterSpacing: -0.3,
              fontFeatures: const [FontFeature.tabularFigures()],
            ),
          ),
        ),
        const SizedBox(height: 2),
        Text(
          countText,
          style: const TextStyle(
            color: AppColors.subtle,
            fontSize: 11,
            fontWeight: FontWeight.w500,
          ),
        ),
      ],
    );
  }
}

class _AliStyleFilterBar extends StatelessWidget {
  const _AliStyleFilterBar({
    required this.selected,
    required this.countText,
    required this.onChanged,
  });

  final _TransactionTab selected;
  final String countText;
  final ValueChanged<_TransactionTab> onChanged;

  @override
  Widget build(BuildContext context) {
    final tabs = <(_TransactionTab, String)>[
      (_TransactionTab.all, '全部'),
      (_TransactionTab.income, '收入'),
      (_TransactionTab.expense, '支出'),
      (_TransactionTab.debt, '欠款'),
    ];
    return Column(
      children: [
        Row(
          children: [
            for (final tab in tabs)
              Expanded(
                child: GestureDetector(
                  behavior: HitTestBehavior.opaque,
                  onTap: () => onChanged(tab.$1),
                  child: Container(
                    padding: const EdgeInsets.only(bottom: 10),
                    alignment: Alignment.center,
                    decoration: BoxDecoration(
                      border: Border(
                        bottom: BorderSide(
                          width: 2,
                          color: selected == tab.$1
                              ? AppColors.ink
                              : Colors.transparent,
                        ),
                      ),
                    ),
                    child: Text(
                      tab.$2,
                      style: TextStyle(
                        color: selected == tab.$1
                            ? AppColors.ink
                            : AppColors.muted,
                        fontSize: 14,
                        fontWeight: selected == tab.$1
                            ? FontWeight.w800
                            : FontWeight.w500,
                        letterSpacing: -0.1,
                      ),
                    ),
                  ),
                ),
              ),
          ],
        ),
        Container(height: 1, color: AppColors.lineSoft),
      ],
    );
  }
}

class _AliStyleGroupedList extends StatelessWidget {
  const _AliStyleGroupedList({required this.transactions});

  final List<BillingTransactionViewModel> transactions;

  @override
  Widget build(BuildContext context) {
    final groups = _groupByDay(transactions);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (var i = 0; i < groups.length; i++) ...[
          if (i != 0) const SizedBox(height: 14),
          _AliGroupHeader(
            label: groups[i].label,
            netText: groups[i].netText,
          ),
          const SizedBox(height: 2),
          Container(
            decoration: BoxDecoration(
              color: AppColors.surface,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: AppColors.lineSoft),
            ),
            child: Column(
              children: [
                for (var j = 0; j < groups[i].items.length; j++) ...[
                  _TransactionDetailRow(
                    transaction: groups[i].items[j],
                    onTap: () => _showTransactionDetail(
                      context,
                      groups[i].items[j],
                    ),
                  ),
                  if (j != groups[i].items.length - 1)
                    const Padding(
                      padding: EdgeInsets.only(left: 62),
                      child: Divider(height: 1, color: AppColors.lineSoft),
                    ),
                ],
              ],
            ),
          ),
        ],
      ],
    );
  }

  List<_AliGroup> _groupByDay(List<BillingTransactionViewModel> items) {
    final map = <String, List<BillingTransactionViewModel>>{};
    final sorted = [...items]..sort((a, b) {
        final aDate = a.recordDate ?? DateTime(1970);
        final bDate = b.recordDate ?? DateTime(1970);
        return bDate.compareTo(aDate);
      });
    for (final item in sorted) {
      final date = item.recordDate;
      final key =
          date != null ? '${date.year}-${date.month}-${date.day}' : 'unknown';
      map.putIfAbsent(key, () => []).add(item);
    }
    return map.entries.map((entry) {
      final parts = entry.key.split('-');
      final date = parts.length == 3
          ? DateTime(
              int.parse(parts[0]), int.parse(parts[1]), int.parse(parts[2]))
          : null;
      final income = entry.value
          .where((t) => t.isIncome)
          .fold<num>(0, (s, t) => s + t.amount);
      final expense = entry.value
          .where((t) => !t.isIncome && !t.isDebt)
          .fold<num>(0, (s, t) => s + t.amount);
      final net = income - expense;
      return _AliGroup(
        label: _aliGroupLabel(date),
        netText: _aliNetText(net),
        items: entry.value,
      );
    }).toList();
  }

  String _aliGroupLabel(DateTime? date) {
    if (date == null) return '未分组';
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final target = DateTime(date.year, date.month, date.day);
    final diff = today.difference(target).inDays;
    if (diff == 0) return '今天';
    if (diff == 1) return '昨天';
    if (diff < 7) return '$diff 天前';
    const weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];
    return '${date.month}月${date.day}日 · ${weekdays[date.weekday - 1]}';
  }

  String _aliNetText(num net) {
    if (net == 0) return '收支平衡';
    if (net > 0) return '净收 ${_ledgerMoney(net, round: true)}';
    return '净支 ${_ledgerMoney(-net, round: true)}';
  }
}

class _AliGroup {
  const _AliGroup({
    required this.label,
    required this.netText,
    required this.items,
  });

  final String label;
  final String netText;
  final List<BillingTransactionViewModel> items;
}

class _AliGroupHeader extends StatelessWidget {
  const _AliGroupHeader({required this.label, required this.netText});

  final String label;
  final String netText;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(4, 14, 4, 8),
      child: Row(
        children: [
          Text(
            label,
            style: const TextStyle(
              color: AppColors.muted,
              fontSize: 12.5,
              fontWeight: FontWeight.w700,
              letterSpacing: 0.1,
            ),
          ),
          const Spacer(),
          Text(
            netText,
            style: const TextStyle(
              color: AppColors.subtle,
              fontSize: 11.5,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
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
      height: 56,
      child: Row(
        children: [
          SizedBox(
            width: 44,
            height: 44,
            child: IconButton(
              onPressed: onBack,
              icon: const Icon(LucideIcons.chevronLeft),
              color: AppColors.ink,
              iconSize: 28,
              padding: EdgeInsets.zero,
            ),
          ),
          const SizedBox(width: 16),
          const Expanded(
            child: Text('账单', style: AppTextStyles.title),
          ),
          SizedBox(
            width: 44,
            height: 44,
            child: IconButton(
              key: const Key('transaction-date-filter'),
              onPressed: onPickDate,
              icon: const Icon(LucideIcons.calendarDays),
              color: AppColors.ink,
              iconSize: 26,
              padding: EdgeInsets.zero,
            ),
          ),
        ],
      ),
    );
  }
}

class _SearchSortBar extends StatelessWidget {
  const _SearchSortBar({
    required this.searchController,
    required this.onSort,
    required this.onClearSearch,
  });

  final TextEditingController searchController;
  final VoidCallback onSort;
  final VoidCallback onClearSearch;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 4, 20, 4),
      child: Row(
        children: [
          Expanded(
            child: Container(
              height: 40,
              padding: const EdgeInsets.symmetric(horizontal: 14),
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: AppColors.lineSoft),
              ),
              child: Row(
                children: [
                  const Icon(
                    LucideIcons.search,
                    size: 16,
                    color: AppColors.subtle,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: TextField(
                      controller: searchController,
                      textInputAction: TextInputAction.search,
                      style: const TextStyle(
                        color: AppColors.ink,
                        fontSize: 14,
                        fontWeight: FontWeight.w500,
                      ),
                      decoration: InputDecoration(
                        isDense: true,
                        contentPadding: EdgeInsets.zero,
                        hintText: '搜索分类、对象、备注',
                        hintStyle: const TextStyle(
                          color: AppColors.subtle,
                          fontSize: 14,
                          fontWeight: FontWeight.w500,
                        ),
                        border: InputBorder.none,
                      ),
                    ),
                  ),
                  ValueListenableBuilder<TextEditingValue>(
                    valueListenable: searchController,
                    builder: (context, value, _) {
                      if (value.text.isEmpty) return const SizedBox.shrink();
                      return GestureDetector(
                        onTap: onClearSearch,
                        behavior: HitTestBehavior.opaque,
                        child: const Padding(
                          padding: EdgeInsets.only(left: 6),
                          child: Icon(
                            LucideIcons.x,
                            size: 15,
                            color: AppColors.subtle,
                          ),
                        ),
                      );
                    },
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(width: 10),
          GestureDetector(
            onTap: onSort,
            behavior: HitTestBehavior.opaque,
            child: Container(
              height: 40,
              width: 40,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: AppColors.lineSoft),
              ),
              child: const Icon(
                LucideIcons.slidersHorizontal,
                size: 18,
                color: AppColors.ink,
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
    final amountColor = transaction.isIncome
        ? _LedgerColors.income
        : (transaction.isDebt ? _LedgerColors.debt : _LedgerColors.ink);
    final hasCounterparty = transaction.counterpartyText.isNotEmpty &&
        transaction.counterpartyText != '未填写对象';
    final detailText =
        hasCounterparty ? transaction.counterpartyText : transaction.sourceText;
    final timeText = transaction.subtitle.isEmpty
        ? transaction.dateText
        : transaction.subtitle.split(' · ').first;

    return AnimatedPress(
      scale: 0.99,
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            Container(
              width: 36,
              height: 36,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: AppColors.surface2,
                borderRadius: BorderRadius.circular(10),
              ),
              child: Icon(
                _transactionIcon(transaction),
                size: 16,
                color: AppColors.ink2,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Flexible(
                        child: Text(
                          transaction.title,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            color: AppColors.ink,
                            fontSize: 15,
                            fontWeight: FontWeight.w700,
                            letterSpacing: -0.1,
                            height: 1.2,
                          ),
                        ),
                      ),
                      const SizedBox(width: 6),
                      Text(
                        '· $timeText',
                        style: const TextStyle(
                          color: AppColors.subtle,
                          fontSize: 12,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 3),
                  Text(
                    detailText,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: AppColors.muted,
                      fontSize: 12.5,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 10),
            FittedBox(
              fit: BoxFit.scaleDown,
              alignment: Alignment.centerRight,
              child: Text(
                transaction.isIncome
                    ? '+${_ledgerMoney(transaction.amount)}'
                    : '-${_ledgerMoney(transaction.amount)}',
                maxLines: 1,
                softWrap: false,
                style: TextStyle(
                  color: amountColor,
                  fontSize: 16,
                  fontWeight: FontWeight.w800,
                  fontFeatures: const [FontFeature.tabularFigures()],
                  letterSpacing: -0.3,
                ),
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
  showModalBottomSheet<void>(
    context: context,
    showDragHandle: true,
    backgroundColor: AppColors.surface,
    isScrollControlled: true,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
    ),
    builder: (sheetContext) {
      return SafeArea(
        top: false,
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(24, 6, 24, 24),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 430),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                _DetailAmountHeader(transaction: transaction),
                const SizedBox(height: 24),
                _DetailInfoGrid(transaction: transaction),
                const SizedBox(height: 12),
                _DetailNoteCard(transaction: transaction),
                const SizedBox(height: 20),
                _DetailActionBar(transaction: transaction),
                const SizedBox(height: 8),
              ],
            ),
          ),
        ),
      );
    },
  );
}

class _DetailActionBar extends StatelessWidget {
  const _DetailActionBar({required this.transaction});

  final BillingTransactionViewModel transaction;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: _DetailActionTile(
            icon: LucideIcons.pencil,
            label: '编辑',
            onTap: () => Navigator.of(context).pop(),
          ),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: _DetailActionTile(
            icon: LucideIcons.copy,
            label: '复制金额',
            onTap: () {
              Clipboard.setData(ClipboardData(text: '${transaction.amount}'));
              Navigator.of(context).pop();
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('金额已复制')),
              );
            },
          ),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: _DetailActionTile(
            icon: LucideIcons.trash2,
            label: '删除',
            danger: true,
            onTap: () => Navigator.of(context).pop(),
          ),
        ),
      ],
    );
  }
}

class _DetailActionTile extends StatelessWidget {
  const _DetailActionTile({
    required this.icon,
    required this.label,
    required this.onTap,
    this.danger = false,
  });

  final IconData icon;
  final String label;
  final VoidCallback onTap;
  final bool danger;

  @override
  Widget build(BuildContext context) {
    final color = danger ? AppColors.red : AppColors.ink2;
    return AnimatedPress(
      scale: 0.96,
      onTap: onTap,
      child: Container(
        height: 56,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: AppColors.surface2,
          borderRadius: BorderRadius.circular(14),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, size: 18, color: color),
            const SizedBox(height: 4),
            Text(
              label,
              style: TextStyle(
                color: color,
                fontSize: 12,
                fontWeight: FontWeight.w700,
                letterSpacing: 0.1,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _DetailAmountHeader extends StatelessWidget {
  const _DetailAmountHeader({required this.transaction});

  final BillingTransactionViewModel transaction;

  @override
  Widget build(BuildContext context) {
    final amount = transaction.isIncome
        ? '+${_ledgerMoney(transaction.amount)}'
        : '-${_ledgerMoney(transaction.amount)}';
    final amountColor =
        transaction.isIncome ? _LedgerColors.income : _LedgerColors.negative;
    final typeLabel =
        transaction.isDebt ? '欠款' : (transaction.isIncome ? '收入' : '支出');
    final datetime = _formatDetailDateTime(transaction.recordDate);
    final length = amount.length;
    final amountFontSize = length > 12 ? 30.0 : (length > 9 ? 34.0 : 40.0);
    return Column(
      children: [
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
          decoration: BoxDecoration(
            color: transaction.isIncome
                ? AppColors.greenSoft
                : (transaction.isDebt
                    ? AppColors.blueSoft
                    : const Color(0xFFFFEFEF)),
            borderRadius: BorderRadius.circular(999),
          ),
          child: Text(
            typeLabel,
            style: TextStyle(
              color: amountColor,
              fontSize: 12,
              fontWeight: FontWeight.w800,
              letterSpacing: 0.1,
            ),
          ),
        ),
        const SizedBox(height: 12),
        Text(
          amount,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          textAlign: TextAlign.center,
          style: TextStyle(
            color: amountColor,
            fontSize: amountFontSize,
            fontWeight: FontWeight.w900,
            letterSpacing: -0.6,
            height: 1.1,
            fontFeatures: const [FontFeature.tabularFigures()],
          ),
        ),
        const SizedBox(height: 10),
        Text(
          transaction.title,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          textAlign: TextAlign.center,
          style: const TextStyle(
            color: AppColors.ink,
            fontSize: 15,
            fontWeight: FontWeight.w700,
            letterSpacing: -0.1,
          ),
        ),
        if (datetime.isNotEmpty) ...[
          const SizedBox(height: 4),
          Text(
            datetime,
            style: const TextStyle(
              color: AppColors.subtle,
              fontSize: 12.5,
              fontWeight: FontWeight.w500,
              letterSpacing: 0.1,
            ),
          ),
        ],
      ],
    );
  }

  String _formatDetailDateTime(DateTime? value) {
    final date = value ?? transaction.recordDate;
    if (date == null) return transaction.dateText;
    final y = date.year;
    final m = date.month.toString().padLeft(2, '0');
    final d = date.day.toString().padLeft(2, '0');
    final h = date.hour.toString().padLeft(2, '0');
    final min = date.minute.toString().padLeft(2, '0');
    return '$y-$m-$d $h:$min';
  }
}

class _DetailInfoGrid extends StatelessWidget {
  const _DetailInfoGrid({required this.transaction});

  final BillingTransactionViewModel transaction;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.lineSoft),
      ),
      child: Column(
        children: [
          _DetailInfoLine(
            label: '分类',
            value: transaction.categoryText,
            showDivider: true,
          ),
          _DetailInfoLine(
            label: '对象',
            value: transaction.counterpartyText,
            showDivider: true,
          ),
          _DetailInfoLine(
            label: '来源',
            value: transaction.sourceText,
            showDivider: false,
          ),
        ],
      ),
    );
  }
}

class _DetailInfoLine extends StatelessWidget {
  const _DetailInfoLine({
    required this.label,
    required this.value,
    required this.showDivider,
  });

  final String label;
  final String value;
  final bool showDivider;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SizedBox(
                width: 72,
                child: Text(
                  label,
                  style: const TextStyle(
                    color: AppColors.muted,
                    fontSize: 14,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  value.isEmpty ? '—' : value,
                  textAlign: TextAlign.right,
                  style: TextStyle(
                    color: value.isEmpty ? AppColors.subtle : AppColors.ink,
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    letterSpacing: -0.1,
                    height: 1.35,
                  ),
                ),
              ),
            ],
          ),
        ),
        if (showDivider)
          const Padding(
            padding: EdgeInsets.only(left: 16),
            child: Divider(height: 1, thickness: 1, color: AppColors.lineSoft),
          ),
      ],
    );
  }
}

class _DetailNoteCard extends StatelessWidget {
  const _DetailNoteCard({required this.transaction});

  final BillingTransactionViewModel transaction;

  @override
  Widget build(BuildContext context) {
    final note = transaction.noteText;
    final hasNote = note.isNotEmpty && note != '—';
    if (!hasNote) return const SizedBox.shrink();
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.lineSoft),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(
            width: 72,
            child: Text(
              '备注',
              style: TextStyle(
                color: AppColors.muted,
                fontSize: 14,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              note,
              textAlign: TextAlign.right,
              style: const TextStyle(
                color: AppColors.ink,
                fontSize: 14,
                fontWeight: FontWeight.w600,
                height: 1.4,
                letterSpacing: -0.1,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

String _ledgerMoney(
  num value, {
  bool round = false,
  bool explicitPositive = false,
}) {
  final sign = value < 0 ? '-' : (explicitPositive && value > 0 ? '+' : '');
  final abs = value.abs();
  final normalized = round ? abs.roundToDouble() : abs.toDouble();
  final integer = normalized.truncate();
  final hasDecimal = !round && (normalized - integer).abs() > 0.001;
  final integerText = _thousandSeparated(integer);
  final decimalText = hasDecimal
      ? normalized.toStringAsFixed(2).split('.').last.replaceFirst(
            RegExp(r'0+$'),
            '',
          )
      : '';
  return '$sign¥$integerText${decimalText.isEmpty ? '' : '.$decimalText'}';
}

String _thousandSeparated(int value) {
  final text = value.toString();
  final buffer = StringBuffer();
  for (var i = 0; i < text.length; i++) {
    final positionFromEnd = text.length - i;
    buffer.write(text[i]);
    if (positionFromEnd > 1 && positionFromEnd % 3 == 1) {
      buffer.write(',');
    }
  }
  return buffer.toString();
}
