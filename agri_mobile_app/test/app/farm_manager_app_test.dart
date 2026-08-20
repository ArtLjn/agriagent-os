import 'package:farm_manager_app/app/farm_manager_app.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fake_app_dependencies.dart';

void main() {
  testWidgets('应用启用中文本地化用于系统日期选择器', (tester) async {
    await tester.pumpWidget(
      FarmManagerApp(dependencies: FakeAppDependencies()),
    );

    final app = tester.widget<MaterialApp>(find.byType(MaterialApp));

    expect(app.locale, const Locale('zh', 'CN'));
    expect(app.supportedLocales, contains(const Locale('zh', 'CN')));
    expect(app.localizationsDelegates, isNotNull);
  });
}
