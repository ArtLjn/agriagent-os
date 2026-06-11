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
  });

  final BusinessRepository businessRepository;
  final RecordFlowController recordFlowController;
  final VoidCallback? onGoHome;
  final VoidCallback? onGoLedger;
  final VoidCallback? onGoYaya;
  final VoidCallback? onGoProfile;
  final VoidCallback? onRecordAgain;

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
    return ReferencePage(
      headerTrailing: const HeaderIconButton(icon: LucideIcons.clock),
      children: [
        const SizedBox(height: 10),
        _RecordActionGrid(
          onAiTap: () => _openAiConfirm(context),
          onManualTap: () => _openManualEdit(context),
        ),
        const SizedBox(height: 10),
        _SmartFillInputBar(
          parsing: _parsing,
          controller: _recordTextController,
          onSubmit: () => _openAiConfirm(context),
        ),
        const SizedBox(height: 12),
        _QuickRecordGrid(
          onLedgerTap: () => _openBusinessPage(
            context,
            LedgerManualCreatePage(
              repository: widget.businessRepository,
              onBottomTabChanged: (index) =>
                  _handleBusinessBottomTab(context, index),
            ),
          ),
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
        const SizedBox(height: 10),
      ],
    );
  }
}

class _RecordActionGrid extends StatelessWidget {
  const _RecordActionGrid({
    required this.onAiTap,
    required this.onManualTap,
  });

  final VoidCallback onAiTap;
  final VoidCallback onManualTap;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: _RecordActionCard(
            title: 'AI帮我填',
            subtitle: '输入一句，自动整理成记录',
            backgroundAsset: AppAssets.recordAiCardBackground,
            buttonIcon: LucideIcons.sparkles,
            buttonLabel: '立即识别',
            foregroundColor: Colors.white,
            buttonColor: AppColors.blueDark,
            onTap: onAiTap,
            gradient: const LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [Color(0xFF1593FF), Color(0xFF16C2EE)],
            ),
            textScrim: const LinearGradient(
              begin: Alignment.centerLeft,
              end: Alignment.centerRight,
              colors: [
                Color(0xE60476D9),
                Color(0x990E9EE7),
                Color(0x0016C2EE),
              ],
              stops: [0, 0.48, 1],
            ),
            textShadowColor: Color(0x66002572),
          ),
        ),
        const SizedBox(width: 14),
        Expanded(
          child: _RecordActionCard(
            title: '自己填',
            subtitle: '手动记录，快速便捷',
            backgroundAsset: AppAssets.recordManualCardBackground,
            buttonIcon: LucideIcons.notebookPen,
            buttonLabel: '立即记录',
            foregroundColor: const Color(0xFF087849),
            buttonColor: const Color(0xFF08A969),
            onTap: onManualTap,
            gradient: const LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [Color(0xFFE9FFF4), Color(0xFFCFF6E4)],
            ),
            textScrim: const LinearGradient(
              begin: Alignment.centerLeft,
              end: Alignment.centerRight,
              colors: [
                Color(0xF2F4FFF8),
                Color(0xBDEFFFF6),
                Color(0x00CFF6E4),
              ],
              stops: [0, 0.52, 1],
            ),
            textShadowColor: Color(0x99FFFFFF),
          ),
        ),
      ],
    );
  }
}

class _RecordActionCard extends StatelessWidget {
  const _RecordActionCard({
    required this.title,
    required this.subtitle,
    required this.backgroundAsset,
    required this.buttonIcon,
    required this.buttonLabel,
    required this.foregroundColor,
    required this.buttonColor,
    required this.gradient,
    required this.textScrim,
    required this.textShadowColor,
    required this.onTap,
  });

  final String title;
  final String subtitle;
  final String backgroundAsset;
  final IconData buttonIcon;
  final String buttonLabel;
  final Color foregroundColor;
  final Color buttonColor;
  final Gradient gradient;
  final Gradient textScrim;
  final Color textShadowColor;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      child: CardPanel(
        radius: 20,
        padding: EdgeInsets.zero,
        gradient: gradient,
        borderColor: Colors.white.withValues(alpha: 0.42),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(20),
          child: SizedBox(
            height: 176,
            child: Stack(
              fit: StackFit.expand,
              children: [
                Container(
                  decoration: BoxDecoration(gradient: gradient),
                ),
                Image.asset(
                  backgroundAsset,
                  alignment: Alignment.centerRight,
                  fit: BoxFit.cover,
                  errorBuilder: (_, __, ___) => const SizedBox.shrink(),
                ),
                DecoratedBox(
                  decoration: BoxDecoration(gradient: textScrim),
                ),
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 16, 16, 14),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        title,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          color: foregroundColor,
                          fontSize: 23,
                          height: 29 / 23,
                          fontWeight: FontWeight.w800,
                          letterSpacing: 0,
                          shadows: [
                            Shadow(
                              color: textShadowColor,
                              blurRadius: 8,
                              offset: const Offset(0, 2),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 6),
                      Text(
                        subtitle,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: AppTextStyles.body.copyWith(
                          color: foregroundColor.withValues(alpha: 0.94),
                          fontSize: 13.5,
                          height: 18 / 13.5,
                          shadows: [
                            Shadow(
                              color: textShadowColor,
                              blurRadius: 7,
                              offset: const Offset(0, 1),
                            ),
                          ],
                        ),
                      ),
                      const Spacer(),
                      Container(
                        height: 40,
                        padding: const EdgeInsets.symmetric(horizontal: 10),
                        decoration: BoxDecoration(
                          color: buttonColor,
                          borderRadius: BorderRadius.circular(999),
                          boxShadow: [
                            BoxShadow(
                              color: buttonColor.withValues(alpha: 0.24),
                              blurRadius: 14,
                              offset: const Offset(0, 6),
                            ),
                          ],
                        ),
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(buttonIcon, color: Colors.white, size: 19),
                            const SizedBox(width: 7),
                            Flexible(
                              child: Text(
                                buttonLabel,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: AppTextStyles.sectionTitle.copyWith(
                                  color: Colors.white,
                                  fontSize: 15,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
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

class _SmartFillInputBar extends StatelessWidget {
  const _SmartFillInputBar({
    required this.parsing,
    required this.controller,
    required this.onSubmit,
  });

  final bool parsing;
  final TextEditingController controller;
  final VoidCallback onSubmit;

  @override
  Widget build(BuildContext context) {
    return CardPanel(
      radius: 18,
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 10),
      child: Row(
        children: [
          const Icon(
            LucideIcons.sparkles,
            size: 22,
            color: AppColors.blue,
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Material(
              color: Colors.transparent,
              child: TextField(
                controller: controller,
                enabled: !parsing,
                minLines: 1,
                maxLines: 2,
                textInputAction: TextInputAction.done,
                onSubmitted: (_) => onSubmit(),
                style: AppTextStyles.body.copyWith(
                  color: AppColors.ink2,
                  fontSize: 16,
                  fontWeight: FontWeight.w700,
                ),
                decoration: InputDecoration(
                  hintText: parsing ? '正在识别记录...' : '输入一句话记录，芽芽会帮你整理',
                  hintStyle: AppTextStyles.body.copyWith(
                    color: AppColors.subtle,
                    fontSize: 16,
                  ),
                  border: InputBorder.none,
                  isDense: true,
                  contentPadding: EdgeInsets.zero,
                ),
              ),
            ),
          ),
          parsing
              ? const SizedBox(
                  width: 22,
                  height: 22,
                  child: CircularProgressIndicator(strokeWidth: 2.4),
                )
              : GestureDetector(
                  behavior: HitTestBehavior.opaque,
                  onTap: onSubmit,
                  child: const SizedBox(
                    width: 32,
                    height: 32,
                    child: Icon(
                      LucideIcons.keyboard,
                      size: 22,
                      color: AppColors.blue,
                    ),
                  ),
                ),
        ],
      ),
    );
  }
}

class _QuickRecordGrid extends StatelessWidget {
  const _QuickRecordGrid({
    required this.onLedgerTap,
    required this.onCycleTap,
    required this.onWorkerTap,
    required this.onTemplateTap,
    required this.onFarmLogTap,
    required this.onWageTap,
  });

  final VoidCallback onLedgerTap;
  final VoidCallback onCycleTap;
  final VoidCallback onWorkerTap;
  final VoidCallback onTemplateTap;
  final VoidCallback onFarmLogTap;
  final VoidCallback onWageTap;

  static const items = [
    _QuickRecordItem(
      '记账',
      '记录收支明细',
      LucideIcons.walletCards,
      AppColors.blue,
      AppColors.blueSoft,
      AppAssets.recordQuickLedger,
      Color(0xFFF2F7FF),
      Color(0xFFE6F0FF),
      Color(0xFFD7E6FF),
    ),
    _QuickRecordItem(
      '记农事',
      '记录农事活动',
      LucideIcons.leaf,
      AppColors.greenDark,
      AppColors.greenSoft,
      AppAssets.recordQuickFarm,
      Color(0xFFF0FBF5),
      Color(0xFFE2F7EA),
      Color(0xFFD0EEDB),
    ),
    _QuickRecordItem(
      '记工资',
      '记录工资发放',
      LucideIcons.handCoins,
      AppColors.amber,
      AppColors.amberSoft,
      AppAssets.recordQuickWage,
      Color(0xFFFFF7E8),
      Color(0xFFFFEFD4),
      Color(0xFFFFE0AD),
    ),
    _QuickRecordItem(
      '建批次',
      '创建生产批次',
      LucideIcons.layers,
      AppColors.purple,
      AppColors.purpleSoft,
      AppAssets.recordQuickBatch,
      Color(0xFFF7F3FF),
      Color(0xFFEEE8FF),
      Color(0xFFE0D6FF),
    ),
    _QuickRecordItem(
      '新增工人',
      '添加工人信息',
      LucideIcons.userRoundPlus,
      AppColors.blue,
      AppColors.blueSoft,
      AppAssets.recordQuickWorker,
      Color(0xFFF2F7FF),
      Color(0xFFE8F2FF),
      Color(0xFFDCEAFF),
    ),
    _QuickRecordItem(
      '建模板',
      '创建记录模板',
      LucideIcons.fileText,
      AppColors.teal,
      AppColors.tealSoft,
      AppAssets.recordQuickTemplate,
      Color(0xFFEFFBFC),
      Color(0xFFE1F7FA),
      Color(0xFFCDEEF3),
    ),
  ];

  @override
  Widget build(BuildContext context) {
    return GridView.count(
      crossAxisCount: 3,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      mainAxisSpacing: 8,
      crossAxisSpacing: 12,
      childAspectRatio: 1.06,
      children: items.map((item) {
        return _QuickRecordTile(
          item: item,
          onTap: switch (item.label) {
            '记账' => onLedgerTap,
            '记农事' => onFarmLogTap,
            '记工资' => onWageTap,
            '建批次' => onCycleTap,
            '新增工人' => onWorkerTap,
            '建模板' => onTemplateTap,
            _ => null,
          },
        );
      }).toList(),
    );
  }
}

class _QuickRecordTile extends StatelessWidget {
  const _QuickRecordTile({required this.item, this.onTap});

  final _QuickRecordItem item;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.fromLTRB(8, 6, 8, 6),
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [item.tileStart, item.tileEnd],
          ),
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: item.border),
          boxShadow: [
            BoxShadow(
              color: item.color.withValues(alpha: 0.08),
              blurRadius: 14,
              offset: Offset(0, 4),
            ),
          ],
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            _RecordImageIconBadge(item: item),
            const SizedBox(height: 3),
            Text(
              item.label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: AppTextStyles.listTitle.copyWith(
                fontSize: 13.5,
                height: 18 / 13.5,
                fontWeight: FontWeight.w700,
              ),
            ),
            Text(
              item.subtitle,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: AppTextStyles.small.copyWith(
                color: AppColors.subtle,
                fontSize: 9,
                height: 11 / 9,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _QuickRecordItem {
  const _QuickRecordItem(
    this.label,
    this.subtitle,
    this.icon,
    this.color,
    this.background,
    this.imageAsset,
    this.tileStart,
    this.tileEnd,
    this.border,
  );

  final String label;
  final String subtitle;
  final IconData icon;
  final Color color;
  final Color background;
  final String imageAsset;
  final Color tileStart;
  final Color tileEnd;
  final Color border;
}

class _RecordImageIconBadge extends StatelessWidget {
  const _RecordImageIconBadge({required this.item});

  final _QuickRecordItem item;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 36,
      height: 36,
      decoration: BoxDecoration(
        color: item.background,
        borderRadius: BorderRadius.circular(11),
        border: Border.all(color: Colors.white.withValues(alpha: 0.64)),
      ),
      child: Center(
        child: Image.asset(
          item.imageAsset,
          width: 24,
          height: 24,
          fit: BoxFit.contain,
          errorBuilder: (_, __, ___) => Icon(
            item.icon,
            size: 21,
            color: item.color,
          ),
        ),
      ),
    );
  }
}
