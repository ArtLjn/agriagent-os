import '../../data/api/api_models.dart';
import '../../data/repositories/billing_repository.dart';

class BillingController {
  BillingController({required this.repository, int? year})
      : year = year ?? DateTime.now().year;

  final BillingRepository repository;
  final int year;

  Future<BillingViewModel> load() async {
    final results = await Future.wait<Object>([
      repository.listCosts(size: 10),
      repository.getYearlySummary(year),
      repository.listDebts(size: 10),
    ]);
    final costs = results[0] as PageResult<ApiRecord>;
    final summary = Map<String, dynamic>.from(results[1] as Map);
    final debts = Map<String, dynamic>.from(results[2] as Map);
    final receivables = _receivables(debts);

    return BillingViewModel(
      incomeText: _compactMoney(_number(summary['total_income'])),
      expenseText: _compactMoney(_number(summary['total_cost'])),
      netProfitText: _signedCompactMoney(_number(summary['net_profit'])),
      debtText: _compactMoney(_receivableTotal(debts, receivables)),
      insightText: _insightText(
        income: _number(summary['total_income']),
        expense: _number(summary['total_cost']),
        netProfit: _number(summary['net_profit']),
      ),
      transactions: costs.items.map(_transaction).toList(),
      receivables: receivables,
      monthlyTrend: _monthlyTrend(costs.items),
    );
  }

  List<double> _monthlyTrend(List<ApiRecord> items) {
    final monthly = List<double>.filled(12, 0);
    for (final item in items) {
      final json = item.json;
      final date = _parseDate(_firstNonEmpty([json['record_date'], json['created_at']]));
      if (date == null || date.year != year) continue;
      final amount = _number(json['amount']);
      final isIncome = '${json['record_type']}' == 'income';
      monthly[date.month - 1] += isIncome ? amount.abs() : -amount.abs();
    }
    return monthly;
  }

  BillingTransactionViewModel _transaction(ApiRecord record) {
    final json = record.json;
    final amount = _number(json['amount']);
    final type = '${json['record_type'] ?? ''}';
    final isIncome = type == 'income';
    final isDebt = type == 'debt' || type == 'receivable';
    final title = _firstNonEmpty([
      json['category'],
      json['record_subtype'],
      json['source_label'],
      json['note'],
    ], fallback: '未分类交易');
    final date = _firstNonEmpty([json['record_date'], json['created_at']]);
    final counterparty = _firstNonEmpty([json['counterparty']], fallback: '');
    final sourceLabel = _firstNonEmpty([
      json['source_label'],
      json['source_type'],
      json['source'],
    ], fallback: isIncome ? '收入记录' : '手动记账');
    final note = _firstNonEmpty([json['note'], json['description']]);
    final subtitle = [
      _relativeDate(_parseDate(date)),
      if (counterparty.isNotEmpty) counterparty,
    ].where((item) => item.isNotEmpty).join(' · ');
    return BillingTransactionViewModel(
      title: title,
      subtitle: subtitle,
      amountText: isIncome ? _money(amount.abs()) : '-${_money(amount.abs())}',
      isIncome: isIncome,
      recordType: type,
      recordDate: _parseDate(date),
      dateText: _dateText(date),
      categoryText: title,
      typeText: isDebt ? '欠款' : (isIncome ? '收入' : '支出'),
      counterpartyText: counterparty.isEmpty ? '未填写对象' : counterparty,
      sourceText: sourceLabel,
      noteText: note.isEmpty ? '暂无备注' : note,
      amount: amount.abs(),
    );
  }

  List<BillingReceivableViewModel> _receivables(Map<String, dynamic> debts) {
    final source = debts['summary'] ?? debts['items'];
    if (source is! List) return const [];
    return source.whereType<Map>().map((item) {
      final json = Map<String, dynamic>.from(item);
      final amount = _number(
        json['remaining'] ??
            json['total_amount'] ??
            json['unsettled_amount'] ??
            json['amount'],
      );
      return BillingReceivableViewModel(
        counterparty: _firstNonEmpty([json['counterparty']], fallback: '未填写对象'),
        amountText: _money(amount),
      );
    }).toList();
  }

  num _receivableTotal(
    Map<String, dynamic> debts,
    List<BillingReceivableViewModel> receivables,
  ) {
    final total = _number(debts['total_amount'] ?? debts['remaining']);
    if (total != 0) return total;
    final source = debts['summary'] ?? debts['items'];
    if (source is List) {
      return source.whereType<Map>().fold<num>(0, (sum, item) {
        return sum +
            _number(
              item['remaining'] ??
                  item['total_amount'] ??
                  item['unsettled_amount'] ??
                  item['amount'],
            );
      });
    }
    return receivables.isEmpty ? 0 : _number(receivables.first.amountText);
  }
}

class BillingViewModel {
  const BillingViewModel({
    required this.incomeText,
    required this.expenseText,
    required this.netProfitText,
    required this.debtText,
    required this.transactions,
    required this.receivables,
    this.insightText,
    this.monthlyTrend = const [],
  });

  final String incomeText;
  final String expenseText;
  final String netProfitText;
  final String debtText;
  final String? insightText;
  final List<BillingTransactionViewModel> transactions;
  final List<BillingReceivableViewModel> receivables;

  /// 12 个月净收益曲线（index 0 = 1 月），数据源来自已加载交易按月聚合。
  final List<double> monthlyTrend;

  bool get isDeficit => netProfitText.startsWith('-');
}

class BillingTransactionViewModel {
  const BillingTransactionViewModel({
    required this.title,
    required this.subtitle,
    required this.amountText,
    required this.isIncome,
    required this.recordType,
    required this.recordDate,
    required this.dateText,
    required this.categoryText,
    required this.typeText,
    required this.counterpartyText,
    required this.sourceText,
    required this.noteText,
    required this.amount,
  });

  final String title;
  final String subtitle;
  final String amountText;
  final bool isIncome;
  final String recordType;
  final DateTime? recordDate;
  final String dateText;
  final String categoryText;
  final String typeText;
  final String counterpartyText;
  final String sourceText;
  final String noteText;
  final num amount;

  bool get isDebt => recordType == 'debt' || recordType == 'receivable';
}

class BillingReceivableViewModel {
  const BillingReceivableViewModel({
    required this.counterparty,
    required this.amountText,
  });

  final String counterparty;
  final String amountText;
}

String _firstNonEmpty(List<Object?> values, {String fallback = ''}) {
  for (final value in values) {
    final text = '$value'.trim();
    if (value != null && text.isNotEmpty && text != 'null') return text;
  }
  return fallback;
}

num _number(Object? value) {
  if (value is num) return value;
  final text = '$value'.replaceAll('¥', '').replaceAll(',', '');
  return num.tryParse(text) ?? 0;
}

DateTime? _parseDate(String value) {
  if (value.isEmpty) return null;
  final normalized = value.length >= 10 ? value.substring(0, 10) : value;
  final parsed = DateTime.tryParse(normalized);
  if (parsed != null) return parsed;
  final parts = normalized.split('-');
  if (parts.length != 3) return null;
  final year = int.tryParse(parts[0]);
  final month = int.tryParse(parts[1]);
  final day = int.tryParse(parts[2]);
  if (year == null || month == null || day == null) return null;
  return DateTime(year, month, day);
}

String _relativeDate(DateTime? date) {
  if (date == null) return '';
  final now = DateTime.now();
  final today = DateTime(now.year, now.month, now.day);
  final target = DateTime(date.year, date.month, date.day);
  final diffDays = today.difference(target).inDays;
  if (diffDays <= 0) return '今天';
  if (diffDays == 1) return '昨天';
  if (diffDays < 7) return '$diffDays 天前';
  if (diffDays < 14) return '上周';
  if (target.year == today.year) return '${target.month}月${target.day}日';
  return '${target.year}年${target.month}月${target.day}日';
}

String _dateText(String value) {
  if (value.isEmpty) return '未填写日期';
  return value.length >= 10 ? value.substring(0, 10) : value;
}

String _money(num value) {
  final prefix = value < 0 ? '-¥' : '¥';
  final abs = value.abs();
  if (abs == abs.roundToDouble()) return '$prefix${abs.toInt()}';
  return '$prefix${abs.toStringAsFixed(2)}';
}

String _signedCompactMoney(num value) {
  if (value < 0) return '-${_compactMoney(value.abs())}';
  return _compactMoney(value);
}

String _compactMoney(num value) {
  final abs = value.abs();
  if (abs < 100000) return _money(value);
  final unit = abs >= 100000000 ? '亿' : '万';
  final divisor = unit == '亿' ? 100000000 : 10000;
  final text = _trimDecimal(abs / divisor);
  final prefix = value < 0 ? '-¥' : '¥';
  return '$prefix$text$unit';
}

String _trimDecimal(num value) {
  final fixed = value.toStringAsFixed(1);
  return fixed.endsWith('.0') ? fixed.substring(0, fixed.length - 2) : fixed;
}

String _insightText({
  required num income,
  required num expense,
  required num netProfit,
}) {
  if (netProfit < 0) {
    return '本年支出高于收入，优先复盘大额支出和未结人工。';
  }
  if (expense == 0 && income == 0) {
    return '暂无收支数据，建议先补齐近期记账记录。';
  }
  if (expense > income * 0.8) {
    return '支出接近收入，建议关注成本占比和欠款回收。';
  }
  return '收支结构较稳，建议持续跟进欠款和季节性成本。';
}
