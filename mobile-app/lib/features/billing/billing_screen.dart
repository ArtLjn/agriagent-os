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
  static const surfaceTint = Color(0xFFFFFFFF);
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

  String get _dateGroupLabel {
    final dated = _transactions
        .map((transaction) => transaction.recordDate)
        .whereType<DateTime>()
        .toList();
    if (dated.isEmpty) return '暂无日期';
    dated.sort((a, b) => b.compareTo(a));
    final latest = dated.first;
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final target = DateTime(latest.year, latest.month, latest.day);
    final prefix = today == target ? '今天' : _ledgerRelativeDate(latest);
    const weekdays = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日'];
    return '$prefix  ${latest.month}月${latest.day}日  ${weekdays[latest.weekday - 1]}';
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
    return Scaffold(
      backgroundColor: const Color(0xFFF8FAFD),
      bottomNavigationBar: _CreateRecordDock(onTap: widget.onCreateRecord),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
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
                  const SizedBox(height: 22),
                  _LedgerPeriodTitle(
                    title: _monthLabel,
                    countText: '共${transactions.length}笔交易',
                  ),
                  const SizedBox(height: 16),
                  _MonthlyBalanceCard(
                    balanceText: _ledgerMoney(
                      _sumAmount(transactions, income: true) -
                          _sumAmount(transactions, income: false),
                      round: true,
                    ),
                    incomeText: _sumText(transactions, income: true),
                    incomeCount: incomeCount,
                    expenseText: _sumText(transactions, income: false),
                    expenseCount: expenseCount,
                    trendData: _monthlyTrendValues(transactions),
                  ),
                  const SizedBox(height: 14),
                  _TransactionFilterBar(selected: _tab, onChanged: _setTab),
                  const SizedBox(height: 12),
                  _TransactionListToolbar(
                    incomeCount: incomeCount,
                    expenseCount: expenseCount,
                    onFilter: _pickDateFilter,
                  ),
                  const SizedBox(height: 12),
                  _DateGroupHeader(text: _dateGroupLabel),
                  const SizedBox(height: 8),
                  _AllTransactionsListCard(
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

  List<double> _monthlyTrendValues(List<BillingTransactionViewModel> source) {
    final sorted = source
        .where((transaction) => transaction.recordDate != null)
        .toList()
      ..sort((a, b) => a.recordDate!.compareTo(b.recordDate!));
    if (sorted.isEmpty) return widget.model.monthlyTrend;
    var running = 0.0;
    return sorted.map((transaction) {
      final delta =
          transaction.isIncome ? transaction.amount : -transaction.amount;
      running += delta.toDouble();
      return running;
    }).toList();
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

class _LedgerPeriodTitle extends StatelessWidget {
  const _LedgerPeriodTitle({
    required this.title,
    required this.countText,
  });

  final String title;
  final String countText;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              title,
              style: AppTextStyles.metric.copyWith(
                color: _LedgerColors.ink,
                fontSize: 31,
                height: 1.08,
              ),
            ),
            const SizedBox(width: 8),
            const Icon(
              LucideIcons.chevronDown,
              size: 20,
              color: AppColors.muted,
            ),
          ],
        ),
        const SizedBox(height: 8),
        Text(
          countText,
          style: AppTextStyles.body.copyWith(
            color: AppColors.muted,
            fontWeight: FontWeight.w700,
          ),
        ),
      ],
    );
  }
}

class _MonthlyBalanceCard extends StatelessWidget {
  const _MonthlyBalanceCard({
    required this.balanceText,
    required this.incomeText,
    required this.incomeCount,
    required this.expenseText,
    required this.expenseCount,
    required this.trendData,
  });

  final String balanceText;
  final String incomeText;
  final int incomeCount;
  final String expenseText;
  final int expenseCount;
  final List<double> trendData;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.96),
        borderRadius: BorderRadius.circular(22),
        boxShadow: const [
          BoxShadow(
            color: Color(0x0A14365F),
            blurRadius: 28,
            offset: Offset(0, 12),
          ),
        ],
      ),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 14),
        child: Row(
          children: [
            Expanded(
              flex: 12,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '本月结余',
                    style: AppTextStyles.body.copyWith(
                      color: AppColors.muted,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  const SizedBox(height: 8),
                  FittedBox(
                    fit: BoxFit.scaleDown,
                    alignment: Alignment.centerLeft,
                    child: Text(
                      balanceText,
                      maxLines: 1,
                      softWrap: false,
                      style: AppTextStyles.metric.copyWith(
                        color: _LedgerColors.ink,
                        fontSize: 38,
                        height: 1,
                        fontFeatures: const [FontFeature.tabularFigures()],
                      ),
                    ),
                  ),
                  const SizedBox(height: 18),
                  SizedBox(
                    width: double.infinity,
                    height: 32,
                    child: CustomPaint(
                      painter: _LedgerSparklinePainter(
                        data: _sparklineData(trendData),
                        lineColor: const Color(0xFF34C986),
                      ),
                      child: const SizedBox.expand(),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 16),
            const _MetricDivider(height: 96),
            const SizedBox(width: 18),
            Expanded(
              flex: 8,
              child: Column(
                children: [
                  _BalanceSideMetric(
                    label: '收入',
                    value: incomeText,
                    countText: '$incomeCount笔',
                    color: _LedgerColors.income,
                    icon: LucideIcons.arrowUpRight,
                  ),
                  const Padding(
                    padding: EdgeInsets.symmetric(vertical: 9),
                    child: Divider(height: 1, color: AppColors.lineSoft),
                  ),
                  _BalanceSideMetric(
                    label: '支出',
                    value: expenseText,
                    countText: '$expenseCount笔',
                    color: _LedgerColors.ink,
                    icon: LucideIcons.arrowDownRight,
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

List<double> _sparklineData(List<double> source) {
  if (source.length >= 3) return source;
  if (source.isEmpty) return const [0, 1, 0.4, 1.2, 0.9, 1.5, 1.1];
  if (source.length == 1) {
    final value = source.first;
    return [value - 1, value, value + 0.6, value + 0.2, value + 1.1];
  }
  final first = source.first;
  final last = source.last;
  final mid = (first + last) / 2;
  return [first, mid + 0.4, mid - 0.2, last, last + 0.3];
}

class _BalanceSideMetric extends StatelessWidget {
  const _BalanceSideMetric({
    required this.label,
    required this.value,
    required this.countText,
    required this.color,
    required this.icon,
  });

  final String label;
  final String value;
  final String countText;
  final Color color;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.centerLeft,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: AppTextStyles.small.copyWith(
              color: AppColors.muted,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 6),
          FittedBox(
            fit: BoxFit.scaleDown,
            alignment: Alignment.centerLeft,
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  value,
                  maxLines: 1,
                  softWrap: false,
                  style: AppTextStyles.sectionTitle.copyWith(
                    color: color,
                    fontSize: 22,
                    fontWeight: FontWeight.w800,
                    fontFeatures: const [FontFeature.tabularFigures()],
                  ),
                ),
                const SizedBox(width: 8),
                Icon(icon, size: 17, color: color),
              ],
            ),
          ),
          const SizedBox(height: 6),
          Text(
            countText,
            style: AppTextStyles.small.copyWith(
              color: AppColors.muted,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
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
    return SizedBox(
      height: 42,
      child: ListView(
        scrollDirection: Axis.horizontal,
        padding: EdgeInsets.zero,
        children: [
          _FilterChipLabel(
            key: const Key('transaction-filter-all'),
            text: '全部',
            selected: selected == _TransactionTab.all,
            onTap: () => onChanged(_TransactionTab.all),
          ),
          const SizedBox(width: 10),
          _FilterChipLabel(
            key: const Key('transaction-filter-income'),
            text: '收入',
            selected: selected == _TransactionTab.income,
            onTap: () => onChanged(_TransactionTab.income),
          ),
          const SizedBox(width: 10),
          _FilterChipLabel(
            key: const Key('transaction-filter-expense'),
            text: '支出',
            selected: selected == _TransactionTab.expense,
            onTap: () => onChanged(_TransactionTab.expense),
          ),
          const SizedBox(width: 10),
          _FilterChipLabel(
            text: '工资',
            selected: false,
            onTap: () => onChanged(_TransactionTab.expense),
          ),
          const SizedBox(width: 10),
          _FilterChipLabel(
            text: '材料',
            selected: false,
            onTap: () => onChanged(_TransactionTab.expense),
          ),
          const SizedBox(width: 10),
          _FilterChipLabel(
            text: '运费',
            selected: false,
            onTap: () => onChanged(_TransactionTab.expense),
          ),
          const SizedBox(width: 10),
          _FilterChipLabel(
            key: const Key('transaction-filter-debt'),
            text: '借贷',
            selected: selected == _TransactionTab.debt,
            onTap: () => onChanged(_TransactionTab.debt),
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
      borderRadius: BorderRadius.circular(999),
      child: Container(
        height: 38,
        constraints: const BoxConstraints(minWidth: 72),
        padding: const EdgeInsets.symmetric(horizontal: 16),
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: selected ? _LedgerColors.primaryDark : Colors.transparent,
          borderRadius: BorderRadius.circular(999),
          border: Border.all(
            color:
                selected ? _LedgerColors.primaryDark : const Color(0xFFD3DCE8),
          ),
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

class _TransactionListToolbar extends StatelessWidget {
  const _TransactionListToolbar({
    required this.incomeCount,
    required this.expenseCount,
    required this.onFilter,
  });

  final int incomeCount;
  final int expenseCount;
  final VoidCallback onFilter;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: RichText(
            text: TextSpan(
              style: AppTextStyles.body.copyWith(
                color: _LedgerColors.ink,
                fontWeight: FontWeight.w800,
              ),
              children: [
                TextSpan(
                  text: '收入 $incomeCount笔',
                  style: const TextStyle(color: _LedgerColors.income),
                ),
                const TextSpan(text: ' · '),
                TextSpan(text: '支出 $expenseCount笔'),
              ],
            ),
          ),
        ),
        InkWell(
          key: const Key('transaction-toolbar-filter'),
          onTap: onFilter,
          borderRadius: BorderRadius.circular(12),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 2, vertical: 6),
            child: Row(
              children: [
                Text(
                  '筛选',
                  style: AppTextStyles.body.copyWith(
                    color: _LedgerColors.ink,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(width: 6),
                const Icon(
                  LucideIcons.funnel,
                  size: 20,
                  color: _LedgerColors.ink,
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class _DateGroupHeader extends StatelessWidget {
  const _DateGroupHeader({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: AppTextStyles.body.copyWith(
        color: AppColors.muted,
        fontWeight: FontWeight.w700,
      ),
    );
  }
}

class _AllTransactionsListCard extends StatelessWidget {
  const _AllTransactionsListCard({
    required this.transactions,
  });

  final List<BillingTransactionViewModel> transactions;

  @override
  Widget build(BuildContext context) {
    return _LedgerSectionCard(
      radius: 22,
      padding: const EdgeInsets.fromLTRB(18, 8, 18, 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (transactions.isEmpty)
            const _EmptyLine(text: '暂无交易')
          else
            Column(
              children: [
                for (var index = 0; index < transactions.length; index++) ...[
                  _TransactionDetailRow(
                    transaction: transactions[index],
                    onTap: () => _showTransactionDetail(
                      context,
                      transactions[index],
                    ),
                  ),
                  if (index != transactions.length - 1)
                    const _IndentedDivider(indent: 58),
                ],
              ],
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
        transaction.isIncome ? _LedgerColors.income : _LedgerColors.ink;
    final hasCounterparty = transaction.counterpartyText.isNotEmpty &&
        transaction.counterpartyText != '未填写对象';
    final detailText =
        hasCounterparty ? transaction.counterpartyText : transaction.sourceText;
    final timeText = transaction.subtitle.isEmpty
        ? transaction.dateText
        : transaction.subtitle.split(' · ').first;

    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: SizedBox(
        height: 78,
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            _LedgerRoundIcon(
              icon: _transactionIcon(transaction),
              color: _transactionIconColor(transaction),
              background: _transactionIconBackground(transaction),
              size: 44,
              iconSize: 20,
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    transaction.title,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: AppTextStyles.sectionTitle.copyWith(
                      color: _LedgerColors.ink,
                      fontSize: 16,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  const SizedBox(height: 3),
                  Text(
                    detailText,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: AppTextStyles.body.copyWith(
                      color: AppColors.muted,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    transaction.subtitle.isEmpty ? timeText : timeText,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: AppTextStyles.small.copyWith(
                      color: AppColors.muted,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 10),
            ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 126),
              child: FittedBox(
                fit: BoxFit.scaleDown,
                alignment: Alignment.centerRight,
                child: Text(
                  transaction.isIncome
                      ? _ledgerMoney(transaction.amount)
                      : _ledgerMoney(-transaction.amount),
                  maxLines: 1,
                  softWrap: false,
                  style: AppTextStyles.sectionTitle.copyWith(
                    color: amountColor,
                    fontSize: 19,
                    fontWeight: FontWeight.w800,
                    fontFeatures: const [FontFeature.tabularFigures()],
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _CreateRecordDock extends StatelessWidget {
  const _CreateRecordDock({required this.onTap});

  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      top: false,
      minimum: const EdgeInsets.only(bottom: 6),
      child: DecoratedBox(
        decoration: const BoxDecoration(
          color: Color(0xFFF8FAFD),
          border: Border(top: BorderSide(color: Color(0x00F8FAFD))),
        ),
        child: SizedBox(
          height: 92,
          child: Center(
            child: InkWell(
              onTap: onTap,
              borderRadius: BorderRadius.circular(999),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(
                    width: 58,
                    height: 58,
                    decoration: BoxDecoration(
                      color: _LedgerColors.primaryDark,
                      shape: BoxShape.circle,
                      boxShadow: const [
                        BoxShadow(
                          color: Color(0x2608223F),
                          blurRadius: 18,
                          offset: Offset(0, 8),
                        ),
                      ],
                    ),
                    child: const Icon(
                      LucideIcons.plus,
                      size: 34,
                      color: Colors.white,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    '新增记录',
                    style: AppTextStyles.body.copyWith(
                      color: AppColors.muted,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ],
              ),
            ),
          ),
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
    builder: (context) {
      return SafeArea(
        top: false,
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(20, 6, 20, 24),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 430),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                _DetailSummaryHeader(transaction: transaction),
                const SizedBox(height: 14),
                _DetailInfoGrid(transaction: transaction),
                const SizedBox(height: 10),
                _DetailNoteCard(transaction: transaction),
              ],
            ),
          ),
        ),
      );
    },
  );
}

class _DetailSummaryHeader extends StatelessWidget {
  const _DetailSummaryHeader({required this.transaction});

  final BillingTransactionViewModel transaction;

  @override
  Widget build(BuildContext context) {
    final amount = transaction.isIncome
        ? _ledgerMoney(transaction.amount)
        : _ledgerMoney(-transaction.amount);
    final amountColor =
        transaction.isIncome ? _LedgerColors.income : _LedgerColors.negative;
    return Padding(
      padding: const EdgeInsets.only(top: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          _LedgerRoundIcon(
            icon: _transactionIcon(transaction),
            color: _transactionIconColor(transaction),
            background: _transactionIconBackground(transaction),
            size: 56,
            iconSize: 25,
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  transaction.title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppTextStyles.dateTitle.copyWith(
                    color: _LedgerColors.ink,
                    fontSize: 21,
                  ),
                ),
                const SizedBox(height: 5),
                Text(
                  '${transaction.typeText} · ${transaction.sourceText}',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppTextStyles.body.copyWith(
                    color: AppColors.muted,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 12),
          ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 132),
            child: FittedBox(
              fit: BoxFit.scaleDown,
              alignment: Alignment.centerRight,
              child: Text(
                amount,
                maxLines: 1,
                softWrap: false,
                style: AppTextStyles.dateTitle.copyWith(
                  color: amountColor,
                  fontSize: 20,
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

class _DetailInfoGrid extends StatelessWidget {
  const _DetailInfoGrid({required this.transaction});

  final BillingTransactionViewModel transaction;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: AppColors.surface3,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: AppColors.lineSoft),
      ),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(14, 8, 14, 8),
        child: Column(
          children: [
            _DetailInfoLine(
              icon: LucideIcons.calendarDays,
              label: '发生日期',
              value: transaction.dateText,
            ),
            const _IndentedDivider(indent: 32),
            _DetailInfoLine(
              icon: LucideIcons.tags,
              label: '分类',
              value: transaction.categoryText,
            ),
            const _IndentedDivider(indent: 32),
            _DetailInfoLine(
              icon: LucideIcons.userRound,
              label: '对象',
              value: transaction.counterpartyText,
            ),
            const _IndentedDivider(indent: 32),
            _DetailInfoLine(
              icon: LucideIcons.fileText,
              label: '来源',
              value: transaction.sourceText,
            ),
          ],
        ),
      ),
    );
  }
}

class _DetailInfoLine extends StatelessWidget {
  const _DetailInfoLine({
    required this.icon,
    required this.label,
    required this.value,
  });

  final IconData icon;
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 44,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Icon(icon, size: 16, color: AppColors.muted),
          const SizedBox(width: 10),
          SizedBox(
            width: 78,
            child: Text(
              label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: AppTextStyles.body.copyWith(
                color: AppColors.muted,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
          Expanded(
            child: Text(
              value,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              textAlign: TextAlign.right,
              style: AppTextStyles.body.copyWith(
                color: _LedgerColors.ink,
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _DetailNoteCard extends StatelessWidget {
  const _DetailNoteCard({required this.transaction});

  final BillingTransactionViewModel transaction;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: AppColors.lineSoft),
      ),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(14, 10, 14, 12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '备注',
              style: AppTextStyles.small.copyWith(
                color: AppColors.muted,
                fontWeight: FontWeight.w800,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              transaction.noteText,
              style: AppTextStyles.body.copyWith(
                color: _LedgerColors.ink,
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
        ),
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

String _ledgerRelativeDate(DateTime date) {
  final now = DateTime.now();
  final today = DateTime(now.year, now.month, now.day);
  final target = DateTime(date.year, date.month, date.day);
  final diffDays = today.difference(target).inDays;
  if (diffDays <= 0) return '今天';
  if (diffDays == 1) return '昨天';
  if (diffDays < 7) return '$diffDays天前';
  if (diffDays < 14) return '上周';
  if (target.year == today.year) return '${target.month}月${target.day}日';
  return '${target.year}年${target.month}月${target.day}日';
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
  const _IndentedDivider({this.indent = 58});

  final double indent;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(left: indent),
      child: const Divider(height: 1, color: _LedgerColors.lineSoft),
    );
  }
}
