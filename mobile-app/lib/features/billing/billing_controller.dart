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
    );
  }

  BillingTransactionViewModel _transaction(ApiRecord record) {
    final json = record.json;
    final amount = _number(json['amount']);
    final type = '${json['record_type'] ?? ''}';
    final isIncome = type == 'income';
    final title = _firstNonEmpty([
      json['category'],
      json['record_subtype'],
      json['source_label'],
      json['note'],
    ], fallback: '未分类交易');
    final date = _firstNonEmpty([json['record_date'], json['created_at']]);
    final counterparty = _firstNonEmpty([json['counterparty']], fallback: '');
    final subtitle = isIncome
        ? [date, if (counterparty.isNotEmpty) counterparty]
            .where((item) => item.isNotEmpty)
            .join(' · ')
        : [date, if (counterparty.isNotEmpty) counterparty else '日常支出']
            .where((item) => item.isNotEmpty)
            .join(' · ');
    return BillingTransactionViewModel(
      title: title,
      subtitle: subtitle,
      amountText: isIncome ? _money(amount.abs()) : '-${_money(amount.abs())}',
      isIncome: isIncome,
      recordType: type,
      recordDate: _parseDate(date),
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
  });

  final String incomeText;
  final String expenseText;
  final String netProfitText;
  final String debtText;
  final String? insightText;
  final List<BillingTransactionViewModel> transactions;
  final List<BillingReceivableViewModel> receivables;
}

class BillingTransactionViewModel {
  const BillingTransactionViewModel({
    required this.title,
    required this.subtitle,
    required this.amountText,
    required this.isIncome,
    required this.recordType,
    required this.recordDate,
    required this.amount,
  });

  final String title;
  final String subtitle;
  final String amountText;
  final bool isIncome;
  final String recordType;
  final DateTime? recordDate;
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
