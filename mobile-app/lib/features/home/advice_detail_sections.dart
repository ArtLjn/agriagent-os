part of 'advice_detail_screen.dart';

class _EvidenceCard extends StatelessWidget {
  const _EvidenceCard({required this.item});

  final AdviceItem? item;

  @override
  Widget build(BuildContext context) {
    final evidence = item?.detailView.evidence ?? const <AdviceEvidence>[];
    final rows = evidence.isEmpty
        ? const [
            _InfoRow(
              icon: LucideIcons.sparkles,
              iconColor: AppColors.blue,
              iconBackground: AppColors.blueSoft,
              text: '暂无更多判断依据',
              showDivider: false,
            )
          ]
        : [
            for (var index = 0; index < evidence.length; index++)
              _InfoRow(
                icon: _sourceIcon(evidence[index].sourceType),
                iconColor: _sourceColor(evidence[index].sourceType),
                iconBackground: _sourceBackground(evidence[index].sourceType),
                text: _joinTitleDescription(
                  evidence[index].title,
                  evidence[index].description,
                ),
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

  @override
  Widget build(BuildContext context) {
    final steps = item?.detailView.steps ?? const <AdviceStep>[];
    final rows = steps.isEmpty
        ? const [
            _StepRow(index: 1, text: '结合现场情况处理', showDivider: false),
          ]
        : [
            for (var index = 0; index < steps.length; index++)
              _StepRow(
                index: steps[index].order > 0 ? steps[index].order : index + 1,
                text: _joinTitleDescription(
                  steps[index].title,
                  steps[index].description,
                ),
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

  @override
  Widget build(BuildContext context) {
    final related = item?.detailView.related ?? const <AdviceRelatedEntry>[];
    final rows = related.isEmpty
        ? const [
            _RelatedRow(
              icon: LucideIcons.link,
              iconColor: AppColors.blue,
              iconBackground: AppColors.blueSoft,
              title: '暂无关联事项',
              value: '可继续问问芽芽',
              valueColor: AppColors.blue,
              showDivider: false,
            )
          ]
        : [
            for (var index = 0; index < related.length; index++)
              _RelatedRow(
                icon: _sourceIcon(related[index].sourceType),
                iconColor: _sourceColor(related[index].sourceType),
                iconBackground: _sourceBackground(related[index].sourceType),
                title: related[index].title,
                value: related[index].description,
                valueColor: AppColors.ink,
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
    required this.text,
    this.showDivider = true,
  });

  final IconData icon;
  final Color iconColor;
  final Color iconBackground;
  final String text;
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
            size: 44,
            iconSize: 22,
          ),
          const SizedBox(width: 12),
          Expanded(child: Text(text, style: AppTextStyles.body)),
        ],
      ),
    );
  }
}

class _StepRow extends StatelessWidget {
  const _StepRow({
    required this.index,
    required this.text,
    this.showDivider = true,
  });

  final int index;
  final String text;
  final bool showDivider;

  @override
  Widget build(BuildContext context) {
    return _DividedRow(
      showDivider: showDivider,
      child: Row(
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
            width: 22,
            height: 22,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(999),
              border: Border.all(color: AppColors.subtle, width: 1.4),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(child: Text(text, style: AppTextStyles.body)),
        ],
      ),
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
    required this.valueColor,
    this.showDivider = true,
  });

  final IconData icon;
  final Color iconColor;
  final Color iconBackground;
  final String title;
  final String value;
  final Color valueColor;
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
                Text(title, style: AppTextStyles.listTitle),
                const SizedBox(height: 2),
                Text(
                  value,
                  style: AppTextStyles.listTitle.copyWith(color: valueColor),
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
  const _AdviceActionBar({required this.suggestion});

  final HomeSuggestionViewModel suggestion;

  @override
  Widget build(BuildContext context) {
    final actions =
        suggestion.item?.detailView.actions ?? const <AdviceAction>[];
    final createAction = _firstAction(actions, 'create_work_order');
    final askAction = _firstAction(actions, 'ask_agent');
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
                Expanded(
                  child: FilledButton.icon(
                    onPressed: () {},
                    icon: const Icon(LucideIcons.filePlus2, size: 20),
                    label: Text(createAction?.label ?? '生成作业单'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: () {},
                    icon: const Icon(LucideIcons.bot, size: 20),
                    label: Text(askAction?.label ?? '问问芽芽'),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

List<_MetaChip> _heroMeta(List<AdviceHeroBadge> badges) {
  final visible = badges.isEmpty
      ? const [
          AdviceHeroBadge(label: '状态', value: '今日建议', level: 'normal'),
        ]
      : badges;
  return visible
      .map(
        (badge) => _MetaChip(
          icon: _badgeIcon(badge.icon),
          iconColor: _levelColor(badge.level, null),
          text: badge.value,
        ),
      )
      .toList();
}

String _joinTitleDescription(String title, String description) {
  final cleanTitle = title.trim();
  final cleanDescription = description.trim();
  if (cleanTitle.isEmpty) return cleanDescription;
  if (cleanDescription.isEmpty) return cleanTitle;
  return '$cleanTitle：$cleanDescription';
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

AdviceAction? _firstAction(List<AdviceAction> actions, String type) {
  for (final action in actions) {
    if (action.type == type) return action;
  }
  return null;
}
