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
    expect(model.transactions, hasLength(1));
    expect(model.transactions.single.title, '肥料');
    expect(model.transactions.single.amountText, '-¥200');
    expect(model.receivables, hasLength(1));
    expect(model.receivables.single.counterparty, '老王');
    expect(model.receivables.single.amountText, '¥200');
    expect(adapter.find('GET', '/costs').query['size'], 10);
    expect(adapter.find('GET', '/debts').query['size'], 10);
  });
}
