import 'package:flutter/material.dart';

import '../../theme/app_colors.dart';

class PhoneSafeScaffold extends StatelessWidget {
  const PhoneSafeScaffold({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(child: child),
    );
  }
}
