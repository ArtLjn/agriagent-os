import 'package:dio/dio.dart';
import 'package:farm_manager_app/data/api/api_client.dart';
import 'package:farm_manager_app/data/repositories/billing_repository.dart';
import 'package:farm_manager_app/features/billing/billing_controller.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/api_test_fixtures.dart';

void main() {
  test('账本 controller 聚合成本列表、年度汇总和欠款提醒', () async {
    final adapter = RecordingAdapter({
      '/costs': paginatedCostsResponse,
      '/costs/summary/2026': yearlySummaryResponse,
      '/debts': debtsResponse,
    });
    final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
    dio.httpClientAdapter = adapter;
    final controller = BillingController(
      repository: BillingRepository(ApiClient(dio: dio)),
      year: 2026,
    );

    final model = await controller.load();

    expect(model.incomeText, '¥0');
    expect(model.expenseText, '¥200');
    expect(model.netProfitText, '-¥200');
    expect(model.insightText, contains('支出高于收入'));
    expect(model.transactions, hasLength(1));
    expect(model.transactions.single.title, '肥料');
    expect(model.transactions.single.amountText, '-¥200');
    expect(model.receivables, hasLength(1));
    expect(model.receivables.single.counterparty, '老王');
    expect(model.receivables.single.amountText, '¥200');
    expect(adapter.find('GET', '/costs').query['size'], 10);
    expect(adapter.find('GET', '/debts').query['size'], 10);
  });

  test('成本记录即使返回负金额也按支出显示', () async {
    final adapter = RecordingAdapter({
      '/costs': {
        'items': [
          {...costRecordResponse, 'record_type': 'cost', 'amount': '-200'}
        ],
        'total': 1,
      },
      '/costs/summary/2026': yearlySummaryResponse,
      '/debts': debtsResponse,
    });
    final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
    dio.httpClientAdapter = adapter;
    final controller = BillingController(
      repository: BillingRepository(ApiClient(dio: dio)),
      year: 2026,
    );

    final model = await controller.load();

    expect(model.transactions.single.isIncome, false);
    expect(model.transactions.single.amountText, '-¥200');
  });

  test('账本年度净收益大金额使用紧凑显示', () async {
    final adapter = RecordingAdapter({
      '/costs': paginatedCostsResponse,
      '/costs/summary/2026': {
        ...yearlySummaryResponse,
        'net_profit': '-110970.16',
      },
      '/debts': debtsResponse,
    });
    final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
    dio.httpClientAdapter = adapter;
    final controller = BillingController(
      repository: BillingRepository(ApiClient(dio: dio)),
      year: 2026,
    );

    final model = await controller.load();

    expect(model.netProfitText, '-¥11.1万');
  });

  test('账本概览指标大金额使用万和亿', () async {
    final adapter = RecordingAdapter({
      '/costs': paginatedCostsResponse,
      '/costs/summary/2026': {
        ...yearlySummaryResponse,
        'total_income': '123456789',
        'total_cost': '116470.16',
        'net_profit': '123340318.84',
      },
      '/debts': {
        'summary': [
          {'counterparty': '老王', 'remaining': '120000000'}
        ],
      },
    });
    final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
    dio.httpClientAdapter = adapter;
    final controller = BillingController(
      repository: BillingRepository(ApiClient(dio: dio)),
      year: 2026,
    );

    final model = await controller.load();

    expect(model.incomeText, '¥1.2亿');
    expect(model.expenseText, '¥11.6万');
    expect(model.netProfitText, '¥1.2亿');
    expect(model.debtText, '¥1.2亿');
  });
}
