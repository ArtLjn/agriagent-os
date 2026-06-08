part of 'yaya_screen.dart';

class _BriefCard extends StatelessWidget {
  const _BriefCard();

  @override
  Widget build(BuildContext context) {
    return CardPanel(
      radius: 18,
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const IconBadge(
                icon: LucideIcons.notebookText,
                color: AppColors.greenDark,
                background: AppColors.greenSoft,
                size: 34,
                iconSize: 18,
              ),
              const SizedBox(width: 10),
              Text(
                '今日简报',
                style: AppTextStyles.dateTitle.copyWith(fontSize: 18),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: const [
              Expanded(
                child: _BriefMetric(
                  icon: LucideIcons.clipboardCheck,
                  color: AppColors.blue,
                  background: AppColors.blueSoft,
                  label: '待确认',
                  value: '2',
                  valueColor: AppColors.blue,
                ),
              ),
              _VerticalBriefDivider(),
              Expanded(
                child: _BriefMetric(
                  icon: LucideIcons.triangleAlert,
                  color: Color(0xFFFF6500),
                  background: AppColors.amberSoft,
                  label: '风险',
                  value: '1',
                  valueColor: Color(0xFFFF6500),
                ),
              ),
              _VerticalBriefDivider(),
              Expanded(
                child: _BriefMetric(
                  icon: LucideIcons.clipboardList,
                  color: AppColors.greenDark,
                  background: AppColors.greenSoft,
                  label: '今日待办',
                  value: '3',
                  valueColor: AppColors.greenDark,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _BriefMetric extends StatelessWidget {
  const _BriefMetric({
    required this.icon,
    required this.color,
    required this.background,
    required this.label,
    required this.value,
    required this.valueColor,
  });

  final IconData icon;
  final Color color;
  final Color background;
  final String label;
  final String value;
  final Color valueColor;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        IconBadge(
          icon: icon,
          color: color,
          background: background,
          size: 40,
          iconSize: 20,
        ),
        const SizedBox(height: 8),
        Text(
          label,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: AppTextStyles.small.copyWith(color: AppColors.muted),
        ),
        const SizedBox(height: 2),
        Text(
          value,
          style: AppTextStyles.metric.copyWith(color: valueColor, fontSize: 28),
        ),
      ],
    );
  }
}

class _VerticalBriefDivider extends StatelessWidget {
  const _VerticalBriefDivider();

  @override
  Widget build(BuildContext context) {
    return Container(width: 1, height: 62, color: AppColors.lineSoft);
  }
}

class _PromptQuestion extends StatelessWidget {
  const _PromptQuestion({required this.icon, required this.title});

  final IconData icon;
  final String title;

  @override
  Widget build(BuildContext context) {
    return CardPanel(
      padding: const EdgeInsets.fromLTRB(16, 12, 14, 12),
      child: Row(
        children: [
          IconBadge(
            icon: icon,
            color: AppColors.blue,
            background: AppColors.blueSoft,
            size: 40,
            iconSize: 20,
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Text(
              title,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: AppTextStyles.sectionTitle.copyWith(fontSize: 17),
            ),
          ),
          const Icon(
            LucideIcons.chevronRight,
            size: 21,
            color: AppColors.subtle,
          ),
        ],
      ),
    );
  }
}

class _ModeChips extends StatelessWidget {
  const _ModeChips();

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        children: const [
          _ModeChip(icon: LucideIcons.brain, label: '深度思考', selected: true),
          SizedBox(width: 10),
          _ModeChip(icon: LucideIcons.chartSpline, label: '经营分析'),
          SizedBox(width: 10),
          _ModeChip(icon: LucideIcons.fileChartColumn, label: '生成报告'),
          SizedBox(width: 10),
          _ModeChip(icon: LucideIcons.layoutGrid, label: '全部技能'),
        ],
      ),
    );
  }
}

class _ModeChip extends StatelessWidget {
  const _ModeChip({
    required this.icon,
    required this.label,
    this.selected = false,
  });

  final IconData icon;
  final String label;
  final bool selected;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 42,
      padding: const EdgeInsets.symmetric(horizontal: 12),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(999),
        border: Border.all(
          color: selected ? AppColors.blue : const Color(0xFFD6DEE9),
          width: selected ? 1.4 : 1,
        ),
      ),
      child: Row(
        children: [
          Icon(
            icon,
            size: 19,
            color: selected ? AppColors.blue : AppColors.muted,
          ),
          const SizedBox(width: 7),
          Text(
            label,
            style: AppTextStyles.body.copyWith(
              color: selected ? AppColors.blue : AppColors.muted,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }
}

class _YayaComposer extends StatelessWidget {
  const _YayaComposer();

  @override
  Widget build(BuildContext context) {
    return CardPanel(
      radius: 18,
      padding: const EdgeInsets.fromLTRB(12, 10, 12, 10),
      child: Row(
        children: [
          const _RobotAvatar(size: 34),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              '发消息或按住说话...',
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: AppTextStyles.body.copyWith(
                color: AppColors.subtle,
                fontSize: 14,
              ),
            ),
          ),
          const SizedBox(width: 8),
          Container(
            width: 42,
            height: 42,
            decoration: BoxDecoration(
              color: AppColors.blue,
              borderRadius: BorderRadius.circular(24),
              boxShadow: const [
                BoxShadow(
                  color: Color(0x1A2F73F6),
                  blurRadius: 14,
                  offset: Offset(0, 6),
                ),
              ],
            ),
            child: const Icon(LucideIcons.mic, color: Colors.white, size: 22),
          ),
          const SizedBox(width: 8),
          Container(
            width: 42,
            height: 42,
            decoration: BoxDecoration(
              color: AppColors.surface,
              borderRadius: BorderRadius.circular(24),
              border: Border.all(color: AppColors.blue, width: 1.5),
            ),
            child:
                const Icon(LucideIcons.plus, color: AppColors.blue, size: 22),
          ),
        ],
      ),
    );
  }
}
