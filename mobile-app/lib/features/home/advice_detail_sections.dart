part of 'advice_detail_screen.dart';

class _EvidenceCard extends StatelessWidget {
  const _EvidenceCard({required this.item});

  final AdviceItem? item;

  static bool hasContent(AdviceItem? item) {
    return (item?.detailView.evidence ?? const <AdviceEvidence>[]).any(
      (entry) =>
          entry.title.trim().isNotEmpty || entry.description.trim().isNotEmpty,
    );
  }

  @override
  Widget build(BuildContext context) {
    final evidence = (item?.detailView.evidence ?? const <AdviceEvidence>[])
        .where(
          (entry) =>
              entry.title.trim().isNotEmpty ||
              entry.description.trim().isNotEmpty,
        )
        .toList();
    final rows = [
      for (var index = 0; index < evidence.length; index++)
        _InfoRow(
          icon: _sourceIcon(evidence[index].sourceType),
          iconColor: _sourceColor(evidence[index].sourceType),
          iconBackground: _sourceBackground(evidence[index].sourceType),
          title: evidence[index].title,
          description: evidence[index].description,
          showDivider: index != evidence.length - 1,
        )
    ];
    return _DetailSectionCard(
      icon: LucideIcons.sparkles,
      title: 'AI 判断依据',
      children: rows,
    );
  }
}

class _StepsCard extends StatelessWidget {
  const _StepsCard({required this.item});

  final AdviceItem? item;

  static bool hasContent(AdviceItem? item) {
    return (item?.detailView.steps ?? const <AdviceStep>[]).any(
      (step) =>
          step.title.trim().isNotEmpty || step.description.trim().isNotEmpty,
    );
  }

  @override
  Widget build(BuildContext context) {
    final steps = (item?.detailView.steps ?? const <AdviceStep>[])
        .where(
          (step) =>
              step.title.trim().isNotEmpty ||
              step.description.trim().isNotEmpty,
        )
        .toList();
    final rows = [
      for (var index = 0; index < steps.length; index++)
        _StepRow(
          index: steps[index].order > 0 ? steps[index].order : index + 1,
          title: steps[index].title,
          description: steps[index].description,
          showDivider: index != steps.length - 1,
        )
    ];
    return _DetailSectionCard(
      icon: LucideIcons.listChecks,
      title: '执行步骤',
      children: rows,
    );
  }
}

class _RelatedCard extends StatelessWidget {
  const _RelatedCard({required this.item});

  final AdviceItem? item;

  static bool hasContent(AdviceItem? item) {
    return (item?.detailView.related ?? const <AdviceRelatedEntry>[]).any(
      (entry) =>
          entry.title.trim().isNotEmpty || entry.description.trim().isNotEmpty,
    );
  }

  @override
  Widget build(BuildContext context) {
    final related = (item?.detailView.related ?? const <AdviceRelatedEntry>[])
        .where(
          (entry) =>
              entry.title.trim().isNotEmpty ||
              entry.description.trim().isNotEmpty,
        )
        .toList();
    final rows = [
      for (var index = 0; index < related.length; index++)
        _RelatedRow(
          icon: _sourceIcon(related[index].sourceType),
          iconColor: _sourceColor(related[index].sourceType),
          iconBackground: _sourceBackground(related[index].sourceType),
          title: related[index].title,
          value: related[index].description,
          showDivider: index != related.length - 1,
        )
    ];
    return _DetailSectionCard(
      icon: LucideIcons.link,
      title: '关联事项',
      children: rows,
    );
  }
}

class _DetailSectionCard extends StatelessWidget {
  const _DetailSectionCard({
    required this.icon,
    required this.title,
    required this.children,
  });

  final IconData icon;
  final String title;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return CardPanel(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, size: 23, color: AppColors.blue),
              const SizedBox(width: 10),
              Text(title, style: AppTextStyles.dateTitle),
            ],
          ),
          const SizedBox(height: 12),
          ...children,
        ],
      ),
    );
  }
}

class _InfoRow extends StatelessWidget {
  const _InfoRow({
    required this.icon,
    required this.iconColor,
    required this.iconBackground,
    required this.title,
    required this.description,
    this.showDivider = true,
  });

  final IconData icon;
  final Color iconColor;
  final Color iconBackground;
  final String title;
  final String description;
  final bool showDivider;

  @override
  Widget build(BuildContext context) {
    final cleanTitle = title.trim();
    final cleanDescription = description.trim();
    return _DividedRow(
      showDivider: showDivider,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          IconBadge(
            icon: icon,
            color: iconColor,
            background: iconBackground,
            size: 44,
            iconSize: 22,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: _TextBlock(
              title: cleanTitle.isEmpty ? cleanDescription : cleanTitle,
              description: cleanTitle.isEmpty ? '' : cleanDescription,
            ),
          ),
        ],
      ),
    );
  }
}

class _StepRow extends StatelessWidget {
  const _StepRow({
    required this.index,
    required this.title,
    required this.description,
    this.showDivider = true,
  });

  final int index;
  final String title;
  final String description;
  final bool showDivider;

  @override
  Widget build(BuildContext context) {
    final cleanTitle = title.trim();
    final cleanDescription = description.trim();
    return _DividedRow(
      showDivider: showDivider,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 28,
            height: 28,
            decoration: BoxDecoration(
              color: AppColors.blueSoft,
              borderRadius: BorderRadius.circular(999),
              border: Border.all(color: const Color(0xFFCFE0FF)),
            ),
            child: Center(
              child: Text(
                '$index',
                style: AppTextStyles.small.copyWith(
                  color: AppColors.blue,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ),
          ),
          const SizedBox(width: 12),
          Container(
            margin: const EdgeInsets.only(top: 3),
            width: 22,
            height: 22,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(999),
              border: Border.all(color: AppColors.subtle, width: 1.4),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: _TextBlock(
              title: cleanTitle.isEmpty ? cleanDescription : cleanTitle,
              description: cleanTitle.isEmpty ? '' : cleanDescription,
            ),
          ),
        ],
      ),
    );
  }
}

class _TextBlock extends StatelessWidget {
  const _TextBlock({required this.title, required this.description});

  final String title;
  final String description;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: AppTextStyles.listTitle.copyWith(
            height: 1.36,
            fontWeight: FontWeight.w700,
          ),
        ),
        if (description.trim().isNotEmpty) ...[
          const SizedBox(height: 4),
          Text(
            description,
            style: AppTextStyles.small.copyWith(
              color: AppColors.muted,
              fontSize: 13.5,
              height: 1.46,
            ),
          ),
        ],
      ],
    );
  }
}

class _RelatedRow extends StatelessWidget {
  const _RelatedRow({
    required this.icon,
    required this.iconColor,
    required this.iconBackground,
    required this.title,
    required this.value,
    this.showDivider = true,
  });

  final IconData icon;
  final Color iconColor;
  final Color iconBackground;
  final String title;
  final String value;
  final bool showDivider;

  @override
  Widget build(BuildContext context) {
    return _DividedRow(
      showDivider: showDivider,
      child: Row(
        children: [
          IconBadge(
            icon: icon,
            color: iconColor,
            background: iconBackground,
            size: 46,
            iconSize: 23,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: AppTextStyles.listTitle.copyWith(
                    fontWeight: FontWeight.w700,
                  ),
                ),
                if (value.trim().isNotEmpty) ...[
                  const SizedBox(height: 4),
                  Text(
                    value,
                    style: AppTextStyles.small.copyWith(
                      color: AppColors.muted,
                      fontSize: 13.5,
                      height: 1.42,
                    ),
                  ),
                ],
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

class _DividedRow extends StatelessWidget {
  const _DividedRow({required this.child, required this.showDivider});

  final Widget child;
  final bool showDivider;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 10),
          child: child,
        ),
        if (showDivider) const Divider(height: 1, color: AppColors.lineSoft),
      ],
    );
  }
}

class _AdviceActionBar extends StatelessWidget {
  const _AdviceActionBar({required this.actions});

  final List<AdviceAction> actions;

  @override
  Widget build(BuildContext context) {
    final visibleActions = actions.take(2).toList();
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 12, 20, 14),
      decoration: const BoxDecoration(
        color: AppColors.surface,
        border: Border(top: BorderSide(color: AppColors.lineSoft)),
      ),
      child: SafeArea(
        top: false,
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 430),
            child: Row(
              children: [
                for (var index = 0; index < visibleActions.length; index++) ...[
                  Expanded(
                    child: _ActionButton(
                      action: visibleActions[index],
                      primary: index == 0,
                    ),
                  ),
                  if (index != visibleActions.length - 1)
                    const SizedBox(width: 12),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _ActionButton extends StatelessWidget {
  const _ActionButton({required this.action, required this.primary});

  final AdviceAction action;
  final bool primary;

  @override
  Widget build(BuildContext context) {
    final icon = _actionIcon(action.type);
    final label = Text(
      action.label,
      maxLines: 1,
      overflow: TextOverflow.ellipsis,
    );
    if (primary) {
      return FilledButton.icon(
        onPressed: () {},
        icon: Icon(icon, size: 20),
        label: label,
      );
    }
    return OutlinedButton.icon(
      onPressed: () {},
      icon: Icon(icon, size: 20),
      label: label,
    );
  }
}

List<_MetaChip> _heroMeta(List<AdviceHeroBadge> badges) {
  return badges
      .map(
        (badge) => _MetaChip(
          icon: _badgeIcon(badge.icon),
          iconColor: _levelColor(badge.level, null),
          text: badge.value,
        ),
      )
      .toList();
}

String _levelText(String? level, int? priority) {
  if (level == 'urgent' || priority == 1) return '高优先级';
  if (level == 'important' || priority == 2) return '重要';
  return '常规';
}

Color _levelColor(String? level, int? priority) {
  if (level == 'urgent' || priority == 1) return AppColors.red;
  if (level == 'important' || priority == 2) return AppColors.amber;
  return AppColors.blue;
}

Color _levelBackground(String? level, int? priority) {
  if (level == 'urgent' || priority == 1) return AppColors.redSoft;
  if (level == 'important' || priority == 2) return AppColors.amberSoft;
  return AppColors.blueSoft;
}

IconData _sourceIcon(String sourceType) {
  if (sourceType.contains('weather')) return LucideIcons.sun;
  if (sourceType.contains('work')) return LucideIcons.clipboardList;
  if (sourceType.contains('cycle') || sourceType.contains('crop')) {
    return LucideIcons.sprout;
  }
  if (sourceType.contains('finance') || sourceType.contains('cost')) {
    return LucideIcons.circleDollarSign;
  }
  return LucideIcons.link;
}

Color _sourceColor(String sourceType) {
  if (sourceType.contains('weather')) return AppColors.amber;
  if (sourceType.contains('work')) return AppColors.blue;
  if (sourceType.contains('cycle') || sourceType.contains('crop')) {
    return AppColors.greenDark;
  }
  if (sourceType.contains('finance') || sourceType.contains('cost')) {
    return AppColors.greenDark;
  }
  return AppColors.blue;
}

Color _sourceBackground(String sourceType) {
  if (sourceType.contains('weather')) return AppColors.amberSoft;
  if (sourceType.contains('work')) return AppColors.blueSoft;
  if (sourceType.contains('cycle') || sourceType.contains('crop')) {
    return AppColors.greenSoft;
  }
  if (sourceType.contains('finance') || sourceType.contains('cost')) {
    return AppColors.greenSoft;
  }
  return AppColors.blueSoft;
}

IconData _badgeIcon(String? icon) {
  if (icon == 'Calendar') return LucideIcons.calendar;
  if (icon == 'CloudSun') return LucideIcons.cloudSun;
  if (icon == 'MapPin') return LucideIcons.mapPin;
  if (icon == 'Thermometer') return LucideIcons.thermometer;
  return LucideIcons.info;
}

IconData _actionIcon(String type) {
  if (type == 'create_work_order') return LucideIcons.filePlus2;
  if (type == 'ask_agent') return LucideIcons.bot;
  return LucideIcons.circleArrowRight;
}

IconData _adviceIcon(String? icon) {
  if (icon == 'CloudSun') return LucideIcons.cloudSun;
  if (icon == 'ClipboardList') return LucideIcons.clipboardList;
  if (icon == 'CircleDollarSign') return LucideIcons.circleDollarSign;
  if (icon == 'Sprout') return LucideIcons.sprout;
  if (icon == 'NotebookPen') return LucideIcons.notebookPen;
  return LucideIcons.wheat;
}
