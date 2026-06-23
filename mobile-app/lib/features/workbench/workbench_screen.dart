import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../shared/widgets/animated_press.dart';
import '../../shared/widgets/reference_page.dart';
import '../../theme/app_colors.dart';
import '../../data/repositories/business_repository.dart';
import '../business/business_pages.dart';
import '../record_flow/record_flow_controller.dart';
import '../record_flow/record_ai_confirm_screen.dart';

class WorkbenchScreen extends StatefulWidget {
  const WorkbenchScreen({
    super.key,
    required this.businessRepository,
    required this.recordFlowController,
    this.onGoHome,
    this.onGoLedger,
    this.onGoYaya,
    this.onGoProfile,
    this.onRecordAgain,
    this.onLedgerSaved,
  });

  final BusinessRepository businessRepository;
  final RecordFlowController recordFlowController;
  final VoidCallback? onGoHome;
  final VoidCallback? onGoLedger;
  final VoidCallback? onGoYaya;
  final VoidCallback? onGoProfile;
  final VoidCallback? onRecordAgain;
  final VoidCallback? onLedgerSaved;

  @override
  State<WorkbenchScreen> createState() => _WorkbenchScreenState();
}

class _WorkbenchScreenState extends State<WorkbenchScreen> {
  final _recordTextController = TextEditingController();

  bool _parsing = false;

  @override
  void dispose() {
    _recordTextController.dispose();
    super.dispose();
  }

  Future<void> _openAiConfirm(BuildContext context) async {
    if (_parsing) return;
    final text = _recordTextController.text.trim();
    if (text.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('先输入一句话记录')),
      );
      return;
    }
    setState(() => _parsing = true);
    try {
      final draft = await widget.recordFlowController.parse(text);
      if (!context.mounted) return;
      Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => RecordAiConfirmScreen(
            controller: widget.recordFlowController,
            draft: draft,
            onGoHome: widget.onGoHome,
            onGoLedger: widget.onGoLedger,
            onRecordAgain: widget.onRecordAgain,
          ),
        ),
      );
    } catch (_) {
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('暂时无法识别记录，请稍后再试')),
      );
    } finally {
      if (mounted) setState(() => _parsing = false);
    }
  }

  void _openManualEdit(BuildContext context) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => LedgerManualCreatePage(
          repository: widget.businessRepository,
          onSaved: widget.onLedgerSaved,
          onBottomTabChanged: (index) => _handleBusinessBottomTab(
            context,
            index,
          ),
        ),
      ),
    );
  }

  void _openBusinessPage(BuildContext context, Widget page) {
    Navigator.of(context).push(MaterialPageRoute(builder: (_) => page));
  }

  void _handleBusinessBottomTab(BuildContext context, int index) {
    Navigator.of(context).popUntil((route) => route.isFirst);
    switch (index) {
      case 0:
        widget.onGoHome?.call();
        return;
      case 1:
        widget.onRecordAgain?.call();
        return;
      case 3:
        widget.onGoLedger?.call();
        return;
      case 2:
        widget.onGoYaya?.call();
        return;
      case 4:
        widget.onGoProfile?.call();
        return;
      default:
        return;
    }
  }

  @override
  Widget build(BuildContext context) {
    return _WorkbenchPage(
      headerTrailing: const HeaderIconButton(icon: LucideIcons.clock),
      children: [
        _AiRecordHero(
          parsing: _parsing,
          controller: _recordTextController,
          onSubmit: () => _openAiConfirm(context),
          onManualTap: () => _openManualEdit(context),
          onFarmLogTap: () => _openBusinessPage(
            context,
            FarmLogCreatePage(
              repository: widget.businessRepository,
              onBottomTabChanged: (index) =>
                  _handleBusinessBottomTab(context, index),
            ),
          ),
          onWageTap: () => _openBusinessPage(
            context,
            WageCreatePage(
              repository: widget.businessRepository,
              onBottomTabChanged: (index) =>
                  _handleBusinessBottomTab(context, index),
            ),
          ),
        ),
        const _TodayMetricsSection(),
        const _ReportShortcutCard(),
        _ToolSection(
          onCycleTap: () => _openBusinessPage(
            context,
            FarmCycleListPage(
              repository: widget.businessRepository,
              onBottomTabChanged: (index) =>
                  _handleBusinessBottomTab(context, index),
            ),
          ),
          onWorkerTap: () => _openBusinessPage(
            context,
            WorkerListPage(
              repository: widget.businessRepository,
              onBottomTabChanged: (index) =>
                  _handleBusinessBottomTab(context, index),
            ),
          ),
          onTemplateTap: () => _openBusinessPage(
            context,
            CropTemplateListPage(
              repository: widget.businessRepository,
              onBottomTabChanged: (index) =>
                  _handleBusinessBottomTab(context, index),
            ),
          ),
          onRecentTap: () => widget.onGoLedger?.call(),
          onPatchRecordTap: () => _openManualEdit(context),
          onWageSettlementTap: () => _openBusinessPage(
            context,
            WageCreatePage(
              repository: widget.businessRepository,
              onBottomTabChanged: (index) =>
                  _handleBusinessBottomTab(context, index),
            ),
          ),
        ),
      ],
    );
  }
}

class _WorkbenchPage extends StatelessWidget {
  const _WorkbenchPage({
    required this.children,
    this.headerTrailing,
  });

  final List<Widget> children;
  final Widget? headerTrailing;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.only(bottom: 120),
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 430),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(20, 14, 20, 0),
                  child: ReferenceHeader(
                    trailing: headerTrailing,
                    showLogo: true,
                  ),
                ),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      const SizedBox(height: 14),
                      ...children,
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _SectionCard extends StatelessWidget {
  const _SectionCard({required this.child, this.padding});

  final Widget child;
  final EdgeInsets? padding;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(top: 16),
      padding: padding ?? const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: AppColors.lineSoft),
        boxShadow: const [
          BoxShadow(
            color: Color(0x06000000),
            blurRadius: 16,
            offset: Offset(0, 6),
          ),
        ],
      ),
      child: child,
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle({required this.icon, required this.title, this.hint});

  final IconData icon;
  final String title;
  final String? hint;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 28,
          height: 28,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: AppColors.blueSoft,
            borderRadius: BorderRadius.circular(8),
          ),
          child: Icon(icon, size: 15, color: AppColors.blue),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: const TextStyle(
                  color: AppColors.ink,
                  fontSize: 16,
                  fontWeight: FontWeight.w800,
                  letterSpacing: 0,
                ),
              ),
              if (hint != null) ...[
                const SizedBox(height: 1),
                Text(
                  hint!,
                  style: const TextStyle(
                    color: AppColors.subtle,
                    fontSize: 11.5,
                    fontWeight: FontWeight.w500,
                    letterSpacing: 0,
                  ),
                ),
              ],
            ],
          ),
        ),
      ],
    );
  }
}

class _AiRecordHero extends StatelessWidget {
  const _AiRecordHero({
    required this.parsing,
    required this.controller,
    required this.onSubmit,
    required this.onManualTap,
    required this.onFarmLogTap,
    required this.onWageTap,
  });

  final bool parsing;
  final TextEditingController controller;
  final VoidCallback onSubmit;
  final VoidCallback onManualTap;
  final VoidCallback onFarmLogTap;
  final VoidCallback onWageTap;

  @override
  Widget build(BuildContext context) {
    final hintText = parsing ? '正在识别记录...' : '例：买肥料 300，老王工资 200';
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 20, 20, 16),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: AppColors.lineSoft),
        boxShadow: const [
          BoxShadow(
            color: Color(0x08000000),
            blurRadius: 20,
            offset: Offset(0, 8),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: AppColors.blueSoft,
                  borderRadius: BorderRadius.circular(999),
                ),
                child: const Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(LucideIcons.sparkles, size: 12, color: AppColors.blue),
                    SizedBox(width: 4),
                    Text(
                      '芽芽智能填写',
                      style: TextStyle(
                        color: AppColors.blue,
                        fontSize: 11,
                        fontWeight: FontWeight.w800,
                        letterSpacing: 0.2,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          const Text(
            '今天要记什么？',
            style: TextStyle(
              color: AppColors.ink,
              fontSize: 22,
              height: 28 / 22,
              fontWeight: FontWeight.w900,
              letterSpacing: -0.2,
            ),
          ),
          const SizedBox(height: 4),
          const Text(
            '账目、农事或工资，一句话自动识别',
            style: TextStyle(
              color: AppColors.muted,
              fontSize: 13,
              height: 18 / 13,
              fontWeight: FontWeight.w500,
              letterSpacing: 0,
            ),
          ),
          const SizedBox(height: 14),
          _SmartFillInputRow(
            parsing: parsing,
            controller: controller,
            hintText: hintText,
            onSubmit: onSubmit,
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: _ShortcutTile(
                  icon: LucideIcons.pencilLine,
                  label: '手动记一笔',
                  onTap: onManualTap,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: _ShortcutTile(
                  icon: LucideIcons.sprout,
                  label: '记农事',
                  onTap: onFarmLogTap,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: _ShortcutTile(
                  icon: LucideIcons.handCoins,
                  label: '记工资',
                  onTap: onWageTap,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _SmartFillInputRow extends StatelessWidget {
  const _SmartFillInputRow({
    required this.parsing,
    required this.controller,
    required this.hintText,
    required this.onSubmit,
  });

  final bool parsing;
  final TextEditingController controller;
  final String hintText;
  final VoidCallback onSubmit;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 52,
      padding: const EdgeInsets.only(left: 16, right: 6),
      decoration: BoxDecoration(
        color: AppColors.surface2,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.line),
      ),
      child: Row(
        children: [
          Expanded(
            child: Material(
              color: Colors.transparent,
              child: TextField(
                controller: controller,
                enabled: !parsing,
                minLines: 1,
                maxLines: 1,
                textInputAction: TextInputAction.done,
                onSubmitted: (_) => onSubmit(),
                style: const TextStyle(
                  color: AppColors.ink,
                  fontSize: 15,
                  fontWeight: FontWeight.w600,
                  letterSpacing: 0,
                ),
                decoration: InputDecoration(
                  hintText: hintText,
                  hintStyle: const TextStyle(
                    color: AppColors.subtle,
                    fontSize: 14,
                    fontWeight: FontWeight.w500,
                    letterSpacing: 0,
                  ),
                  border: InputBorder.none,
                  isDense: true,
                  contentPadding: EdgeInsets.zero,
                ),
              ),
            ),
          ),
          const SizedBox(width: 6),
          AnimatedPress(
            scale: 0.95,
            onTap: parsing ? null : onSubmit,
            child: Container(
              height: 40,
              padding: const EdgeInsets.symmetric(horizontal: 14),
              decoration: BoxDecoration(
                color: AppColors.blue,
                borderRadius: BorderRadius.circular(12),
                boxShadow: [
                  BoxShadow(
                    color: AppColors.blue.withValues(alpha: 0.24),
                    blurRadius: 10,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
              child: Center(
                child: parsing
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(
                          strokeWidth: 2.2,
                          color: Colors.white,
                        ),
                      )
                    : const Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(
                            LucideIcons.sparkles,
                            color: Colors.white,
                            size: 14,
                          ),
                          SizedBox(width: 4),
                          Text(
                            '识别',
                            style: TextStyle(
                              color: Colors.white,
                              fontSize: 14,
                              fontWeight: FontWeight.w800,
                              letterSpacing: 0.3,
                            ),
                          ),
                        ],
                      ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ShortcutTile extends StatelessWidget {
  const _ShortcutTile({
    required this.icon,
    required this.label,
    required this.onTap,
  });

  final IconData icon;
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return AnimatedPress(
      scale: 0.96,
      onTap: onTap,
      child: Container(
        height: 44,
        padding: const EdgeInsets.symmetric(horizontal: 6),
        decoration: BoxDecoration(
          color: AppColors.surface2,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, size: 15, color: AppColors.blue),
            const SizedBox(width: 5),
            Flexible(
              child: FittedBox(
                fit: BoxFit.scaleDown,
                child: Text(
                  label,
                  maxLines: 1,
                  style: const TextStyle(
                    color: AppColors.ink2,
                    fontSize: 12.5,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 0,
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _TodayMetricsSection extends StatelessWidget {
  const _TodayMetricsSection();

  @override
  Widget build(BuildContext context) {
    return _SectionCard(
      padding: const EdgeInsets.fromLTRB(20, 18, 20, 18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _SectionTitle(
            icon: LucideIcons.layoutDashboard,
            title: '今日概览',
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: _MetricTile(
                  label: '今日已记',
                  value: '3',
                  unit: '条',
                  icon: LucideIcons.pencilLine,
                  accent: AppColors.blue,
                  accentSoft: AppColors.blueSoft,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: _MetricTile(
                  label: '待确认',
                  value: '1',
                  unit: '条',
                  icon: LucideIcons.circleAlert,
                  accent: AppColors.amber,
                  accentSoft: AppColors.amberSoft,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(
                child: _MetricTile(
                  label: '工资待结',
                  value: '2',
                  unit: '人',
                  icon: LucideIcons.users,
                  accent: AppColors.green,
                  accentSoft: AppColors.greenSoft,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: _MetricTile(
                  label: '本周支出',
                  value: '1,280',
                  unit: '¥',
                  icon: LucideIcons.wallet,
                  accent: AppColors.purple,
                  accentSoft: AppColors.purpleSoft,
                  currencyPrefix: true,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _MetricTile extends StatelessWidget {
  const _MetricTile({
    required this.label,
    required this.value,
    required this.unit,
    required this.icon,
    required this.accent,
    required this.accentSoft,
    this.currencyPrefix = false,
  });

  final String label;
  final String value;
  final String unit;
  final IconData icon;
  final Color accent;
  final Color accentSoft;
  final bool currencyPrefix;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(14, 14, 14, 14),
      decoration: BoxDecoration(
        color: AppColors.surface2,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Container(
            width: 32,
            height: 32,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: accentSoft,
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(icon, size: 16, color: accent),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: AppColors.muted,
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    letterSpacing: 0,
                  ),
                ),
                const SizedBox(height: 4),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.baseline,
                  textBaseline: TextBaseline.alphabetic,
                  children: [
                    if (currencyPrefix) ...[
                      Text(
                        unit,
                        style: TextStyle(
                          color: AppColors.ink,
                          fontSize: 13,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      const SizedBox(width: 1),
                    ],
                    Flexible(
                      child: FittedBox(
                        fit: BoxFit.scaleDown,
                        alignment: Alignment.centerLeft,
                        child: Text(
                          value,
                          maxLines: 1,
                          style: const TextStyle(
                            color: AppColors.ink,
                            fontSize: 22,
                            fontWeight: FontWeight.w900,
                            letterSpacing: -0.3,
                          ),
                        ),
                      ),
                    ),
                    if (!currencyPrefix) ...[
                      const SizedBox(width: 2),
                      Text(
                        unit,
                        style: const TextStyle(
                          color: AppColors.muted,
                          fontSize: 12,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ],
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _ReportShortcutCard extends StatelessWidget {
  const _ReportShortcutCard();

  @override
  Widget build(BuildContext context) {
    return _SectionCard(
      padding: const EdgeInsets.fromLTRB(20, 18, 20, 18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _SectionTitle(
            icon: LucideIcons.barChart3,
            title: '经营报告',
            hint: '本周12条记录 · 本月支出 ¥4,820',
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: _ReportButton(
                  icon: LucideIcons.fileText,
                  label: '生成周报',
                  hint: '本周经营汇总',
                  accent: AppColors.blue,
                  accentSoft: AppColors.blueSoft,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: _ReportButton(
                  icon: LucideIcons.calendarDays,
                  label: '生成月报',
                  hint: '本月经营汇总',
                  accent: AppColors.green,
                  accentSoft: AppColors.greenSoft,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _ReportButton extends StatelessWidget {
  const _ReportButton({
    required this.icon,
    required this.label,
    required this.hint,
    required this.accent,
    required this.accentSoft,
  });

  final IconData icon;
  final String label;
  final String hint;
  final Color accent;
  final Color accentSoft;

  @override
  Widget build(BuildContext context) {
    return AnimatedPress(
      scale: 0.97,
      child: Container(
        padding: const EdgeInsets.fromLTRB(14, 12, 12, 12),
        decoration: BoxDecoration(
          color: accentSoft,
          borderRadius: BorderRadius.circular(14),
        ),
        child: Row(
          children: [
            Container(
              width: 30,
              height: 30,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: BorderRadius.circular(9),
              ),
              child: Icon(icon, size: 15, color: accent),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    label,
                    style: TextStyle(
                      color: accent,
                      fontSize: 13,
                      fontWeight: FontWeight.w800,
                      letterSpacing: 0,
                    ),
                  ),
                  const SizedBox(height: 1),
                  Text(
                    hint,
                    style: const TextStyle(
                      color: AppColors.muted,
                      fontSize: 11,
                      fontWeight: FontWeight.w500,
                      letterSpacing: 0,
                    ),
                  ),
                ],
              ),
            ),
            Icon(
              LucideIcons.chevronRight,
              size: 14,
              color: accent.withValues(alpha: 0.6),
            ),
          ],
        ),
      ),
    );
  }
}

class _ToolSection extends StatelessWidget {
  const _ToolSection({
    required this.onCycleTap,
    required this.onWorkerTap,
    required this.onTemplateTap,
    required this.onRecentTap,
    required this.onPatchRecordTap,
    required this.onWageSettlementTap,
  });

  final VoidCallback onCycleTap;
  final VoidCallback onWorkerTap;
  final VoidCallback onTemplateTap;
  final VoidCallback onRecentTap;
  final VoidCallback onPatchRecordTap;
  final VoidCallback onWageSettlementTap;

  @override
  Widget build(BuildContext context) {
    final items = [
      _ToolItem(
        label: '建批次',
        icon: LucideIcons.layers,
        onTap: onCycleTap,
      ),
      _ToolItem(
        label: '新增工人',
        icon: LucideIcons.userPlus,
        onTap: onWorkerTap,
      ),
      _ToolItem(
        label: '建模板',
        icon: LucideIcons.layoutTemplate,
        onTap: onTemplateTap,
      ),
      _ToolItem(
        label: '最近记录',
        icon: LucideIcons.history,
        onTap: onRecentTap,
      ),
      _ToolItem(
        label: '补记录',
        icon: LucideIcons.filePlus,
        onTap: onPatchRecordTap,
      ),
      _ToolItem(
        label: '工资结算',
        icon: LucideIcons.coins,
        onTap: onWageSettlementTap,
      ),
    ];

    return _SectionCard(
      padding: const EdgeInsets.fromLTRB(20, 18, 20, 18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _SectionTitle(
            icon: LucideIcons.briefcaseBusiness,
            title: '常用工具',
          ),
          const SizedBox(height: 16),
          GridView.count(
            crossAxisCount: 3,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            mainAxisSpacing: 10,
            crossAxisSpacing: 10,
            childAspectRatio: 1.05,
            children: items
                .map((item) => _ToolTile(item: item))
                .toList(growable: false),
          ),
        ],
      ),
    );
  }
}

class _ToolTile extends StatelessWidget {
  const _ToolTile({required this.item});

  final _ToolItem item;

  @override
  Widget build(BuildContext context) {
    return AnimatedPress(
      scale: 0.95,
      onTap: item.onTap,
      child: Container(
        decoration: BoxDecoration(
          color: AppColors.surface2,
          borderRadius: BorderRadius.circular(16),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: 36,
              height: 36,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: BorderRadius.circular(11),
                border: Border.all(color: AppColors.lineSoft),
              ),
              child: Icon(item.icon, size: 17, color: AppColors.ink2),
            ),
            const SizedBox(height: 7),
            Text(
              item.label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                color: AppColors.ink2,
                fontSize: 12.5,
                fontWeight: FontWeight.w700,
                letterSpacing: 0,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ToolItem {
  const _ToolItem({
    required this.label,
    required this.icon,
    required this.onTap,
  });

  final String label;
  final IconData icon;
  final VoidCallback onTap;
}

class HeaderIconButton extends StatelessWidget {
  const HeaderIconButton({super.key, required this.icon, this.onTap});

  final IconData icon;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return AnimatedPress(
      scale: 0.94,
      onTap: onTap,
      child: Container(
        width: 40,
        height: 40,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppColors.lineSoft),
        ),
        child: Icon(icon, size: 18, color: AppColors.ink),
      ),
    );
  }
}
