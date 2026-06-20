part of 'home_screen.dart';

class _AiSuggestionsCard extends StatelessWidget {
  const _AiSuggestionsCard({
    required this.suggestions,
    this.onBottomTabChanged,
  });

  final List<HomeSuggestionViewModel> suggestions;
  final ValueChanged<int>? onBottomTabChanged;

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
              icon: _suggestionIcon(visible[index], index),
              color: _suggestionColor(visible[index], index),
              background: _suggestionBackground(visible[index], index),
              title: visible[index].title,
              subtitle: visible[index].subtitle,
              onTap: () {
                Navigator.of(context).push(
                  MaterialPageRoute<void>(
                    builder: (_) => AdviceDetailScreen(
                      suggestion: visible[index],
                      onBottomTabChanged: onBottomTabChanged,
                    ),
                  ),
                );
              },
            ),
            if (index != visible.length - 1) const _SoftDivider(),
          ],
        ],
      ),
    );
  }

  IconData _suggestionIcon(HomeSuggestionViewModel suggestion, int index) {
    final icon = suggestion.item?.compact.icon;
    if (icon == 'CloudSun') return LucideIcons.cloudSun;
    if (icon == 'ClipboardList') return LucideIcons.clipboardList;
    if (icon == 'CircleDollarSign') return LucideIcons.circleDollarSign;
    if (icon == 'Sprout') return LucideIcons.sprout;
    if (icon == 'NotebookPen') return LucideIcons.notebookPen;
    return const [
      LucideIcons.cloudRain,
      LucideIcons.droplets,
      LucideIcons.circleDollarSign,
    ][index % 3];
  }

  Color _suggestionColor(HomeSuggestionViewModel suggestion, int index) {
    final color = suggestion.item?.compact.iconColor;
    if (color == 'green' || color == 'emerald') return AppColors.greenDark;
    if (color == 'amber') return AppColors.amber;
    if (color == 'blue') return AppColors.blue;
    return const [
      AppColors.blue,
      AppColors.greenDark,
      AppColors.amber
    ][index % 3];
  }

  Color _suggestionBackground(HomeSuggestionViewModel suggestion, int index) {
    final color = suggestion.item?.compact.iconColor;
    if (color == 'green' || color == 'emerald') return AppColors.greenSoft;
    if (color == 'amber') return AppColors.amberSoft;
    if (color == 'blue') return AppColors.blueSoft;
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
    required this.onTap,
  });

  final IconData icon;
  final Color color;
  final Color background;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: SizedBox(
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
        ),
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
