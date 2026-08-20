import 'package:flutter/material.dart';

import 'app_colors.dart';

class AppTextStyles {
  const AppTextStyles._();

  static const title = TextStyle(
    fontSize: 22,
    height: 28 / 22,
    fontWeight: FontWeight.w800,
    color: AppColors.ink,
    letterSpacing: 0,
  );

  static const dateTitle = TextStyle(
    fontSize: 18,
    height: 26 / 18,
    fontWeight: FontWeight.w800,
    color: AppColors.ink,
    letterSpacing: 0,
  );

  static const sectionTitle = TextStyle(
    fontSize: 16,
    height: 22 / 16,
    fontWeight: FontWeight.w800,
    color: AppColors.ink,
    letterSpacing: 0,
  );

  static const listTitle = TextStyle(
    fontSize: 15,
    height: 22 / 15,
    fontWeight: FontWeight.w600,
    color: AppColors.ink,
    letterSpacing: 0,
  );

  static const body = TextStyle(
    fontSize: 14,
    height: 21 / 14,
    fontWeight: FontWeight.w500,
    color: AppColors.ink,
    letterSpacing: 0,
  );

  static const small = TextStyle(
    fontSize: 12,
    height: 16 / 12,
    fontWeight: FontWeight.w500,
    color: AppColors.muted,
    letterSpacing: 0,
  );

  static const tab = TextStyle(
    fontSize: 11,
    height: 14 / 11,
    fontWeight: FontWeight.w600,
    letterSpacing: 0,
  );

  static const metric = TextStyle(
    fontSize: 30,
    height: 36 / 30,
    fontWeight: FontWeight.w800,
    color: AppColors.ink,
    letterSpacing: 0,
  );
}
