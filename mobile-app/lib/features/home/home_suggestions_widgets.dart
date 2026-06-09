part of 'home_screen.dart';

class _AiSuggestionsCard extends StatelessWidget {
  const _AiSuggestionsCard({required this.suggestions});

  final List<HomeSuggestionViewModel> suggestions;

  @override
  Widget build(BuildContext context) {
    final visible = suggestions.isEmpty
        ? const [HomeSuggestionViewModel(title: '暂无建议', subtitle: '稍后再来看看')]
        : suggestions;
    return CardPanel(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(LucideIcons.sparkles, size: 24, color: AppColors.blue),
              SizedBox(width: 10),
              Text('AI 今日建议', style: AppTextStyles.dateTitle),
            ],
          ),
          const SizedBox(height: 12),
          for (var index = 0; index < visible.length; index++) ...[
            _SuggestionRow(
              icon: _suggestionIcon(index),
              color: _suggestionColor(index),
              background: _suggestionBackground(index),
              title: visible[index].title,
              subtitle: visible[index].subtitle,
            ),
            if (index != visible.length - 1) const _SoftDivider(),
          ],
        ],
      ),
    );
  }

  IconData _suggestionIcon(int index) {
    return const [
      LucideIcons.cloudRain,
      LucideIcons.droplets,
      LucideIcons.circleDollarSign,
    ][index % 3];
  }

  Color _suggestionColor(int index) {
    return const [
      AppColors.blue,
      AppColors.greenDark,
      AppColors.amber
    ][index % 3];
  }

  Color _suggestionBackground(int index) {
    return const [
      AppColors.blueSoft,
      AppColors.greenSoft,
      AppColors.amberSoft,
    ][index % 3];
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
                Text(
                  title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppTextStyles.listTitle,
                ),
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
