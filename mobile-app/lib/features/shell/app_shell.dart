import 'package:flutter/material.dart';

import '../../theme/app_colors.dart';
import '../billing/billing_screen.dart';
import '../home/home_screen.dart';
import '../profile/profile_screen.dart';
import '../workbench/workbench_screen.dart';
import '../yaya/yaya_screen.dart';
import 'bottom_tab_bar.dart';

class AppShell extends StatefulWidget {
  const AppShell({super.key, this.initialIndex = 0});

  final int initialIndex;

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  late int selectedIndex = widget.initialIndex;

  static const pages = [
    HomeScreen(),
    WorkbenchScreen(),
    YayaScreen(),
    BillingScreen(),
    ProfileScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: DecoratedBox(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [AppColors.backgroundTop, AppColors.background],
          ),
        ),
        child: Stack(
          children: [
            IndexedStack(index: selectedIndex, children: pages),
            Positioned(
              left: 20,
              right: 20,
              bottom: 26,
              child: AppBottomTabBar(
                selectedIndex: selectedIndex,
                onChanged: (index) => setState(() => selectedIndex = index),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
