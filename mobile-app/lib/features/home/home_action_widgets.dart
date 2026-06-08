part of 'home_screen.dart';

class _QuickActionStrip extends StatelessWidget {
  const _QuickActionStrip();

  @override
  Widget build(BuildContext context) {
    return const CardPanel(
      padding: EdgeInsets.symmetric(horizontal: 14, vertical: 14),
      child: Row(
        children: [
          Expanded(
            child: _ActionItem(
              icon: LucideIcons.bot,
              color: AppColors.blue,
              background: AppColors.blueSoft,
              title: '问问芽芽',
              subtitle: 'AI 农业助手',
            ),
          ),
          _VerticalSoftDivider(),
          Expanded(
            child: _ActionItem(
              icon: LucideIcons.notebookPen,
              color: AppColors.greenDark,
              background: AppColors.greenSoft,
              title: '记一笔',
              subtitle: '快速记账',
            ),
          ),
          _VerticalSoftDivider(),
          Expanded(
            child: _ActionItem(
              icon: LucideIcons.fileChartColumn,
              color: AppColors.purple,
              background: AppColors.purpleSoft,
              title: '生成报告',
              subtitle: '经营分析报告',
            ),
          ),
        ],
      ),
    );
  }
}

class _ActionItem extends StatelessWidget {
  const _ActionItem({
    required this.icon,
    required this.color,
    required this.background,
    required this.title,
    required this.subtitle,
  });

  final IconData icon;
  final Color color;
  final Color background;
  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        IconBadge(
          icon: icon,
          color: color,
          background: background,
          size: 38,
          iconSize: 21,
        ),
        const SizedBox(width: 9),
        Flexible(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                title,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: AppTextStyles.listTitle.copyWith(fontSize: 14),
              ),
              const SizedBox(height: 2),
              Text(
                subtitle,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: AppTextStyles.small,
              ),
            ],
          ),
        ),
      ],
    );
  }
}
