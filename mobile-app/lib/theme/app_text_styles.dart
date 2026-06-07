import 'package:flutter/material.dart';

import 'app_colors.dart';

class AppTextStyles {
  const AppTextStyles._();

  static const title = TextStyle(
    fontSize: 23,
    height: 1.05,
    fontWeight: FontWeight.w800,
    color: AppColors.ink,
    letterSpacing: 0,
  );

  static const sectionTitle = TextStyle(
    fontSize: 16,
    height: 1.2,
    fontWeight: FontWeight.w800,
    color: AppColors.ink,
    letterSpacing: 0,
  );

  static const body = TextStyle(
    fontSize: 13,
    height: 20 / 13,
    fontWeight: FontWeight.w500,
    color: AppColors.muted,
    letterSpacing: 0,
  );

  static const small = TextStyle(
    fontSize: 11,
    height: 16 / 11,
    fontWeight: FontWeight.w600,
    color: AppColors.muted,
    letterSpacing: 0,
  );

  static const tab = TextStyle(
    fontSize: 10,
    height: 1.2,
    fontWeight: FontWeight.w700,
    letterSpacing: 0,
  );
}
