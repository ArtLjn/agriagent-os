import 'package:flutter/material.dart';

import 'app_colors.dart';

class AppTextStyles {
  const AppTextStyles._();

  static const title = TextStyle(
    fontSize: 24,
    height: 1.05,
    fontWeight: FontWeight.w800,
    color: AppColors.ink,
    letterSpacing: 0,
  );

  static const sectionTitle = TextStyle(
    fontSize: 17,
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

  static const metric = TextStyle(
    fontSize: 20,
    height: 1.05,
    fontWeight: FontWeight.w800,
    color: AppColors.ink,
    letterSpacing: 0,
  );
}
