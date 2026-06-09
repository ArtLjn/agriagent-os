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
      incomeText: _money(_number(summary['total_income'])),
      expenseText: _money(_number(summary['total_cost'])),
      netProfitText: _signedMoney(_number(summary['net_profit'])),
      debtText: _money(_receivableTotal(debts, receivables)),
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
    final counterparty =
        _firstNonEmpty([json['counterparty']], fallback: '未填写对象');
    return BillingTransactionViewModel(
      title: title,
      subtitle:
          [date, counterparty].where((item) => item.isNotEmpty).join(' · '),
      amountText: isIncome ? _money(amount.abs()) : '-${_money(amount.abs())}',
      isIncome: isIncome,
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
  });

  final String incomeText;
  final String expenseText;
  final String netProfitText;
  final String debtText;
  final List<BillingTransactionViewModel> transactions;
  final List<BillingReceivableViewModel> receivables;
}

class BillingTransactionViewModel {
  const BillingTransactionViewModel({
    required this.title,
    required this.subtitle,
    required this.amountText,
    required this.isIncome,
  });

  final String title;
  final String subtitle;
  final String amountText;
  final bool isIncome;
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

String _money(num value) {
  final prefix = value < 0 ? '-¥' : '¥';
  final abs = value.abs();
  if (abs == abs.roundToDouble()) return '$prefix${abs.toInt()}';
  return '$prefix${abs.toStringAsFixed(2)}';
}

String _signedMoney(num value) {
  if (value < 0) return '-${_money(value.abs())}';
  return _money(value);
}
