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
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        const Expanded(child: Text('从一个话题开始', style: AppTextStyles.small)),
        TextButton.icon(
            onPressed: _shuffleSuggestions,
            icon: const Icon(LucideIcons.refreshCw, size: 14),
            label: const Text('换一批'),
            style: TextButton.styleFrom(foregroundColor: AppColors.muted)),
      ]),
      const SizedBox(height: 8),
      LayoutBuilder(
          builder: (context, constraints) => Wrap(
                spacing: 12,
                runSpacing: 12,
                children: [
                  for (var index = 0; index < suggestions.length; index++)
                    SizedBox(
                        width: (constraints.maxWidth - 12) / 2,
                        child: _SuggestionRow(
                            spec: suggestions[index],
                            icon: [
                              LucideIcons.sprout,
                              LucideIcons.cloudSun,
                              LucideIcons.chartNoAxesCombined,
                              LucideIcons.notebookText
                            ][index],
                            onTap: () =>
                                widget.onSelected(suggestions[index].label))),
                ],
              )),
    ]);
  }
}

class _SuggestionRow extends StatelessWidget {
  const _SuggestionRow(
      {required this.spec, required this.icon, required this.onTap});
  final _SuggestionSpec spec;
  final IconData icon;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: AppColors.surface,
      shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: const BorderSide(color: AppColors.line)),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Container(
          constraints: const BoxConstraints(minHeight: 104),
          padding: const EdgeInsets.all(16),
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
              Icon(icon, color: AppColors.blue, size: 20),
              const Icon(LucideIcons.arrowUpRight,
                  color: AppColors.subtle, size: 16),
            ]),
            const SizedBox(height: 16),
            Text(spec.label, style: AppTextStyles.body),
          ]),
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
  });

  final Future<void> Function(String text) onSubmit;
  final bool sending;
  final VoidCallback? onMorePressed;

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
    return Material(
      color: AppColors.surface,
      shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(24),
          side: const BorderSide(color: AppColors.line)),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 16, 12, 10),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          TextField(
            controller: textController,
            enabled: !widget.sending,
            minLines: 1,
            maxLines: 4,
            textInputAction: TextInputAction.send,
            onSubmitted: (_) => _submit(),
            decoration: const InputDecoration(
              hintText: '说说你的农场问题…',
              hintStyle: AppTextStyles.body,
              border: InputBorder.none,
              isDense: true,
              contentPadding: EdgeInsets.zero,
            ),
            style:
                AppTextStyles.body.copyWith(color: AppColors.ink, height: 1.5),
          ),
          const SizedBox(height: 12),
          Row(children: [
            TextButton.icon(
              onPressed: widget.sending ? null : widget.onMorePressed,
              icon: const Icon(LucideIcons.plus, size: 18),
              label: const Text('技能'),
              style: TextButton.styleFrom(
                  foregroundColor: AppColors.muted,
                  padding: const EdgeInsets.symmetric(horizontal: 8)),
            ),
            const Spacer(),
            IconButton.filled(
              tooltip: widget.sending ? '正在回复' : '发送',
              onPressed: widget.sending ? null : _submit,
              style: IconButton.styleFrom(
                  backgroundColor: AppColors.blue,
                  disabledBackgroundColor: AppColors.blueSoft,
                  foregroundColor: Colors.white,
                  minimumSize: const Size(44, 44)),
              icon: Icon(
                  widget.sending ? LucideIcons.loaderCircle : LucideIcons.send,
                  size: 20),
            ),
          ]),
        ]),
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
                  fontWeight: FontWeight.w600,
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
              fontWeight: FontWeight.w600,
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
              fontWeight: FontWeight.w600,
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
                            fontWeight: FontWeight.w600,
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
                            fontWeight: FontWeight.w600,
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
    return Material(
      color: AppColors.surface,
      shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: const BorderSide(color: AppColors.lineSoft)),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onDetailsTap,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 16, 4, 16),
          child: Row(children: [
            _SoftIcon(
                icon: spec.icon,
                color: spec.color,
                background: spec.background,
                size: 40,
                iconSize: 20),
            const SizedBox(width: 14),
            Expanded(
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                  Text(spec.title, style: AppTextStyles.listTitle),
                  const SizedBox(height: 6),
                  Text(spec.subtitle,
                      maxLines: 3,
                      overflow: TextOverflow.ellipsis,
                      style: AppTextStyles.small),
                ])),
            IconButton(
                onPressed: onDetailsTap,
                tooltip: '查看${spec.title}详情',
                icon: const Icon(LucideIcons.chevronRight,
                    size: 18, color: AppColors.subtle)),
          ]),
        ),
      ),
    );
  }
}

class _SkillDetailsSheet extends StatelessWidget {
  const _SkillDetailsSheet({required this.spec});

  final _SkillSpec spec;

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints:
          BoxConstraints(maxHeight: MediaQuery.sizeOf(context).height * 0.85),
      decoration: const BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.vertical(top: Radius.circular(24))),
      child: SafeArea(
        top: false,
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(24, 20, 24, 28),
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            Row(children: [
              _SoftIcon(
                  icon: spec.icon,
                  color: spec.color,
                  background: spec.background,
                  size: 40,
                  iconSize: 20),
              const SizedBox(width: 12),
              Expanded(
                  child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                    Text(spec.title, style: AppTextStyles.sectionTitle),
                    const SizedBox(height: 4),
                    Text(spec.category, style: AppTextStyles.small),
                  ])),
              IconButton(
                  tooltip: '关闭',
                  onPressed: () => Navigator.of(context).pop(),
                  icon: const Icon(LucideIcons.x, size: 20)),
            ]),
            const SizedBox(height: 24),
            Text(spec.details, style: AppTextStyles.body),
            if (spec.examples.isNotEmpty) ...[
              const SizedBox(height: 28),
              const Text('可以这样问', style: AppTextStyles.listTitle),
              const SizedBox(height: 8),
              const Text('点击一个例子，向芽芽提问', style: AppTextStyles.small),
              const SizedBox(height: 16),
              for (final example in spec.examples) ...[
                OutlinedButton(
                  style: OutlinedButton.styleFrom(
                      padding: const EdgeInsets.all(16),
                      foregroundColor: AppColors.ink,
                      side: const BorderSide(color: AppColors.lineSoft),
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12))),
                  onPressed: () => Navigator.of(context).pop(example),
                  child: Row(children: [
                    Expanded(child: Text(example, style: AppTextStyles.body)),
                    const SizedBox(width: 12),
                    const Icon(LucideIcons.arrowUpRight,
                        size: 18, color: AppColors.blue)
                  ]),
                ),
                const SizedBox(height: 12),
              ],
            ],
          ]),
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
