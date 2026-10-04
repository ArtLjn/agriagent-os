import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../shared/widgets/card_panel.dart';
import '../../theme/app_text_styles.dart';
import '../../shared/assets/app_assets.dart';
import '../../shared/widgets/reference_page.dart';
import '../../theme/app_colors.dart';
import '../../data/repositories/business_repository.dart';
import '../business/business_pages.dart';

class WorkbenchScreen extends StatefulWidget {
  const WorkbenchScreen({
    super.key,
    required this.businessRepository,
    this.onGoHome,
    this.onGoLedger,
    this.onGoYaya,
    this.onGoProfile,
    this.onRecordAgain,
    this.onLedgerSaved,
  });

  final BusinessRepository businessRepository;
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
    final today = DateTime.now();
    final weekday = ['一', '二', '三', '四', '五', '六', '日'][today.weekday - 1];
    return ReferencePage(
      title: '记录',
      subtitle: '${today.month}月${today.day}日 · 星期$weekday',
      headerTrailing: IconButton(
        tooltip: '查看最近记录',
        onPressed: widget.onGoLedger,
        icon: const Icon(LucideIcons.history, size: 22),
      ),
      children: [
        const SizedBox(height: 32),
        const Text('把今天的经营记下来', style: AppTextStyles.title),
        const SizedBox(height: 8),
        const Text('每一笔投入，每一次耕耘，都有据可查。', style: AppTextStyles.small),
        const SizedBox(height: 24),
        CardPanel(
          padding: const EdgeInsets.all(8),
          child: Column(children: [
            _RecordEntry(
              label: '手动记一笔',
              subtitle: '收入、支出与日常花费',
              icon: LucideIcons.walletCards,
              primary: true,
              onTap: () => _openManualEdit(context),
            ),
            const SizedBox(height: 8),
            Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Expanded(
                  child: _RecordEntry(
                label: '记农事',
                subtitle: '留存田间作业',
                icon: LucideIcons.sprout,
                onTap: () => _openBusinessPage(context,
                    FarmLogCreatePage(repository: widget.businessRepository)),
              )),
              const SizedBox(width: 8),
              Expanded(
                  child: _RecordEntry(
                label: '记工资',
                subtitle: '整理人工费用',
                icon: LucideIcons.handCoins,
                onTap: () => _openBusinessPage(context,
                    WageCreatePage(repository: widget.businessRepository)),
              )),
            ]),
          ]),
        ),
        const SizedBox(height: 16),
        Material(
          color: AppColors.blueSoft,
          borderRadius: BorderRadius.circular(20),
          child: InkWell(
            onTap: widget.onGoYaya,
            borderRadius: BorderRadius.circular(20),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Row(children: [
                ClipOval(
                    child: Image.asset(AppAssets.yayaMascotLogo,
                        width: 40, height: 40)),
                const SizedBox(width: 12),
                Expanded(
                    child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                      const Text('让芽芽帮你整理', style: AppTextStyles.listTitle),
                      const SizedBox(height: 4),
                      Text('说说发生了什么，保存前由你确认。',
                          style: AppTextStyles.small
                              .copyWith(color: AppColors.muted)),
                    ])),
                const SizedBox(width: 8),
                const Icon(LucideIcons.arrowUpRight,
                    color: AppColors.blue, size: 20),
              ]),
            ),
          ),
        ),
        const SizedBox(height: 32),
        const Text('农场资料', style: AppTextStyles.sectionTitle),
        const SizedBox(height: 12),
        CardPanel(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
          child: Column(children: [
            _RecordTool(
                label: '建批次',
                subtitle: '管理作物与地块',
                icon: LucideIcons.layers,
                onTap: () => _openBusinessPage(
                    context,
                    FarmCycleListPage(
                        repository: widget.businessRepository,
                        onBottomTabChanged: (index) =>
                            _handleBusinessBottomTab(context, index)))),
            const Divider(height: 1),
            _RecordTool(
                label: '新增工人',
                subtitle: '管理工人档案',
                icon: LucideIcons.users,
                onTap: () => _openBusinessPage(
                    context,
                    WorkerListPage(
                        repository: widget.businessRepository,
                        onBottomTabChanged: (index) =>
                            _handleBusinessBottomTab(context, index)))),
            const Divider(height: 1),
            _RecordTool(
                label: '建模板',
                subtitle: '沉淀种植经验',
                icon: LucideIcons.bookOpenText,
                onTap: () => _openBusinessPage(
                    context,
                    CropTemplateListPage(
                        repository: widget.businessRepository,
                        onBottomTabChanged: (index) =>
                            _handleBusinessBottomTab(context, index)))),
          ]),
        ),
        const SizedBox(height: 24),
        TextButton.icon(
          onPressed: widget.onGoLedger,
          icon: const Icon(LucideIcons.history, size: 16),
          label: const Text('查看最近记录'),
        ),
      ],
    );
  }
}

class _RecordEntry extends StatelessWidget {
  const _RecordEntry(
      {required this.label,
      required this.subtitle,
      required this.icon,
      required this.onTap,
      this.primary = false});
  final String label;
  final String subtitle;
  final IconData icon;
  final VoidCallback onTap;
  final bool primary;

  @override
  Widget build(BuildContext context) {
    final text =
        Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(label,
          style:
              primary ? AppTextStyles.sectionTitle : AppTextStyles.listTitle),
      const SizedBox(height: 6),
      Text(subtitle, style: AppTextStyles.small),
    ]);
    return Material(
      color: primary ? AppColors.blueSoft : AppColors.surface,
      borderRadius: BorderRadius.circular(16),
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: primary
              ? Row(children: [
                  Container(
                      width: 48,
                      height: 48,
                      decoration: BoxDecoration(
                          color: AppColors.blue,
                          borderRadius: BorderRadius.circular(16)),
                      child: Icon(icon, color: Colors.white, size: 24)),
                  const SizedBox(width: 16),
                  Expanded(child: text),
                  const SizedBox(width: 8),
                  const Icon(LucideIcons.arrowRight,
                      color: AppColors.blue, size: 20),
                ])
              : Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Icon(icon, color: AppColors.ink2, size: 24),
                  const SizedBox(height: 16),
                  text,
                ]),
        ),
      ),
    );
  }
}

class _RecordTool extends StatelessWidget {
  const _RecordTool(
      {required this.label,
      required this.subtitle,
      required this.icon,
      required this.onTap});
  final String label;
  final String subtitle;
  final IconData icon;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 16),
        child: Row(children: [
          Icon(icon, color: AppColors.muted, size: 20),
          const SizedBox(width: 12),
          Expanded(child: Text(label, style: AppTextStyles.body)),
          const SizedBox(width: 8),
          Flexible(
              child: Text(subtitle,
                  textAlign: TextAlign.right, style: AppTextStyles.small)),
          const SizedBox(width: 8),
          const Icon(LucideIcons.chevronRight,
              size: 16, color: AppColors.subtle),
        ]),
      ),
    );
  }
}
