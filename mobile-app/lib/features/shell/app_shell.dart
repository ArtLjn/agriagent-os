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

  void _selectTab(int index) => setState(() => selectedIndex = index);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      bottomNavigationBar: AppBottomTabBar(
        selectedIndex: selectedIndex,
        onChanged: _selectTab,
      ),
      body: DecoratedBox(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [AppColors.backgroundTop, AppColors.background],
          ),
        ),
        child: IndexedStack(
          index: selectedIndex,
          children: [
            const HomeScreen(),
            WorkbenchScreen(
              onGoHome: () => _selectTab(0),
              onGoLedger: () => _selectTab(3),
              onRecordAgain: () => _selectTab(1),
            ),
            const YayaScreen(),
            const BillingScreen(),
            const ProfileScreen(),
          ],
        ),
      ),
    );
  }
}
