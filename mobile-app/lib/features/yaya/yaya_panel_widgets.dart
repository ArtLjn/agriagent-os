part of 'yaya_screen.dart';

class _SuggestionPills extends StatelessWidget {
  const _SuggestionPills();

  @override
  Widget build(BuildContext context) {
    const suggestions = [
      _SuggestionSpec(
        icon: LucideIcons.sun,
        label: '今天适合干什么',
        color: AppColors.blue,
        background: AppColors.blueSoft,
      ),
      _SuggestionSpec(
        icon: LucideIcons.chartNoAxesColumnIncreasing,
        label: '本月成本怎么看',
        color: AppColors.greenDark,
        background: AppColors.greenSoft,
      ),
      _SuggestionSpec(
        icon: LucideIcons.fileText,
        label: '生成周报',
        color: AppColors.purple,
        background: AppColors.purpleSoft,
      ),
    ];
    return Column(
      children: [
        Wrap(
          alignment: WrapAlignment.center,
          spacing: 10,
          runSpacing: 10,
          children: [
            for (final suggestion in suggestions)
              _SuggestionPill(spec: suggestion),
          ],
        ),
        const SizedBox(height: 18),
        Align(
          alignment: Alignment.centerRight,
          child: TextButton.icon(
            onPressed: () {},
            icon: const Icon(LucideIcons.refreshCw, size: 16),
            label: const Text('换一换'),
            style: TextButton.styleFrom(
              foregroundColor: AppColors.muted,
              textStyle: AppTextStyles.body.copyWith(
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
        ),
      ],
    );
  }
}

class _SuggestionPill extends StatelessWidget {
  const _SuggestionPill({required this.spec});

  final _SuggestionSpec spec;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 50,
      padding: const EdgeInsets.fromLTRB(12, 8, 14, 8),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: AppColors.line),
        boxShadow: const [
          BoxShadow(
            color: Color(0x08000000),
            blurRadius: 16,
            offset: Offset(0, 8),
          ),
        ],
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          _SoftIcon(
            icon: spec.icon,
            color: spec.color,
            background: spec.background,
            size: 28,
            iconSize: 15,
            shape: _SoftIconShape.rounded,
          ),
          const SizedBox(width: 8),
          Text(
            spec.label,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: AppTextStyles.body.copyWith(
              color: AppColors.ink2,
              fontSize: 14,
              fontWeight: FontWeight.w800,
            ),
          ),
        ],
      ),
    );
  }
}

class _SuggestionSpec {
  const _SuggestionSpec({
    required this.icon,
    required this.label,
    required this.color,
    required this.background,
  });

  final IconData icon;
  final String label;
  final Color color;
  final Color background;
}

class _ModeChips extends StatelessWidget {
  const _ModeChips({required this.onSkillsPressed});

  final VoidCallback onSkillsPressed;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        const Expanded(
          child: ModeChip(
            icon: LucideIcons.brain,
            label: '深度思考',
            selected: true,
            compact: true,
          ),
        ),
        const SizedBox(width: 8),
        const Expanded(
          child: ModeChip(
            icon: LucideIcons.chartSpline,
            label: '经营分析',
            compact: true,
          ),
        ),
        const SizedBox(width: 8),
        const Expanded(
          child: ModeChip(
            icon: LucideIcons.fileChartColumn,
            label: '生成报告',
            compact: true,
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: ModeChip(
            icon: LucideIcons.layoutGrid,
            label: '全部技能',
            compact: true,
            onTap: onSkillsPressed,
          ),
        ),
      ],
    );
  }
}

class ModeChip extends StatelessWidget {
  const ModeChip({
    super.key,
    required this.icon,
    required this.label,
    this.selected = false,
    this.compact = false,
    this.onTap,
  });

  final IconData icon;
  final String label;
  final bool selected;
  final bool compact;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: Container(
        height: compact ? 38 : 40,
        constraints: const BoxConstraints(minWidth: 44),
        padding: EdgeInsets.symmetric(horizontal: compact ? 7 : 13),
        decoration: BoxDecoration(
          color: selected ? AppColors.blueSoft : AppColors.surface,
          borderRadius: BorderRadius.circular(999),
          border: Border.all(
            color: selected ? AppColors.blue : AppColors.line,
            width: selected ? 1.3 : 1,
          ),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              icon,
              size: compact ? 16 : 18,
              color: selected ? AppColors.blue : AppColors.muted,
            ),
            SizedBox(width: compact ? 4 : 7),
            Flexible(
              child: FittedBox(
                fit: BoxFit.scaleDown,
                child: Text(
                  label,
                  maxLines: 1,
                  style: AppTextStyles.body.copyWith(
                    color: selected ? AppColors.blue : AppColors.muted,
                    fontSize: compact ? 13 : 14,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class AssistantInputBar extends StatefulWidget {
  const AssistantInputBar({
    super.key,
    required this.onSubmit,
    this.sending = false,
  });

  final Future<void> Function(String text) onSubmit;
  final bool sending;

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
      height: 72,
      padding: const EdgeInsets.fromLTRB(12, 10, 10, 10),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(28),
        border: Border.all(color: AppColors.line),
        boxShadow: const [
          BoxShadow(
            color: Color(0x121473FF),
            blurRadius: 24,
            offset: Offset(0, 10),
          ),
        ],
      ),
      child: Row(
        children: [
          const YayaMascot(size: 42),
          const SizedBox(width: 12),
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
          const SizedBox(width: 8),
          _RoundActionButton(
            icon: widget.sending ? LucideIcons.loaderCircle : LucideIcons.send,
            filled: true,
            onTap: widget.sending ? null : _submit,
          ),
          const SizedBox(width: 8),
          _RoundActionButton(
            icon: LucideIcons.plus,
            onTap: widget.sending ? null : () {},
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
          width: 44,
          height: 44,
          decoration: BoxDecoration(
            color: filled ? AppColors.blue : AppColors.surface,
            borderRadius: BorderRadius.circular(22),
            border:
                filled ? null : Border.all(color: AppColors.blue, width: 1.4),
            boxShadow: filled
                ? const [
                    BoxShadow(
                      color: Color(0x222F73F6),
                      blurRadius: 14,
                      offset: Offset(0, 6),
                    ),
                  ]
                : null,
          ),
          child: Icon(
            icon,
            color: filled ? Colors.white : AppColors.blue,
            size: 22,
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
                      Text(
                        spec.time,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: AppTextStyles.small.copyWith(
                          color: AppColors.subtle,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 2),
                  Text(
                    spec.tag,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: AppTextStyles.small.copyWith(
                      color: spec.selected ? AppColors.blue : AppColors.subtle,
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
    this.time,
    this.tag,
    this.selected,
    this.sessionId,
  );

  final String title;
  final String time;
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
  const _DrawerUserBar();

  @override
  Widget build(BuildContext context) {
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
              '张',
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
                Text('张三', style: AppTextStyles.listTitle),
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
  const _SkillCard({required this.spec});

  final _SkillSpec spec;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppColors.line),
        boxShadow: const [
          BoxShadow(
            color: Color(0x07000000),
            blurRadius: 18,
            offset: Offset(0, 8),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _SoftIcon(
            icon: spec.icon,
            color: spec.color,
            background: spec.background,
          ),
          const Spacer(),
          Row(
            children: [
              Expanded(
                child: Text(
                  spec.title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppTextStyles.listTitle.copyWith(
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
              const Icon(
                LucideIcons.chevronRight,
                size: 18,
                color: AppColors.subtle,
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            spec.subtitle,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: AppTextStyles.small.copyWith(color: AppColors.muted),
          ),
        ],
      ),
    );
  }
}

class _RecommendedSkillList extends StatelessWidget {
  const _RecommendedSkillList({required this.skills});

  final List<_SkillSpec> skills;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(14, 16, 14, 14),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppColors.line),
        boxShadow: const [
          BoxShadow(
            color: Color(0x07000000),
            blurRadius: 18,
            offset: Offset(0, 8),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Container(
                width: 4,
                height: 22,
                decoration: BoxDecoration(
                  color: AppColors.blue,
                  borderRadius: BorderRadius.circular(999),
                ),
              ),
              const SizedBox(width: 8),
              Text(
                '推荐技能',
                style: AppTextStyles.sectionTitle.copyWith(fontSize: 17),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Container(
            decoration: BoxDecoration(
              color: AppColors.surface,
              borderRadius: BorderRadius.circular(18),
              border: Border.all(color: AppColors.lineSoft),
            ),
            child: Column(
              children: [
                for (var index = 0; index < skills.length; index++) ...[
                  _SkillListTile(spec: skills[index]),
                  if (index != skills.length - 1)
                    const Padding(
                      padding: EdgeInsets.only(left: 78, right: 14),
                      child: Divider(height: 1, color: AppColors.lineSoft),
                    ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _SkillListTile extends StatelessWidget {
  const _SkillListTile({required this.spec});

  final _SkillSpec spec;

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(minHeight: 78),
      padding: const EdgeInsets.fromLTRB(14, 12, 12, 12),
      child: Row(
        children: [
          _SoftIcon(
            icon: spec.icon,
            color: spec.color,
            background: spec.background,
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(
                  spec.title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppTextStyles.listTitle.copyWith(
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 3),
                Text(
                  spec.subtitle,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppTextStyles.small.copyWith(color: AppColors.muted),
                ),
              ],
            ),
          ),
          const Icon(
            LucideIcons.chevronRight,
            size: 20,
            color: AppColors.subtle,
          ),
        ],
      ),
    );
  }
}

enum _SoftIconShape { circle, rounded }

class _SoftIcon extends StatelessWidget {
  const _SoftIcon({
    required this.icon,
    required this.color,
    required this.background,
    this.size = 42,
    this.iconSize = 21,
    this.shape = _SoftIconShape.circle,
  });

  final IconData icon;
  final Color color;
  final Color background;
  final double size;
  final double iconSize;
  final _SoftIconShape shape;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: background,
        shape: shape == _SoftIconShape.circle
            ? BoxShape.circle
            : BoxShape.rectangle,
        borderRadius:
            shape == _SoftIconShape.rounded ? BorderRadius.circular(10) : null,
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
    required this.color,
    required this.background,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final Color color;
  final Color background;
}
