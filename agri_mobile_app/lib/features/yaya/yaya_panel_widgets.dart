part of 'yaya_screen.dart';

class _SuggestionPills extends StatefulWidget {
  const _SuggestionPills({required this.onSelected});

  final ValueChanged<String> onSelected;

  @override
  State<_SuggestionPills> createState() => _SuggestionPillsState();
}

class _SuggestionPillsState extends State<_SuggestionPills> {
  static const _suggestionGroups = [
    [
      _SuggestionSpec(
        label: '记录今天农活',
      ),
      _SuggestionSpec(
        label: '今天适合干什么',
      ),
      _SuggestionSpec(
        label: '本月成本怎么看',
      ),
      _SuggestionSpec(
        label: '生成周报',
      ),
    ],
    [
      _SuggestionSpec(
        label: '查一下最近天气',
      ),
      _SuggestionSpec(
        label: '记录今天农活',
      ),
      _SuggestionSpec(
        label: '帮我记一笔账',
      ),
      _SuggestionSpec(
        label: '查看待确认事项',
      ),
    ],
    [
      _SuggestionSpec(
        label: '查看种植批次',
      ),
      _SuggestionSpec(
        label: '看看未结工资',
      ),
      _SuggestionSpec(
        label: '生成经营报告',
      ),
      _SuggestionSpec(
        label: '今天适合干什么',
      ),
    ],
  ];

  int _groupIndex = 0;

  void _shuffleSuggestions() {
    setState(() {
      _groupIndex = (_groupIndex + 1) % _suggestionGroups.length;
    });
  }

  @override
  Widget build(BuildContext context) {
    final suggestions = _suggestionGroups[_groupIndex];
    return Padding(
      padding: EdgeInsets.zero,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  '常用问题',
                  style: AppTextStyles.small.copyWith(
                    color: AppColors.subtle,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
              TextButton(
                onPressed: _shuffleSuggestions,
                style: TextButton.styleFrom(
                  foregroundColor: AppColors.subtle,
                  minimumSize: const Size(0, 28),
                  padding: EdgeInsets.zero,
                  tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  textStyle: AppTextStyles.small.copyWith(
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                child: const Text('换一批'),
              ),
            ],
          ),
          const SizedBox(height: 2),
          Container(
            decoration: const BoxDecoration(
              border: Border(
                top: BorderSide(color: AppColors.lineSoft),
              ),
            ),
            child: Column(
              children: [
                for (var index = 0; index < suggestions.length; index++)
                  _SuggestionRow(
                    number: index + 1,
                    spec: suggestions[index],
                    showDivider: index != suggestions.length - 1,
                    onTap: () => widget.onSelected(suggestions[index].label),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _SuggestionRow extends StatelessWidget {
  const _SuggestionRow({
    required this.number,
    required this.spec,
    required this.showDivider,
    required this.onTap,
  });

  final int number;
  final _SuggestionSpec spec;
  final bool showDivider;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        child: Container(
          height: 44,
          alignment: Alignment.centerLeft,
          padding: const EdgeInsets.symmetric(horizontal: 2),
          decoration: BoxDecoration(
            border: showDivider
                ? const Border(bottom: BorderSide(color: AppColors.lineSoft))
                : null,
          ),
          child: Row(
            children: [
              SizedBox(
                width: 28,
                child: Text(
                  number.toString().padLeft(2, '0'),
                  style: AppTextStyles.small.copyWith(
                    color: AppColors.subtle,
                    fontSize: 11,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
              Expanded(
                child: Text(
                  spec.label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppTextStyles.body.copyWith(
                    color: AppColors.ink2,
                    fontSize: 14,
                    fontWeight: FontWeight.w700,
                    height: 1.2,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _SuggestionSpec {
  const _SuggestionSpec({
    required this.label,
  });

  final String label;
}

class AssistantInputBar extends StatefulWidget {
  const AssistantInputBar({
    super.key,
    required this.onSubmit,
    this.sending = false,
    this.onMorePressed,
    this.embedded = false,
  });

  final Future<void> Function(String text) onSubmit;
  final bool sending;
  final VoidCallback? onMorePressed;
  final bool embedded;

  @override
  State<AssistantInputBar> createState() => _AssistantInputBarState();
}

class _AssistantInputBarState extends State<AssistantInputBar> {
  final textController = TextEditingController();

  @override
  void dispose() {
    textController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final text = textController.text.trim();
    if (text.isEmpty || widget.sending) return;
    await widget.onSubmit(text);
    if (mounted) textController.clear();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      height: widget.embedded ? 52 : 56,
      padding: EdgeInsets.fromLTRB(
          10, widget.embedded ? 6 : 7, 6, widget.embedded ? 6 : 7),
      decoration: BoxDecoration(
        color: widget.embedded ? AppColors.surface3 : AppColors.surface,
        borderRadius: BorderRadius.circular(28),
        border: Border.all(color: AppColors.lineSoft),
        boxShadow: widget.embedded
            ? null
            : const [
                BoxShadow(
                  color: Color(0x080B2447),
                  blurRadius: 12,
                  offset: Offset(0, 5),
                ),
              ],
      ),
      child: Row(
        children: [
          const YayaMascot(size: 30),
          const SizedBox(width: 8),
          Expanded(
            child: Material(
              color: Colors.transparent,
              child: TextField(
                controller: textController,
                enabled: !widget.sending,
                minLines: 1,
                maxLines: 1,
                textInputAction: TextInputAction.send,
                onSubmitted: (_) => _submit(),
                decoration: InputDecoration(
                  hintText: '发消息或按住说话...',
                  hintStyle: AppTextStyles.body.copyWith(
                    color: AppColors.subtle,
                    fontSize: 15,
                  ),
                  border: InputBorder.none,
                  isDense: true,
                  contentPadding: EdgeInsets.zero,
                ),
                style: AppTextStyles.body.copyWith(
                  color: AppColors.ink,
                  fontSize: 15,
                ),
              ),
            ),
          ),
          const SizedBox(width: 4),
          _RoundActionButton(
            icon: widget.sending ? LucideIcons.loaderCircle : LucideIcons.send,
            filled: true,
            onTap: widget.sending ? null : _submit,
          ),
          const SizedBox(width: 6),
          _RoundActionButton(
            icon: LucideIcons.plus,
            onTap: widget.sending ? null : widget.onMorePressed,
          ),
        ],
      ),
    );
  }
}

class _RoundActionButton extends StatelessWidget {
  const _RoundActionButton({
    required this.icon,
    this.filled = false,
    this.onTap,
  });

  final IconData icon;
  final bool filled;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final active = onTap != null;
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: Opacity(
        opacity: active ? 1 : 0.58,
        child: Container(
          width: 42,
          height: 42,
          decoration: BoxDecoration(
            color: filled ? AppColors.blue : AppColors.surface,
            borderRadius: BorderRadius.circular(21),
            border:
                filled ? null : Border.all(color: AppColors.blue, width: 1.5),
            boxShadow: filled
                ? const [
                    BoxShadow(
                      color: Color(0x1A2F73F6),
                      blurRadius: 10,
                      offset: Offset(0, 4),
                    ),
                  ]
                : null,
          ),
          child: Icon(
            icon,
            color: filled ? Colors.white : AppColors.blue,
            size: 21,
          ),
        ),
      ),
    );
  }
}

class _DrawerSkillEntry extends StatelessWidget {
  const _DrawerSkillEntry({required this.onTap});

  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: Container(
        height: 58,
        padding: const EdgeInsets.symmetric(horizontal: 14),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: AppColors.line),
        ),
        child: Row(
          children: [
            const _SoftIcon(
              icon: LucideIcons.layoutGrid,
              color: AppColors.blue,
              background: AppColors.blueSoft,
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                '全部技能',
                style: AppTextStyles.listTitle.copyWith(
                  fontWeight: FontWeight.w800,
                ),
              ),
            ),
            const Icon(
              LucideIcons.chevronRight,
              size: 20,
              color: AppColors.subtle,
            ),
          ],
        ),
      ),
    );
  }
}

class _RecentChatHeader extends StatelessWidget {
  const _RecentChatHeader();

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: Text(
            '最近对话',
            style: AppTextStyles.sectionTitle.copyWith(fontSize: 17),
          ),
        ),
        Container(
          height: 32,
          padding: const EdgeInsets.symmetric(horizontal: 12),
          decoration: BoxDecoration(
            color: AppColors.blueSoft,
            borderRadius: BorderRadius.circular(16),
          ),
          alignment: Alignment.center,
          child: Text(
            '芽芽对话',
            style: AppTextStyles.small.copyWith(
              color: AppColors.blue,
              fontWeight: FontWeight.w800,
            ),
          ),
        ),
      ],
    );
  }
}

class _ChatSection extends StatelessWidget {
  const _ChatSection({
    required this.title,
    required this.items,
    required this.onTap,
  });

  final String title;
  final List<_ChatItemSpec> items;
  final ValueChanged<String> onTap;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.only(left: 4),
          child: Text(
            title,
            style: AppTextStyles.small.copyWith(
              color: AppColors.subtle,
              fontWeight: FontWeight.w800,
            ),
          ),
        ),
        const SizedBox(height: 8),
        for (var index = 0; index < items.length; index++) ...[
          _ChatItem(
            spec: items[index],
            onTap: () => onTap(items[index].sessionId),
          ),
          if (index != items.length - 1) const SizedBox(height: 2),
        ],
      ],
    );
  }
}

class _ChatItem extends StatelessWidget {
  const _ChatItem({required this.spec, required this.onTap});

  final _ChatItemSpec spec;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: Container(
        constraints: const BoxConstraints(minHeight: 50),
        padding: const EdgeInsets.fromLTRB(10, 7, 10, 7),
        decoration: BoxDecoration(
          color: spec.selected ? AppColors.blueSoft : Colors.transparent,
          borderRadius: BorderRadius.circular(14),
        ),
        child: Row(
          children: [
            Icon(
              LucideIcons.messageCircle,
              size: 17,
              color: spec.selected ? AppColors.blue : AppColors.subtle,
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          spec.title,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: AppTextStyles.listTitle.copyWith(
                            color: spec.selected
                                ? AppColors.blueDark
                                : AppColors.ink,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      ConstrainedBox(
                        constraints: const BoxConstraints(maxWidth: 56),
                        child: Text(
                          spec.tag,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          textAlign: TextAlign.right,
                          style: AppTextStyles.small.copyWith(
                            color: spec.selected
                                ? AppColors.blue
                                : AppColors.subtle,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 2),
                  Text(
                    spec.preview,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: AppTextStyles.small.copyWith(
                      color: AppColors.subtle,
                      fontSize: 11,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ChatItemSpec {
  const _ChatItemSpec(
    this.title,
    this.preview,
    this.tag,
    this.selected,
    this.sessionId,
  );

  final String title;
  final String preview;
  final String tag;
  final bool selected;
  final String sessionId;
}

class _EmptyHistory extends StatelessWidget {
  const _EmptyHistory();

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 86,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: AppColors.background,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: AppColors.lineSoft),
      ),
      child: Text(
        '暂无历史会话',
        style: AppTextStyles.body.copyWith(color: AppColors.subtle),
      ),
    );
  }
}

class _DrawerUserBar extends StatelessWidget {
  const _DrawerUserBar({required this.nickname});

  final String nickname;

  @override
  Widget build(BuildContext context) {
    final displayName = nickname.trim().isEmpty ? '农友' : nickname.trim();
    return Container(
      padding: const EdgeInsets.fromLTRB(18, 12, 18, 18),
      decoration: const BoxDecoration(
        color: AppColors.surface,
        border: Border(top: BorderSide(color: AppColors.lineSoft)),
      ),
      child: Row(
        children: [
          Container(
            width: 42,
            height: 42,
            decoration: BoxDecoration(
              color: AppColors.blueSoft,
              borderRadius: BorderRadius.circular(16),
            ),
            alignment: Alignment.center,
            child: Text(
              displayName.characters.first,
              style: AppTextStyles.sectionTitle.copyWith(
                color: AppColors.blue,
              ),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  displayName,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppTextStyles.listTitle,
                ),
                const SizedBox(height: 2),
                Text(
                  '农场负责人',
                  style: AppTextStyles.small.copyWith(color: AppColors.muted),
                ),
              ],
            ),
          ),
          Stack(
            clipBehavior: Clip.none,
            children: [
              const _HeaderIconButton(icon: LucideIcons.settings),
              Positioned(
                top: 8,
                right: 8,
                child: Container(
                  width: 8,
                  height: 8,
                  decoration: const BoxDecoration(
                    color: AppColors.red,
                    shape: BoxShape.circle,
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _SkillCard extends StatelessWidget {
  const _SkillCard({required this.spec, required this.onDetailsTap});

  final _SkillSpec spec;
  final VoidCallback onDetailsTap;

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(minHeight: 92),
      padding: const EdgeInsets.fromLTRB(16, 16, 14, 16),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: AppColors.line),
        boxShadow: const [
          BoxShadow(
            color: Color(0x07000000),
            blurRadius: 18,
            offset: Offset(0, 8),
          ),
        ],
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          _SoftIcon(
            icon: spec.icon,
            color: spec.color,
            background: spec.background,
            size: 52,
            iconSize: 24,
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  spec.title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppTextStyles.sectionTitle.copyWith(
                    fontSize: 17,
                    fontWeight: FontWeight.w800,
                    height: 22 / 17,
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  spec.subtitle,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppTextStyles.small.copyWith(
                    color: AppColors.muted,
                    height: 18 / 12,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 10),
          IconButton(
            onPressed: onDetailsTap,
            tooltip: '查看${spec.title}详情',
            style: IconButton.styleFrom(
              backgroundColor: AppColors.surface2,
              fixedSize: const Size(36, 36),
              minimumSize: const Size(36, 36),
              padding: EdgeInsets.zero,
            ),
            icon: const Icon(
              LucideIcons.chevronRight,
              size: 19,
              color: AppColors.subtle,
            ),
          ),
        ],
      ),
    );
  }
}

class _SkillDetailsSheet extends StatelessWidget {
  const _SkillDetailsSheet({required this.spec});

  final _SkillSpec spec;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      top: false,
      child: Container(
        margin: const EdgeInsets.all(12),
        padding: const EdgeInsets.fromLTRB(20, 10, 20, 20),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(24),
          boxShadow: const [
            BoxShadow(
              color: Color(0x1A000000),
              blurRadius: 28,
              offset: Offset(0, 12),
            ),
          ],
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(
              child: Container(
                width: 36,
                height: 4,
                margin: const EdgeInsets.only(bottom: 18),
                decoration: BoxDecoration(
                  color: AppColors.line,
                  borderRadius: BorderRadius.circular(999),
                ),
              ),
            ),
            Row(
              children: [
                _SoftIcon(
                  icon: spec.icon,
                  color: spec.color,
                  background: spec.background,
                  size: 48,
                  iconSize: 23,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        spec.title,
                        style: AppTextStyles.sectionTitle.copyWith(
                          fontSize: 18,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      const SizedBox(height: 3),
                      Text(
                        spec.category,
                        style: AppTextStyles.small.copyWith(
                          color: AppColors.subtle,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 18),
            Text(
              spec.details,
              style: AppTextStyles.body.copyWith(
                color: AppColors.ink2,
                height: 22 / 14,
              ),
            ),
            if (spec.examples.isNotEmpty) ...[
              const SizedBox(height: 18),
              Text(
                '可以这样问',
                style: AppTextStyles.listTitle.copyWith(
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 10),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  for (final example in spec.examples)
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 12,
                        vertical: 8,
                      ),
                      decoration: BoxDecoration(
                        color: AppColors.surface2,
                        borderRadius: BorderRadius.circular(16),
                        border: Border.all(color: AppColors.lineSoft),
                      ),
                      child: Text(
                        example,
                        style: AppTextStyles.small.copyWith(
                          color: AppColors.ink2,
                        ),
                      ),
                    ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _SoftIcon extends StatelessWidget {
  const _SoftIcon({
    required this.icon,
    required this.color,
    required this.background,
    this.size = 42,
    this.iconSize = 21,
  });

  final IconData icon;
  final Color color;
  final Color background;
  final double size;
  final double iconSize;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: background,
        shape: BoxShape.circle,
      ),
      child: Icon(icon, color: color, size: iconSize),
    );
  }
}

class _SkillSpec {
  const _SkillSpec({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.details,
    required this.examples,
    required this.category,
    required this.color,
    required this.background,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final String details;
  final List<String> examples;
  final String category;
  final Color color;
  final Color background;
}

_SkillSpec _skillSpecFromApi(YayaSkill skill) {
  final colors = _skillColors(skill.iconColor);
  return _SkillSpec(
    icon: _skillIcon(skill.icon),
    title: skill.title,
    subtitle: skill.summary,
    details: skill.details,
    examples: skill.examples,
    category: skill.category,
    color: colors.$1,
    background: colors.$2,
  );
}

IconData _skillIcon(String icon) {
  return switch (icon) {
    'clipboard-list' => LucideIcons.notebookText,
    'receipt-yuan' => LucideIcons.walletCards,
    'file-pen' => LucideIcons.clipboardPenLine,
    'user-round' => LucideIcons.handCoins,
    'layout-grid' => LucideIcons.layers3,
    'pie-chart' => LucideIcons.chartPie,
    'cloud-sun' => LucideIcons.cloudSun,
    'settings' => LucideIcons.settings,
    _ => LucideIcons.sparkles,
  };
}

(Color, Color) _skillColors(String color) {
  return switch (color) {
    'green' => (AppColors.greenDark, AppColors.greenSoft),
    'amber' || 'orange' => (AppColors.amber, AppColors.amberSoft),
    'purple' => (AppColors.purple, AppColors.purpleSoft),
    'teal' => (AppColors.teal, AppColors.tealSoft),
    'gray' => (AppColors.muted, AppColors.surface2),
    _ => (AppColors.blue, AppColors.blueSoft),
  };
}
