import 'dart:async';

import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../app/app_dependencies.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_theme.dart';
import '../billing/billing_screen.dart';
import '../business/business_pages.dart';
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

class _AppShellState extends State<AppShell>
    with SingleTickerProviderStateMixin {
  late int selectedIndex = widget.initialIndex;
  int billingRefreshKey = 0;
  double _tabDirection = 1;
  late final _tabController = AnimationController(
      vsync: this, duration: AppMotion.tabDuration, value: 1);
  late final _tabProgress =
      _tabController.drive(CurveTween(curve: AppMotion.curve));
  @override
  void initState() {
    super.initState();
    unawaited(widget.dependencies.loadAppOverview().catchError((Object _) {}));
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  void _selectTab(int index) {
    if (index == selectedIndex) return;
    FocusManager.instance.primaryFocus?.unfocus();
    setState(() {
      _tabDirection = index > selectedIndex ? 1 : -1;
      selectedIndex = index;
    });
    if (MediaQuery.disableAnimationsOf(context)) {
      _tabController.value = 1;
    } else {
      _tabController.forward(from: 0);
    }
  }

  void _refreshBilling() {
    setState(() => billingRefreshKey += 1);
  }

  void _openLedgerCreate(BuildContext context) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => LedgerManualCreatePage(
          repository: widget.dependencies.business,
          onSaved: _refreshBilling,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final showLedgerFab = selectedIndex == 3;
    return Scaffold(
      backgroundColor: AppColors.background,
      floatingActionButton: showLedgerFab
          ? FloatingActionButton.extended(
              heroTag: 'ledger-manual-create',
              onPressed: () => _openLedgerCreate(context),
              backgroundColor: AppColors.blue,
              foregroundColor: Colors.white,
              elevation: 0,
              shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(16)),
              icon: const Icon(LucideIcons.plus, size: 20),
              label: const Text('记一笔'),
            )
          : null,
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
        child: FadeTransition(
          key: const ValueKey('main-tab-fade'),
          opacity: _tabProgress.drive(Tween(begin: 0.72, end: 1.0)),
          child: SlideTransition(
            key: const ValueKey('main-tab-slide'),
            position: _tabProgress.drive(Tween(
                begin: Offset(0.018 * _tabDirection, 0), end: Offset.zero)),
            // 稳定的 IndexedStack 保留聊天、输入与滚动位置，切换只改变绘制动效。
            child: IndexedStack(
              index: selectedIndex,
              children: [
                HomeScreen(
                  repository: widget.dependencies.dashboard,
                  onBottomTabChanged: _selectTab,
                ),
                WorkbenchScreen(
                  businessRepository: widget.dependencies.business,
                  onGoHome: () => _selectTab(0),
                  onGoLedger: () => _selectTab(3),
                  onGoYaya: () => _selectTab(2),
                  onGoProfile: () => _selectTab(4),
                  onRecordAgain: () => _selectTab(1),
                  onLedgerSaved: _refreshBilling,
                ),
                YayaScreen(
                  repository: widget.dependencies.yaya,
                  profileRepository: widget.dependencies.profile,
                ),
                BillingScreen(
                  repository: widget.dependencies.billing,
                  refreshKey: billingRefreshKey,
                  onCreateRecord: () => _openLedgerCreate(context),
                ),
                ProfileScreen(
                  repository: widget.dependencies.profile,
                  locations: widget.dependencies.locations,
                  location: widget.dependencies.location,
                  onLogout: widget.onLogout,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
