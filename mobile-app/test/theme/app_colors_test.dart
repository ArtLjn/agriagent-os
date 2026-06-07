import 'package:farm_manager_app/theme/app_colors.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('芽芽主题不使用紫色', () {
    expect(AppColors.teal.toARGB32(), isNot(equals(0xFF8559F6)));
    expect(AppColors.tealSoft.toARGB32(), isNot(equals(0xFFF3EFFF)));
  });

  test('核心色值与 HTML 设计稿一致', () {
    expect(AppColors.background, const Color(0xFFF6F8FB));
    expect(AppColors.surface, Colors.white);
    expect(AppColors.ink, const Color(0xFF101828));
    expect(AppColors.blue, const Color(0xFF4078FF));
    expect(AppColors.cyan, const Color(0xFF0EA5B8));
    expect(AppColors.teal, const Color(0xFF0891B2));
  });
}
