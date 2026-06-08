part of 'home_screen.dart';

class _AiSuggestionsCard extends StatelessWidget {
  const _AiSuggestionsCard();

  @override
  Widget build(BuildContext context) {
    return const CardPanel(
      padding: EdgeInsets.fromLTRB(16, 16, 16, 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(LucideIcons.sparkles, size: 24, color: AppColors.blue),
              SizedBox(width: 10),
              Text('AI 今日建议', style: AppTextStyles.dateTitle),
            ],
          ),
          SizedBox(height: 12),
          _SuggestionRow(
            icon: LucideIcons.cloudRain,
            color: AppColors.blue,
            background: AppColors.blueSoft,
            title: '午后避开露天作业',
            subtitle: '预计午后有雷阵雨，注意防范。',
          ),
          _SoftDivider(),
          _SuggestionRow(
            icon: LucideIcons.droplets,
            color: AppColors.greenDark,
            background: AppColors.greenSoft,
            title: '西瓜批次补充灌溉',
            subtitle: '当前土壤墒情一般，建议及时补水。',
          ),
          _SoftDivider(),
          _SuggestionRow(
            icon: LucideIcons.circleDollarSign,
            color: AppColors.amber,
            background: AppColors.amberSoft,
            title: '本月饲料成本偏高',
            subtitle: '饲料成本环比上升，建议优化采购计划。',
          ),
        ],
      ),
    );
  }
}

class _SuggestionRow extends StatelessWidget {
  const _SuggestionRow({
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
    return SizedBox(
      height: 72,
      child: Row(
        children: [
          IconBadge(
            icon: icon,
            color: color,
            background: background,
            size: 48,
            iconSize: 25,
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: AppTextStyles.listTitle),
                const SizedBox(height: 3),
                Text(
                  subtitle,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppTextStyles.small.copyWith(fontSize: 13),
                ),
              ],
            ),
          ),
          const Icon(
            LucideIcons.chevronRight,
            size: 22,
            color: AppColors.subtle,
          ),
        ],
      ),
    );
  }
}

class _SoftDivider extends StatelessWidget {
  const _SoftDivider();

  @override
  Widget build(BuildContext context) {
    return const Divider(height: 1, color: AppColors.lineSoft);
  }
}
