import 'package:flutter/material.dart';

import 'app_colors.dart';

class AppTextStyles {
  const AppTextStyles._();

  /// Hero / 页面大标题 — 28-34px
  static const title = TextStyle(
    fontSize: 24,
    height: 1.05,
    fontWeight: FontWeight.w900,
    color: AppColors.ink,
    letterSpacing: 0,
  );

  /// 区块标题 — 20-24px
  static const sectionTitle = TextStyle(
    fontSize: 16,
    height: 1.2,
    fontWeight: FontWeight.w900,
    color: AppColors.ink,
    letterSpacing: 0,
  );

  /// 正文 / 列表标题 — 15-16px
  static const body = TextStyle(
    fontSize: 14,
    height: 20 / 14,
    fontWeight: FontWeight.w500,
    color: AppColors.muted,
    letterSpacing: 0,
  );

  /// 辅助文字 / 标签 / Caption — 12-13px
  static const small = TextStyle(
    fontSize: 12,
    height: 16 / 12,
    fontWeight: FontWeight.w600,
    color: AppColors.muted,
    letterSpacing: 0,
  );

  static const tab = TextStyle(
    fontSize: 10,
    height: 1.2,
    fontWeight: FontWeight.w800,
    letterSpacing: 0,
  );

  /// 大数字 / 指标 — 20px+
  static const metric = TextStyle(
    fontSize: 20,
    height: 1.05,
    fontWeight: FontWeight.w900,
    color: AppColors.ink,
    letterSpacing: 0,
  );
}
