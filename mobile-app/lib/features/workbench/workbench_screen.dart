import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../shared/widgets/card_panel.dart';
import '../../shared/widgets/reference_page.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';
import '../record_flow/record_flow_controller.dart';
import '../record_flow/record_ai_confirm_screen.dart';
import '../record_flow/record_manual_edit_screen.dart';

part 'workbench_ai_card.dart';

class WorkbenchScreen extends StatefulWidget {
  const WorkbenchScreen({
    super.key,
    required this.recordFlowController,
    this.onGoHome,
    this.onGoLedger,
    this.onRecordAgain,
  });

  final RecordFlowController recordFlowController;
  final VoidCallback? onGoHome;
  final VoidCallback? onGoLedger;
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

  @override
  Widget build(BuildContext context) {
    return ReferencePage(
      headerTrailing: const HeaderIconButton(icon: LucideIcons.clock),
      children: [
        const SizedBox(height: 14),
        _RecordActionGrid(
          onAiTap: () => _openAiConfirm(context),
          onManualTap: () => _openManualEdit(context),
        ),
        const SizedBox(height: 14),
        _VoiceInputCard(
          parsing: _parsing,
          onTap: () => _openAiConfirm(context),
        ),
        const SizedBox(height: 14),
        const _QuickRecordCard(),
        const SizedBox(height: 14),
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
            buttonIcon: LucideIcons.mic,
            buttonLabel: '开始说话',
            onTap: onAiTap,
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [Color(0xFF3685FF), AppColors.blueDark],
            ),
          ),
        ),
        SizedBox(width: 14),
        Expanded(
          child: _RecordActionCard(
            title: '自己填',
            subtitle: '手动记录，快速便捷',
            icon: LucideIcons.pencil,
            buttonIcon: LucideIcons.notebookPen,
            buttonLabel: '立即记录',
            onTap: onManualTap,
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [Color(0xFF39D681), Color(0xFF17B664)],
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
    required this.buttonIcon,
    required this.buttonLabel,
    required this.gradient,
    required this.onTap,
  });

  final String title;
  final String subtitle;
  final IconData icon;
  final IconData buttonIcon;
  final String buttonLabel;
  final Gradient gradient;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      child: CardPanel(
        radius: 12,
        padding: const EdgeInsets.all(18),
        gradient: gradient,
        borderColor: Colors.transparent,
        child: SizedBox(
          height: 120,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      title,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 21,
                        height: 26 / 21,
                        fontWeight: FontWeight.w800,
                        letterSpacing: 0,
                      ),
                    ),
                  ),
                  Icon(icon,
                      color: Colors.white.withValues(alpha: 0.92), size: 28),
                ],
              ),
              const SizedBox(height: 9),
              Text(
                subtitle,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: AppTextStyles.body.copyWith(
                  color: Colors.white.withValues(alpha: 0.9),
                ),
              ),
              const Spacer(),
              Container(
                height: 38,
                padding: const EdgeInsets.symmetric(horizontal: 12),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.18),
                  borderRadius: BorderRadius.circular(999),
                  border: Border.all(
                    color: Colors.white.withValues(alpha: 0.34),
                  ),
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
        padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
        child: Row(
          children: [
            const Icon(LucideIcons.mic, size: 24, color: AppColors.navy),
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
                : const Icon(
                    LucideIcons.audioWaveform,
                    size: 24,
                    color: AppColors.blue,
                  ),
          ],
        ),
      ),
    );
  }
}

class _QuickRecordCard extends StatelessWidget {
  const _QuickRecordCard();

  @override
  Widget build(BuildContext context) {
    return const CardPanel(
      padding: EdgeInsets.fromLTRB(16, 12, 16, 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('手动快捷记录', style: AppTextStyles.sectionTitle),
          SizedBox(height: 12),
          _QuickRecordGrid(),
        ],
      ),
    );
  }
}

class _QuickRecordGrid extends StatelessWidget {
  const _QuickRecordGrid();

  static const items = [
    _QuickRecordItem(
        '记账', LucideIcons.walletCards, AppColors.blue, AppColors.blueSoft),
    _QuickRecordItem(
        '记农事', LucideIcons.leaf, AppColors.greenDark, AppColors.greenSoft),
    _QuickRecordItem(
        '记工资', LucideIcons.handCoins, AppColors.amber, AppColors.amberSoft),
    _QuickRecordItem(
        '建批次', LucideIcons.layers, AppColors.purple, AppColors.purpleSoft),
    _QuickRecordItem(
        '新增工人', LucideIcons.userRoundPlus, AppColors.blue, AppColors.blueSoft),
    _QuickRecordItem(
        '建模板', LucideIcons.fileText, AppColors.teal, AppColors.tealSoft),
  ];

  @override
  Widget build(BuildContext context) {
    return GridView.count(
      crossAxisCount: 3,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      mainAxisSpacing: 8,
      crossAxisSpacing: 12,
      childAspectRatio: 1.28,
      children: items.map((item) => _QuickRecordTile(item: item)).toList(),
    );
  }
}

class _QuickRecordTile extends StatelessWidget {
  const _QuickRecordTile({required this.item});

  final _QuickRecordItem item;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(12),
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
          IconBadge(
            icon: item.icon,
            color: item.color,
            background: item.background,
            size: 38,
            iconSize: 21,
          ),
          const SizedBox(height: 8),
          Text(item.label, style: AppTextStyles.listTitle),
        ],
      ),
    );
  }
}

class _QuickRecordItem {
  const _QuickRecordItem(this.label, this.icon, this.color, this.background);

  final String label;
  final IconData icon;
  final Color color;
  final Color background;
}
