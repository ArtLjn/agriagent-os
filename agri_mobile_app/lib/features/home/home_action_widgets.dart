part of 'home_screen.dart';

class _QuickActionStrip extends StatelessWidget {
  const _QuickActionStrip({this.onBottomTabChanged});

  final ValueChanged<int>? onBottomTabChanged;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
            child: _ActionItem(
                icon: LucideIcons.notebookPen,
                title: '记农事',
                primary: true,
                onTap: onBottomTabChanged == null
                    ? null
                    : () => onBottomTabChanged!(1))),
        const SizedBox(width: 12),
        Expanded(
            child: _ActionItem(
                icon: LucideIcons.walletCards,
                title: '看账本',
                onTap: onBottomTabChanged == null
                    ? null
                    : () => onBottomTabChanged!(3))),
        const SizedBox(width: 12),
        Expanded(
            child: _ActionItem(
                icon: LucideIcons.bot,
                title: '问芽芽',
                onTap: onBottomTabChanged == null
                    ? null
                    : () => onBottomTabChanged!(2))),
      ],
    );
  }
}

class _ActionItem extends StatelessWidget {
  const _ActionItem(
      {required this.icon,
      required this.title,
      this.onTap,
      this.primary = false});

  final IconData icon;
  final String title;
  final VoidCallback? onTap;
  final bool primary;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      child: Material(
        color: primary ? AppColors.blue : AppColors.surface,
        borderRadius: BorderRadius.circular(16),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(16),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 16),
            child: Column(
              children: [
                Icon(icon,
                    size: 24,
                    color: primary ? AppColors.surface : AppColors.blue),
                const SizedBox(height: 12),
                Text(title,
                    style: AppTextStyles.body.copyWith(
                        color: primary ? AppColors.surface : AppColors.ink,
                        fontWeight: FontWeight.w600)),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
