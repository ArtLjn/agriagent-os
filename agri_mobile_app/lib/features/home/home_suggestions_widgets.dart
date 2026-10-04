part of 'home_screen.dart';

class _AiSuggestionsCard extends StatelessWidget {
  const _AiSuggestionsCard(
      {required this.suggestions,
      required this.score,
      this.onBottomTabChanged});

  final List<HomeSuggestionViewModel> suggestions;
  final String score;
  final ValueChanged<int>? onBottomTabChanged;

  @override
  Widget build(BuildContext context) {
    // 概览占位文案不是 AI 建议；只有实际建议才开放详情入口。
    final visible =
        suggestions.where((suggestion) => suggestion.item != null).toList();
    return CardPanel(
      padding: const EdgeInsets.all(20),
      shadow: false,
      radius: 20,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              const Icon(LucideIcons.sparkles, size: 20, color: AppColors.blue),
              const SizedBox(width: 8),
              Expanded(
                  child: Text('芽芽建议',
                      style: AppTextStyles.sectionTitle
                          .copyWith(fontWeight: FontWeight.w600))),
              if (score != '暂无评分')
                StatusPill(
                    text: score,
                    color: AppColors.blue,
                    background: AppColors.blueSoft),
            ],
          ),
          const SizedBox(height: 16),
          if (visible.isEmpty) ...[
            Text('把问题交给芽芽，把时间留给田间。',
                style:
                    AppTextStyles.body.copyWith(fontWeight: FontWeight.w600)),
            const SizedBox(height: 8),
            Text('今天还没有经营建议。农场里的疑问，可以和芽芽聊聊。',
                style: AppTextStyles.body.copyWith(color: AppColors.muted)),
            const SizedBox(height: 16),
            Align(
              alignment: Alignment.centerLeft,
              child: TextButton.icon(
                onPressed: onBottomTabChanged == null
                    ? null
                    : () => onBottomTabChanged!(2),
                style: TextButton.styleFrom(
                    foregroundColor: AppColors.blue,
                    backgroundColor: AppColors.blueSoft,
                    minimumSize: const Size(140, 48)),
                icon: const Icon(LucideIcons.bot, size: 18),
                label: const Text('问问芽芽'),
              ),
            ),
          ] else
            for (var index = 0; index < visible.length; index++) ...[
              _SuggestionRow(
                suggestion: visible[index],
                onTap: () {
                  Navigator.of(context).push(MaterialPageRoute<void>(
                    builder: (_) => AdviceDetailScreen(
                        suggestion: visible[index],
                        onBottomTabChanged: onBottomTabChanged),
                  ));
                },
              ),
              if (index != visible.length - 1)
                const Divider(height: 24, color: AppColors.lineSoft),
            ],
        ],
      ),
    );
  }
}

class _SuggestionRow extends StatelessWidget {
  const _SuggestionRow({required this.suggestion, required this.onTap});

  final HomeSuggestionViewModel suggestion;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final icon = switch (suggestion.item?.compact.icon) {
      'CloudSun' => LucideIcons.cloudSun,
      'ClipboardList' => LucideIcons.clipboardList,
      'CircleDollarSign' => LucideIcons.circleDollarSign,
      'Sprout' => LucideIcons.sprout,
      'NotebookPen' => LucideIcons.notebookPen,
      _ => LucideIcons.sparkles,
    };
    final color = switch (suggestion.item?.compact.iconColor) {
      'green' || 'emerald' => AppColors.greenDark,
      'amber' => AppColors.amber,
      _ => AppColors.blue,
    };
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 12),
          child: Row(
            children: [
              IconBadge(
                  icon: icon,
                  color: color,
                  background: color.withValues(alpha: 0.08),
                  size: 40,
                  iconSize: 20),
              const SizedBox(width: 12),
              Expanded(
                  child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(suggestion.title,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: AppTextStyles.body
                          .copyWith(fontWeight: FontWeight.w600)),
                  const SizedBox(height: 4),
                  Text(suggestion.subtitle,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: AppTextStyles.small.copyWith(height: 1.5)),
                ],
              )),
              const SizedBox(width: 8),
              const Icon(LucideIcons.chevronRight,
                  size: 18, color: AppColors.subtle),
            ],
          ),
        ),
      ),
    );
  }
}
