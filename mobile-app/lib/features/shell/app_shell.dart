import 'dart:async';

import 'package:flutter/material.dart';

import '../../app/app_dependencies.dart';
import '../../theme/app_colors.dart';
import '../billing/billing_screen.dart';
import '../home/home_screen.dart';
import '../profile/profile_screen.dart';
import '../workbench/workbench_screen.dart';
import '../yaya/yaya_screen.dart';
import 'bottom_tab_bar.dart';

class AppShell extends StatefulWidget {
  const AppShell({
    super.key,
    required this.dependencies,
    this.initialIndex = 0,
    this.onLogout,
  });

  final AppDependencies dependencies;
  final int initialIndex;
  final Future<void> Function()? onLogout;

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  late int selectedIndex = widget.initialIndex;

  @override
  void initState() {
    super.initState();
    unawaited(widget.dependencies.loadAppOverview().catchError((Object _) {}));
  }

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
            YayaScreen(repository: widget.dependencies.yaya),
            const BillingScreen(),
            ProfileScreen(
              repository: widget.dependencies.profile,
              onLogout: widget.onLogout,
            ),
          ],
        ),
      ),
    );
  }
}
