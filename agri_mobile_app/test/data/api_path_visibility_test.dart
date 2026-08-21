import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('API 路径只允许出现在 data 层', () {
    final lib = Directory('lib');
    final offenders = <String>[];

    for (final entity in lib.listSync(recursive: true)) {
      if (entity is! File || !entity.path.endsWith('.dart')) continue;
      if (entity.path.contains('/data/')) continue;
      final text = entity.readAsStringSync();
      if (RegExp(
        r'"/(agent|costs|debts|weather|planting|cycles|auth|settings|api)/',
      ).hasMatch(text)) {
        offenders.add(entity.path);
      }
    }

    expect(offenders, isEmpty, reason: 'API 路径不能出现在 UI 层: $offenders');
  });
}
