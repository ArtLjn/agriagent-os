import 'dart:async';

import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../app/app_dependencies.dart';
import '../../theme/app_colors.dart';
import '../billing/billing_screen.dart';
import '../business/business_pages.dart';
import '../home/home_screen.dart';
import '../record_flow/record_flow_controller.dart';
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
  int billingRefreshKey = 0;
  late final recordFlowController = RecordFlowController(
    workbench: widget.dependencies.workbench,
    billing: widget.dependencies.billing,
  );

  @override
  void initState() {
    super.initState();
    unawaited(widget.dependencies.loadAppOverview().catchError((Object _) {}));
  }

  void _selectTab(int index) => setState(() => selectedIndex = index);

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
          ? FloatingActionButton(
              heroTag: 'ledger-manual-create',
              onPressed: () => _openLedgerCreate(context),
              backgroundColor: AppColors.blue,
              foregroundColor: Colors.white,
              elevation: 4,
              shape: const CircleBorder(),
              child: const Icon(LucideIcons.plus, size: 26),
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
        child: IndexedStack(
          index: selectedIndex,
          children: [
            HomeScreen(
              repository: widget.dependencies.dashboard,
              onBottomTabChanged: _selectTab,
            ),
            WorkbenchScreen(
              businessRepository: widget.dependencies.business,
              recordFlowController: recordFlowController,
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
            ),
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
