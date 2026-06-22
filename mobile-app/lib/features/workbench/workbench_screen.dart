import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../shared/assets/app_assets.dart';
import '../../shared/widgets/card_panel.dart';
import '../../shared/widgets/reference_page.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';
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
        const SizedBox(height: 2),
        _SmartFillBanner(
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
        const SizedBox(height: 8),
        const _ReportShortcutCard(),
        const SizedBox(height: 8),
        const _TodayOverviewSection(),
        const SizedBox(height: 8),
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
        const SizedBox(height: 8),
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
        padding: const EdgeInsets.only(bottom: 112),
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
                  padding: const EdgeInsets.symmetric(horizontal: 12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: children,
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

class _RecordCard extends StatelessWidget {
  const _RecordCard({
    required this.child,
    this.padding = const EdgeInsets.all(14),
  });

  final Widget child;
  final EdgeInsets padding;

  @override
  Widget build(BuildContext context) {
    return CardPanel(
      radius: 18,
      padding: padding,
      background: Colors.white,
      borderColor: const Color(0xFFE2EAF4),
      shadow: true,
      child: child,
    );
  }
}

class _GeneratedIcon extends StatelessWidget {
  const _GeneratedIcon({
    required this.asset,
    required this.size,
  });

  final String asset;
  final double size;

  @override
  Widget build(BuildContext context) {
    return Image.asset(
      asset,
      width: size,
      height: size,
      fit: BoxFit.contain,
      errorBuilder: (_, __, ___) => const SizedBox.shrink(),
    );
  }
}

class _SmartFillBanner extends StatelessWidget {
  const _SmartFillBanner({
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
    return LayoutBuilder(
      builder: (context, constraints) {
        final width = constraints.maxWidth;
        final isNarrow = width < 382;
        final hintText = parsing ? '正在识别记录...' : '例：买肥料300，老王工资200';
        return SizedBox(
          width: width,
          child: CardPanel(
            radius: 18,
            padding: EdgeInsets.zero,
            borderColor: const Color(0xFFDCE8F7),
            shadow: true,
            child: ClipRRect(
              borderRadius: BorderRadius.circular(18),
              child: Stack(
                children: [
                  const Positioned.fill(child: _SmartBannerBackground()),
                  Positioned(
                    right: isNarrow ? 36 : 50,
                    top: 18,
                    child: Container(
                      width: isNarrow ? 82 : 94,
                      height: isNarrow ? 82 : 94,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: Colors.white.withValues(alpha: 0.74),
                        border: Border.all(
                          color: const Color(0xFFE3F0FF),
                          width: 1,
                        ),
                        boxShadow: [
                          BoxShadow(
                            color: AppColors.blue.withValues(alpha: 0.09),
                            blurRadius: 18,
                            offset: const Offset(0, 8),
                          ),
                        ],
                      ),
                      child: ClipOval(
                        child: Image.asset(
                          AppAssets.yayaMascotLogo,
                          fit: BoxFit.cover,
                          errorBuilder: (_, __, ___) => const SizedBox.shrink(),
                        ),
                      ),
                    ),
                  ),
                  Padding(
                    padding: const EdgeInsets.fromLTRB(14, 12, 14, 10),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const _SmartFillBadge(),
                        const SizedBox(height: 12),
                        Text(
                          '今天要记什么？',
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: AppTextStyles.title.copyWith(
                            fontSize: 22,
                            height: 28 / 22,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                        const SizedBox(height: 4),
                        SizedBox(
                          width: isNarrow ? 218 : 264,
                          child: Text(
                            '说一句，芽芽会整理成账目、农事或工资',
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: AppTextStyles.body.copyWith(
                              color: AppColors.muted,
                              fontSize: 13.5,
                              height: 18 / 13.5,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                        const SizedBox(height: 12),
                        _SmartFillInputRow(
                          parsing: parsing,
                          controller: controller,
                          hintText: hintText,
                          onSubmit: onSubmit,
                          compact: isNarrow,
                        ),
                        const SizedBox(height: 8),
                        Row(
                          children: [
                            Expanded(
                              child: _SmartShortcutPill(
                                icon: LucideIcons.pencilLine,
                                label: '手动记一笔',
                                color: AppColors.blue,
                                onTap: onManualTap,
                                compact: isNarrow,
                              ),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: _SmartShortcutPill(
                                icon: LucideIcons.sprout,
                                label: '记农事',
                                color: AppColors.greenDark,
                                onTap: onFarmLogTap,
                                compact: isNarrow,
                              ),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: _SmartShortcutPill(
                                icon: LucideIcons.handCoins,
                                label: '记工资',
                                color: AppColors.amber,
                                onTap: onWageTap,
                                compact: isNarrow,
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }
}

class _SmartBannerBackground extends StatelessWidget {
  const _SmartBannerBackground();

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: Colors.white,
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFFFFFFFF), Color(0xFFF9FCFF), Color(0xFFF6FBFF)],
        ),
        boxShadow: [
          BoxShadow(
            color: AppColors.blue.withValues(alpha: 0.05),
            blurRadius: 26,
            offset: const Offset(0, 8),
          ),
        ],
      ),
      child: Stack(
        children: [
          Positioned(
            right: -22,
            top: -18,
            width: 164,
            height: 164,
            child: DecoratedBox(
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: RadialGradient(
                  colors: [
                    AppColors.blue.withValues(alpha: 0.12),
                    AppColors.cyan.withValues(alpha: 0.04),
                    Colors.transparent,
                  ],
                ),
              ),
            ),
          ),
          Positioned(
            right: 14,
            top: 70,
            width: 128,
            height: 116,
            child: DecoratedBox(
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: AppColors.blue.withValues(alpha: 0.04),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _SmartFillBadge extends StatelessWidget {
  const _SmartFillBadge();

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 26,
      padding: const EdgeInsets.symmetric(horizontal: 10),
      decoration: BoxDecoration(
        color: const Color(0xFFF0F7FF),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: const Color(0xFFD4E7FF)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(LucideIcons.sparkles, size: 14, color: AppColors.blue),
          const SizedBox(width: 5),
          Text(
            '芽芽智能填写',
            style: AppTextStyles.small.copyWith(
              color: AppColors.blue,
              fontSize: 12,
              height: 16 / 12,
              fontWeight: FontWeight.w800,
            ),
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
    required this.compact,
  });

  final bool parsing;
  final TextEditingController controller;
  final String hintText;
  final VoidCallback onSubmit;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 44,
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.98),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFFD9E4F0)),
      ),
      child: Row(
        children: [
          const SizedBox(width: 16),
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
                style: AppTextStyles.body.copyWith(
                  color: AppColors.ink2,
                  fontSize: 15,
                  fontWeight: FontWeight.w700,
                ),
                decoration: InputDecoration(
                  hintText: hintText,
                  hintStyle: AppTextStyles.body.copyWith(
                    color: AppColors.subtle,
                    fontSize: compact ? 13.5 : 15,
                    overflow: TextOverflow.ellipsis,
                  ),
                  border: InputBorder.none,
                  isDense: true,
                  contentPadding: EdgeInsets.zero,
                ),
              ),
            ),
          ),
          const SizedBox(width: 6),
          Padding(
            padding: const EdgeInsets.only(right: 6),
            child: GestureDetector(
              behavior: HitTestBehavior.opaque,
              onTap: parsing ? null : onSubmit,
              child: Container(
                height: 36,
                width: compact ? 84 : 92,
                decoration: BoxDecoration(
                  color: AppColors.blue,
                  borderRadius: BorderRadius.circular(13),
                  boxShadow: [
                    BoxShadow(
                      color: AppColors.blue.withValues(alpha: 0.22),
                      blurRadius: 12,
                      offset: const Offset(0, 5),
                    ),
                  ],
                ),
                child: Center(
                  child: parsing
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(
                            strokeWidth: 2.2,
                            color: Colors.white,
                          ),
                        )
                      : Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            const Icon(
                              LucideIcons.sparkles,
                              color: Colors.white,
                              size: 16,
                            ),
                            const SizedBox(width: 4),
                            Text(
                              '识别',
                              style: AppTextStyles.sectionTitle.copyWith(
                                color: Colors.white,
                                fontSize: 14,
                              ),
                            ),
                          ],
                        ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _SmartShortcutPill extends StatelessWidget {
  const _SmartShortcutPill({
    required this.icon,
    required this.label,
    required this.color,
    required this.onTap,
    required this.compact,
  });

  final IconData icon;
  final String label;
  final Color color;
  final VoidCallback onTap;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      child: Container(
        height: 40,
        padding: EdgeInsets.symmetric(horizontal: compact ? 6 : 8),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(15),
          border: Border.all(color: const Color(0xFFE1E8F2)),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            _SmartShortcutIcon(icon: icon, color: color, label: label),
            SizedBox(width: compact ? 5 : 7),
            Flexible(
              child: FittedBox(
                fit: BoxFit.scaleDown,
                child: Text(
                  label,
                  maxLines: 1,
                  style: AppTextStyles.body.copyWith(
                    color: AppColors.ink2,
                    fontSize: compact ? 12.5 : 13.5,
                    fontWeight: FontWeight.w800,
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

class _SmartShortcutIcon extends StatelessWidget {
  const _SmartShortcutIcon({
    required this.icon,
    required this.color,
    required this.label,
  });

  final IconData icon;
  final Color color;
  final String label;

  @override
  Widget build(BuildContext context) {
    if (label == '记农事') {
      return Container(
        width: 22,
        height: 22,
        decoration: BoxDecoration(
          color: AppColors.greenDark,
          borderRadius: BorderRadius.circular(7),
        ),
        child: const Icon(LucideIcons.sprout, size: 15, color: Colors.white),
      );
    }
    return Icon(icon, size: 18, color: color);
  }
}

class _ReportShortcutCard extends StatelessWidget {
  const _ReportShortcutCard();

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final width = constraints.maxWidth;
        final isNarrow = width < 382;
        return SizedBox(
          width: width,
          child: _RecordCard(
            padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
            child: isNarrow
                ? Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const _ReportSummaryBlock(compact: true),
                      const SizedBox(height: 10),
                      Row(
                        children: const [
                          Expanded(
                            child: _ReportActionButton(
                              icon: LucideIcons.fileBarChart,
                              label: '生成周报',
                              color: AppColors.blue,
                              background: Color(0xFFF4F9FF),
                              compact: true,
                            ),
                          ),
                          SizedBox(width: 10),
                          Expanded(
                            child: _ReportActionButton(
                              icon: LucideIcons.calendarDays,
                              label: '生成月报',
                              color: AppColors.greenDark,
                              background: Color(0xFFF0FAF6),
                              compact: true,
                            ),
                          ),
                        ],
                      ),
                    ],
                  )
                : Row(
                    children: const [
                      Expanded(child: _ReportSummaryBlock(compact: false)),
                      SizedBox(width: 8),
                      _ReportActionButton(
                        icon: LucideIcons.fileBarChart,
                        label: '生成周报',
                        color: AppColors.blue,
                        background: Color(0xFFF4F9FF),
                        compact: false,
                      ),
                      SizedBox(width: 10),
                      _ReportActionButton(
                        icon: LucideIcons.calendarDays,
                        label: '生成月报',
                        color: AppColors.greenDark,
                        background: Color(0xFFF0FAF6),
                        compact: false,
                      ),
                    ],
                  ),
          ),
        );
      },
    );
  }
}

class _ReportSummaryBlock extends StatelessWidget {
  const _ReportSummaryBlock({required this.compact});

  final bool compact;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const _SectionIconBadge(
              icon: LucideIcons.barChart3,
              color: Colors.white,
              background: AppColors.blue,
            ),
            const SizedBox(width: 12),
            Flexible(
              child: Text(
                '经营报告',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: AppTextStyles.sectionTitle.copyWith(
                  fontSize: 17,
                  height: 22 / 17,
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        Text.rich(
          TextSpan(
            children: const [
              TextSpan(text: '本周'),
              TextSpan(
                text: '12',
                style: TextStyle(color: AppColors.blue),
              ),
              TextSpan(text: '条记录 · 本月支出'),
              TextSpan(
                text: '¥4,820',
                style: TextStyle(color: AppColors.greenDark),
              ),
            ],
          ),
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: AppTextStyles.small.copyWith(
            color: AppColors.muted,
            fontSize: compact ? 11.8 : 12.5,
            fontWeight: FontWeight.w700,
          ),
        ),
      ],
    );
  }
}

class _ReportActionButton extends StatelessWidget {
  const _ReportActionButton({
    required this.icon,
    required this.label,
    required this.color,
    required this.background,
    required this.compact,
  });

  final IconData icon;
  final String label;
  final Color color;
  final Color background;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 44,
      width: compact ? 70 : 76,
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFFDDE7F3)),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, size: compact ? 14 : 16, color: color),
          const SizedBox(width: 4),
          Flexible(
            child: Text(
              label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: AppTextStyles.small.copyWith(
                color: color,
                fontSize: compact ? 10.5 : 11.5,
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _TodayOverviewSection extends StatelessWidget {
  const _TodayOverviewSection();

  static const items = [
    _OverviewMetric(
      label: '今日已记',
      value: '3条',
      imageAsset: AppAssets.recordOverviewRecordedBlue,
      background: Color(0xFFF4F8FF),
      border: Color(0xFFDDEBFF),
    ),
    _OverviewMetric(
      label: '待确认',
      value: '1条',
      imageAsset: AppAssets.recordOverviewPendingOrange,
      background: Color(0xFFFFFAF3),
      border: Color(0xFFFFE8C8),
    ),
    _OverviewMetric(
      label: '工资待结',
      value: '2人',
      imageAsset: AppAssets.recordOverviewWorkersGreen,
      background: Color(0xFFF3FCF7),
      border: Color(0xFFDDF4E8),
    ),
    _OverviewMetric(
      label: '本周支出',
      value: '¥1,280',
      imageAsset: AppAssets.recordOverviewWalletPurple,
      background: Color(0xFFF8F5FF),
      border: Color(0xFFE8DEFF),
    ),
  ];

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final width = constraints.maxWidth;
        final isNarrow = width < 382;
        return SizedBox(
          width: width,
          child: _RecordCard(
            padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const _SectionHeading(
                  icon: LucideIcons.layoutDashboard,
                  title: '今日概览',
                ),
                const SizedBox(height: 12),
                GridView.count(
                  crossAxisCount: 2,
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  mainAxisSpacing: 10,
                  crossAxisSpacing: isNarrow ? 10 : 12,
                  childAspectRatio: isNarrow ? 1.2 : 2.92,
                  children: items
                      .map((item) => _OverviewMetricTile(
                            item: item,
                            compact: isNarrow,
                          ))
                      .toList(),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

class _OverviewMetricTile extends StatelessWidget {
  const _OverviewMetricTile({required this.item, required this.compact});

  final _OverviewMetric item;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: EdgeInsets.symmetric(
        horizontal: compact ? 12 : 14,
        vertical: compact ? 7 : 6,
      ),
      decoration: BoxDecoration(
        color: item.background,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: item.border),
      ),
      child: Row(
        children: [
          _GeneratedIcon(
            asset: item.imageAsset,
            size: compact ? 35 : 40,
          ),
          SizedBox(width: compact ? 9 : 11),
          Expanded(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  item.label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppTextStyles.body.copyWith(
                    color: AppColors.muted,
                    fontSize: compact ? 11.5 : 12.5,
                    height: compact ? 15 / 11.5 : 15 / 12.5,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                SizedBox(height: compact ? 1 : 2),
                FittedBox(
                  fit: BoxFit.scaleDown,
                  alignment: Alignment.centerLeft,
                  child: Text(
                    item.value,
                    maxLines: 1,
                    style: AppTextStyles.sectionTitle.copyWith(
                      fontSize: compact ? 18 : 19,
                      height: 22 / 19,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _OverviewMetric {
  const _OverviewMetric({
    required this.label,
    required this.value,
    required this.imageAsset,
    required this.background,
    required this.border,
  });

  final String label;
  final String value;
  final String imageAsset;
  final Color background;
  final Color border;
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

  static const items = [
    _ToolItem(
        '建批次', LucideIcons.layers, AppColors.purple, AppColors.purpleSoft),
    _ToolItem(
        '新增工人', LucideIcons.userRoundPlus, AppColors.blue, AppColors.blueSoft),
    _ToolItem(
        '建模板', LucideIcons.fileText, AppColors.greenDark, AppColors.greenSoft),
    _ToolItem('最近记录', LucideIcons.clock, AppColors.blue, AppColors.blueSoft),
    _ToolItem(
        '补记录', LucideIcons.pencilLine, AppColors.amber, AppColors.amberSoft),
    _ToolItem(
        '工资结算', LucideIcons.walletCards, AppColors.amber, AppColors.amberSoft),
  ];

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final width = constraints.maxWidth;
        final isNarrow = width < 382;
        return SizedBox(
          width: width,
          child: _RecordCard(
            padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const _SectionHeading(
                  icon: LucideIcons.briefcaseBusiness,
                  title: '常用工具',
                ),
                const SizedBox(height: 12),
                GridView.count(
                  crossAxisCount: 3,
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  mainAxisSpacing: 10,
                  crossAxisSpacing: isNarrow ? 10 : 12,
                  childAspectRatio: isNarrow ? 2.35 : 2.92,
                  children: items.map((item) {
                    return _ToolTile(
                      item: item,
                      compact: isNarrow,
                      onTap: switch (item.label) {
                        '建批次' => onCycleTap,
                        '新增工人' => onWorkerTap,
                        '建模板' => onTemplateTap,
                        '最近记录' => onRecentTap,
                        '补记录' => onPatchRecordTap,
                        '工资结算' => onWageSettlementTap,
                        _ => null,
                      },
                    );
                  }).toList(),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

class _ToolTile extends StatelessWidget {
  const _ToolTile({required this.item, required this.compact, this.onTap});

  final _ToolItem item;
  final bool compact;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      child: Container(
        padding: EdgeInsets.symmetric(horizontal: compact ? 8 : 10),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(13),
          border: Border.all(color: AppColors.lineSoft),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: compact ? 30 : 31,
              height: compact ? 30 : 31,
              decoration: BoxDecoration(
                color: item.background,
                borderRadius: BorderRadius.circular(10),
              ),
              child:
                  Icon(item.icon, size: compact ? 17 : 18, color: item.color),
            ),
            SizedBox(width: compact ? 6 : 7),
            Flexible(
              child: FittedBox(
                fit: BoxFit.scaleDown,
                child: Text(
                  item.label,
                  maxLines: 1,
                  style: AppTextStyles.body.copyWith(
                    color: AppColors.ink2,
                    fontSize: compact ? 12.5 : 13,
                    fontWeight: FontWeight.w700,
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

class _ToolItem {
  const _ToolItem(this.label, this.icon, this.color, this.background);

  final String label;
  final IconData icon;
  final Color color;
  final Color background;
}

class _SectionHeading extends StatelessWidget {
  const _SectionHeading({required this.icon, required this.title});

  final IconData icon;
  final String title;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        _SectionIconBadge(
          icon: icon,
          color: Colors.white,
          background: AppColors.blue,
        ),
        const SizedBox(width: 12),
        Text(
          title,
          style: AppTextStyles.sectionTitle.copyWith(
            fontSize: 18,
            height: 24 / 18,
          ),
        ),
      ],
    );
  }
}

class _SectionIconBadge extends StatelessWidget {
  const _SectionIconBadge({
    required this.icon,
    required this.color,
    required this.background,
  });

  final IconData icon;
  final Color color;
  final Color background;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 32,
      height: 32,
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Icon(icon, size: 18, color: color),
    );
  }
}
