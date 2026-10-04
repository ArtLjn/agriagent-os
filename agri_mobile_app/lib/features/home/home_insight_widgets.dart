part of 'home_screen.dart';

class _BusinessOverview extends StatelessWidget {
  const _BusinessOverview({required this.model, this.onBottomTabChanged});

  final HomeViewModel model;
  final ValueChanged<int>? onBottomTabChanged;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text('经营概览',
            style: AppTextStyles.sectionTitle
                .copyWith(fontWeight: FontWeight.w600)),
        const SizedBox(height: 16),
        IntrinsicHeight(
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Expanded(
                  child: _OverviewMetric(
                      icon: LucideIcons.clipboardList,
                      label: '作业安排',
                      value: model.workOrderCountText,
                      caption: '查看作业记录',
                      onTap: onBottomTabChanged == null
                          ? null
                          : () => onBottomTabChanged!(1))),
              const SizedBox(width: 12),
              Expanded(
                  child: _OverviewMetric(
                      icon: LucideIcons.walletCards,
                      label: '未结人工',
                      value: model.unsettledLaborText,
                      caption: '查看资金账本',
                      onTap: onBottomTabChanged == null
                          ? null
                          : () => onBottomTabChanged!(3))),
            ],
          ),
        ),
      ],
    );
  }
}

class _OverviewMetric extends StatelessWidget {
  const _OverviewMetric(
      {required this.icon,
      required this.label,
      required this.value,
      required this.caption,
      this.onTap});

  final IconData icon;
  final String label;
  final String value;
  final String caption;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      child: Material(
        color: AppColors.surface,
        shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(20),
            side: const BorderSide(color: AppColors.line)),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(20),
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(icon, color: AppColors.blue, size: 20),
                const SizedBox(height: 16),
                Text(label, style: AppTextStyles.small),
                const SizedBox(height: 8),
                SizedBox(
                  width: double.infinity,
                  child: FittedBox(
                    fit: BoxFit.scaleDown,
                    alignment: Alignment.centerLeft,
                    child: Text(value,
                        style: AppTextStyles.metric.copyWith(
                            fontSize: 26, fontWeight: FontWeight.w600),
                        maxLines: 1),
                  ),
                ),
                const SizedBox(height: 12),
                Text(caption, style: AppTextStyles.small),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
