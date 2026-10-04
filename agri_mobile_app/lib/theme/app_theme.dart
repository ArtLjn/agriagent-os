import 'package:flutter/cupertino.dart' show CupertinoPageTransitionsBuilder;
import 'package:flutter/material.dart';

import 'app_colors.dart';
import 'app_text_styles.dart';

class AppTheme {
  const AppTheme._();

  static ThemeData light() {
    final shape =
        RoundedRectangleBorder(borderRadius: BorderRadius.circular(16));
    return ThemeData(
      useMaterial3: true,
      pageTransitionsTheme: const PageTransitionsTheme(builders: {
        TargetPlatform.android: _FarmPageTransitionsBuilder(),
        TargetPlatform.fuchsia: _FarmPageTransitionsBuilder(),
        TargetPlatform.linux: _FarmPageTransitionsBuilder(),
        TargetPlatform.windows: _FarmPageTransitionsBuilder(),
        TargetPlatform.iOS: CupertinoPageTransitionsBuilder(),
        TargetPlatform.macOS: CupertinoPageTransitionsBuilder(),
      }),
      colorScheme: ColorScheme.fromSeed(
        seedColor: AppColors.blue,
        primary: AppColors.blue,
        secondary: AppColors.greenDark,
        surface: AppColors.surface,
        onSurface: AppColors.ink,
        surfaceTint: Colors.transparent,
      ),
      scaffoldBackgroundColor: AppColors.background,
      fontFamily: 'System',
      splashFactory: NoSplash.splashFactory,
      highlightColor: Colors.transparent,
      dividerColor: AppColors.lineSoft,
      dividerTheme: const DividerThemeData(color: AppColors.lineSoft),
      appBarTheme: const AppBarTheme(
        backgroundColor: AppColors.surface,
        foregroundColor: AppColors.ink,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        centerTitle: false,
        titleTextStyle: AppTextStyles.title,
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size(44, 52),
          shape: shape,
          textStyle: AppTextStyles.listTitle,
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          minimumSize: const Size(44, 52),
          shape: shape,
          side: const BorderSide(color: AppColors.line),
          textStyle: AppTextStyles.listTitle,
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          minimumSize: const Size(44, 44),
          textStyle: AppTextStyles.body,
        ),
      ),
      dialogTheme: DialogThemeData(
        backgroundColor: AppColors.surface,
        surfaceTintColor: Colors.transparent,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
        titleTextStyle: AppTextStyles.title,
        contentTextStyle: AppTextStyles.body,
      ),
      bottomSheetTheme: const BottomSheetThemeData(
        backgroundColor: AppColors.surface,
        surfaceTintColor: Colors.transparent,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
        ),
        clipBehavior: Clip.antiAlias,
      ),
      snackBarTheme: SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
        backgroundColor: AppColors.navy,
        contentTextStyle: AppTextStyles.body.copyWith(color: Colors.white),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      ),
      textSelectionTheme:
          const TextSelectionThemeData(cursorColor: AppColors.blue),
    );
  }
}

// 动效参数集中维护，导航、页面和弹层共享同一节奏。
class AppMotion {
  const AppMotion._();

  static const tabDuration = Duration(milliseconds: 220);
  static const pageDuration = Duration(milliseconds: 280);
  static const exitDuration = Duration(milliseconds: 220);
  static const sheetDuration = Duration(milliseconds: 260);
  static const curve = Curves.easeOutCubic;

  static AnimationStyle sheetStyle(BuildContext context) =>
      MediaQuery.disableAnimationsOf(context)
          ? AnimationStyle.noAnimation
          : const AnimationStyle(
              duration: sheetDuration, reverseDuration: exitDuration);
}

class _FarmPageTransitionsBuilder extends PageTransitionsBuilder {
  const _FarmPageTransitionsBuilder();

  @override
  Duration get transitionDuration => AppMotion.pageDuration;

  @override
  Duration get reverseTransitionDuration => AppMotion.exitDuration;

  @override
  Widget buildTransitions<T>(
      PageRoute<T> route,
      BuildContext context,
      Animation<double> animation,
      Animation<double> secondaryAnimation,
      Widget child) {
    if (MediaQuery.disableAnimationsOf(context)) return child;
    return SlideTransition(
      position: secondaryAnimation.drive(
          Tween(begin: Offset.zero, end: const Offset(-0.01, 0))
              .chain(CurveTween(curve: AppMotion.curve))),
      child: FadeTransition(
        key: const ValueKey('page-route-fade'),
        opacity: animation.drive(
            CurveTween(curve: const Interval(0, 0.7, curve: AppMotion.curve))),
        child: SlideTransition(
          key: const ValueKey('page-route-slide'),
          position: animation.drive(
              Tween(begin: const Offset(0.035, 0), end: Offset.zero)
                  .chain(CurveTween(curve: AppMotion.curve))),
          child: child,
        ),
      ),
    );
  }
}
