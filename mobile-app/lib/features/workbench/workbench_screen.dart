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
import '../record_flow/record_manual_edit_screen.dart';

part 'workbench_ai_card.dart';

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
  static const _exampleText = '今天买饲料 3680 元';

  bool _parsing = false;

  Future<void> _openAiConfirm(BuildContext context) async {
    if (_parsing) return;
    setState(() => _parsing = true);
    try {
      final draft = await widget.recordFlowController.parse(_exampleText);
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
        builder: (_) => RecordManualEditScreen(
          controller: widget.recordFlowController,
          draft: const RecordDraft(
            scene: 'manual.record',
            originalText: '',
            fields: {},
            missingFields: [],
            warnings: [],
          ),
          onGoHome: widget.onGoHome,
          onGoLedger: widget.onGoLedger,
          onRecordAgain: widget.onRecordAgain,
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
        _VoiceInputCard(
          parsing: _parsing,
          onTap: () => _openAiConfirm(context),
        ),
        const SizedBox(height: 10),
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
        ),
        const SizedBox(height: 10),
        _AiGeneratedCard(
          onEdit: () => _openManualEdit(context),
          onSave: () => _openAiConfirm(context),
        ),
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
            subtitle: '说一句，自动整理成记录',
            icon: LucideIcons.bot,
            imageAsset: AppAssets.recordAiRobot,
            accentAsset: AppAssets.recordMicrophone,
            buttonIcon: LucideIcons.mic,
            buttonLabel: '开始说话',
            foregroundColor: Colors.white,
            buttonColor: AppColors.blueDark,
            illustrationBackground: const Color(0x33FFFFFF),
            onTap: onAiTap,
            gradient: const LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [Color(0xFF2680FF), Color(0xFF58C4FF)],
            ),
          ),
        ),
        const SizedBox(width: 14),
        Expanded(
          child: _RecordActionCard(
            title: '自己填',
            subtitle: '手动记录，快速便捷',
            icon: LucideIcons.pencil,
            imageAsset: AppAssets.recordManualNote,
            accentAsset: AppAssets.recordQuickTemplate,
            buttonIcon: LucideIcons.notebookPen,
            buttonLabel: '立即记录',
            foregroundColor: const Color(0xFF087849),
            buttonColor: const Color(0xFF08A969),
            illustrationBackground: const Color(0xFFE7FAF0),
            onTap: onManualTap,
            gradient: const LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [Color(0xFFE9FFF4), Color(0xFFCFF6E4)],
            ),
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
    required this.icon,
    required this.imageAsset,
    required this.accentAsset,
    required this.buttonIcon,
    required this.buttonLabel,
    required this.foregroundColor,
    required this.buttonColor,
    required this.illustrationBackground,
    required this.gradient,
    required this.onTap,
  });

  final String title;
  final String subtitle;
  final IconData icon;
  final String imageAsset;
  final String accentAsset;
  final IconData buttonIcon;
  final String buttonLabel;
  final Color foregroundColor;
  final Color buttonColor;
  final Color illustrationBackground;
  final Gradient gradient;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      child: CardPanel(
        radius: 20,
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 14),
        gradient: gradient,
        borderColor: Colors.white.withValues(alpha: 0.42),
        child: SizedBox(
          height: 148,
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
                ),
              ),
              const SizedBox(height: 6),
              Text(
                subtitle,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: AppTextStyles.body.copyWith(
                  color: foregroundColor.withValues(alpha: 0.82),
                ),
              ),
              const Spacer(),
              Align(
                alignment: Alignment.centerRight,
                child: SizedBox(
                  width: 110,
                  height: 46,
                  child: Stack(
                    clipBehavior: Clip.none,
                    children: [
                      Positioned(
                        right: 4,
                        top: 3,
                        child: Container(
                          width: 68,
                          height: 42,
                          decoration: BoxDecoration(
                            color: illustrationBackground,
                            borderRadius: BorderRadius.circular(24),
                          ),
                        ),
                      ),
                      Positioned(
                        right: 46,
                        top: 21,
                        child: Image.asset(
                          accentAsset,
                          width: 30,
                          height: 30,
                          fit: BoxFit.contain,
                          errorBuilder: (_, __, ___) => Icon(
                            icon,
                            color: foregroundColor,
                            size: 34,
                          ),
                        ),
                      ),
                      Positioned(
                        right: 8,
                        top: 0,
                        child: Image.asset(
                          imageAsset,
                          width: 54,
                          height: 54,
                          fit: BoxFit.contain,
                          errorBuilder: (_, __, ___) => Icon(
                            icon,
                            color: foregroundColor,
                            size: 46,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
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
      ),
    );
  }
}

class _VoiceInputCard extends StatelessWidget {
  const _VoiceInputCard({
    required this.parsing,
    required this.onTap,
  });

  final bool parsing;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      child: CardPanel(
        radius: 18,
        padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 10),
        child: Row(
          children: [
            Image.asset(
              AppAssets.recordMicrophone,
              width: 26,
              height: 26,
              fit: BoxFit.contain,
              errorBuilder: (_, __, ___) =>
                  const Icon(LucideIcons.mic, size: 24, color: AppColors.navy),
            ),
            const SizedBox(width: 18),
            Expanded(
              child: Text(
                parsing ? '正在识别记录...' : '例如：今天买饲料 3680 元',
                style: AppTextStyles.body.copyWith(
                  color: AppColors.subtle,
                  fontSize: 16,
                ),
              ),
            ),
            parsing
                ? const SizedBox(
                    width: 22,
                    height: 22,
                    child: CircularProgressIndicator(strokeWidth: 2.4),
                  )
                : Image.asset(
                    AppAssets.recordVoiceWave,
                    width: 28,
                    height: 24,
                    fit: BoxFit.contain,
                    errorBuilder: (_, __, ___) => const Icon(
                      LucideIcons.audioWaveform,
                      size: 24,
                      color: AppColors.blue,
                    ),
                  ),
          ],
        ),
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
  });

  final VoidCallback onLedgerTap;
  final VoidCallback onCycleTap;
  final VoidCallback onWorkerTap;
  final VoidCallback onTemplateTap;

  static const items = [
    _QuickRecordItem('记账', '记录收支明细', LucideIcons.walletCards, AppColors.blue,
        AppColors.blueSoft, AppAssets.recordQuickLedger),
    _QuickRecordItem('记农事', '记录农事活动', LucideIcons.leaf, AppColors.greenDark,
        AppColors.greenSoft, AppAssets.recordQuickFarm),
    _QuickRecordItem('记工资', '记录工资发放', LucideIcons.handCoins, AppColors.amber,
        AppColors.amberSoft, AppAssets.recordQuickWage),
    _QuickRecordItem('建批次', '创建生产批次', LucideIcons.layers, AppColors.purple,
        AppColors.purpleSoft, AppAssets.recordQuickBatch),
    _QuickRecordItem('新增工人', '添加工人信息', LucideIcons.userRoundPlus,
        AppColors.blue, AppColors.blueSoft, AppAssets.recordQuickWorker),
    _QuickRecordItem('建模板', '创建记录模板', LucideIcons.fileText, AppColors.teal,
        AppColors.tealSoft, AppAssets.recordQuickTemplate),
  ];

  @override
  Widget build(BuildContext context) {
    return GridView.count(
      crossAxisCount: 3,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      mainAxisSpacing: 6,
      crossAxisSpacing: 12,
      childAspectRatio: 1.06,
      children: items.map((item) {
        return _QuickRecordTile(
          item: item,
          onTap: switch (item.label) {
            '记账' => onLedgerTap,
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
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: AppColors.lineSoft),
          boxShadow: const [
            BoxShadow(
              color: Color(0x06000000),
              blurRadius: 12,
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
  );

  final String label;
  final String subtitle;
  final IconData icon;
  final Color color;
  final Color background;
  final String imageAsset;
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
