import 'package:farm_manager_app/shared/widgets/city_picker_sheet.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('城市选择器可搜索区县并返回名称和坐标', (tester) async {
    CityPickerResult? selected;

    await tester.pumpWidget(
      MaterialApp(
        home: Builder(
          builder: (context) {
            return Scaffold(
              body: TextButton(
                onPressed: () async {
                  selected = await showCityPickerSheet(
                    context: context,
                    selectedCity: '',
                  );
                },
                child: const Text('选择经营地区'),
              ),
            );
          },
        ),
      ),
    );

    await tester.tap(find.text('选择经营地区'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), '睢宁');
    await tester.pumpAndSettle();
    await tester.tap(find.text('睢宁县'));
    await tester.pumpAndSettle();

    expect(selected?.name, '睢宁县');
    expect(selected?.latitude, 34.20442);
    expect(selected?.longitude, 117.28386);
  });

  testWidgets('城市选择器选择直辖市区县时直接返回', (tester) async {
    CityPickerResult? selected;

    await tester.pumpWidget(
      MaterialApp(
        home: Builder(
          builder: (context) {
            return Scaffold(
              body: TextButton(
                onPressed: () async {
                  selected = await showCityPickerSheet(
                    context: context,
                    selectedCity: '',
                  );
                },
                child: const Text('选择经营地区'),
              ),
            );
          },
        ),
      ),
    );

    await tester.tap(find.text('选择经营地区'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('北京市'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('朝阳区'));
    await tester.pumpAndSettle();

    expect(selected?.name, '朝阳区');
    expect(selected?.latitude, 39.9075);
    expect(selected?.longitude, 116.39723);
  });
}
