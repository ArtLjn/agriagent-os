part of 'billing_screen.dart';

class LedgerSummaryCard extends StatelessWidget {
  const LedgerSummaryCard({super.key});

  @override
  Widget build(BuildContext context) {
    return CardPanel(
      radius: 18,
      padding: const EdgeInsets.fromLTRB(18, 16, 18, 14),
      borderColor: const Color(0xFFDDEBFF),
      gradient: const LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [Color(0xFFF4FAFF), Color(0xFFEAF4FF)],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(16),
        child: SizedBox(
          height: 236,
          child: Stack(
            clipBehavior: Clip.hardEdge,
            children: [
              Positioned(
                left: 86,
                right: 0,
                top: 34,
                height: 168,
                child: IgnorePointer(
                  child: Opacity(
                    opacity: 0.78,
                    child: ShaderMask(
                      blendMode: BlendMode.dstIn,
                      shaderCallback: (bounds) {
                        return const LinearGradient(
                          begin: Alignment.topCenter,
                          end: Alignment.bottomCenter,
                          stops: [0, 0.72, 1],
                          colors: [
                            Colors.white,
                            Colors.white,
                            Colors.transparent
                          ],
                        ).createShader(bounds);
                      },
                      child: Image.asset(
                        AppAssets.homeHeroFarm,
                        fit: BoxFit.cover,
                        alignment: Alignment.centerRight,
                      ),
                    ),
                  ),
                ),
              ),
              Positioned.fill(
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(16),
                    gradient: const LinearGradient(
                      begin: Alignment.centerLeft,
                      end: Alignment.centerRight,
                      stops: [0, 0.46, 1],
                      colors: [
                        Color(0xF7F4FAFF),
                        Color(0xDDF4FAFF),
                        Color(0x00F4FAFF),
                      ],
                    ),
                  ),
                ),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Row(
                    children: [
                      Text('资金概览', style: AppTextStyles.dateTitle),
                      SizedBox(width: 10),
                      _LedgerPill(text: '本月'),
                      SizedBox(width: 8),
                      _LedgerPill(
                        text: 'AI分析',
                        icon: LucideIcons.sparkles,
                        foreground: Color(0xFF1473FF),
                        background: Color(0xF2FFFFFF),
                        borderColor: Color(0x662F73F6),
                      ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  SizedBox(
                    height: 122,
                    child: Align(
                      alignment: Alignment.centerLeft,
                      child: ConstrainedBox(
                        constraints: const BoxConstraints(maxWidth: 176),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Text(
                              '12.8万',
                              style: AppTextStyles.metric.copyWith(
                                color: AppColors.blue,
                                fontSize: 46,
                                height: 0.98,
                                fontFeatures: const [
                                  FontFeature.tabularFigures(),
                                ],
                              ),
                            ),
                            const SizedBox(height: 7),
                            Text(
                              '资金稳定，支出略高',
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: AppTextStyles.listTitle.copyWith(
                                color: AppColors.muted,
                                fontSize: 15,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 8),
                  const _LedgerMetricsPanel(),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _LedgerMetricsPanel extends StatelessWidget {
  const _LedgerMetricsPanel();

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 70,
      padding: const EdgeInsets.symmetric(horizontal: 8),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.88),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.lineSoft),
      ),
      child: Row(
        children: const [
          Expanded(
            child: LedgerMetricColumn(
              icon: LucideIcons.trendingUp,
              label: '收入',
              value: '2.9万',
              color: Color(0xFF08A66A),
              background: Color(0xFFE9F8F0),
            ),
          ),
          _MetricDivider(),
          Expanded(
            child: LedgerMetricColumn(
              icon: LucideIcons.arrowDownToLine,
              label: '支出',
              value: '1.8万',
              color: Color(0xFFF05A24),
              background: Color(0xFFFFF3E8),
            ),
          ),
          _MetricDivider(),
          Expanded(
            child: LedgerMetricColumn(
              icon: LucideIcons.badgeAlert,
              label: '欠款',
              value: '6410',
              color: AppColors.purple,
              background: AppColors.purpleSoft,
            ),
          ),
        ],
      ),
    );
  }
}

class LedgerMetricColumn extends StatelessWidget {
  const LedgerMetricColumn({
    super.key,
    required this.icon,
    required this.label,
    required this.value,
    required this.color,
    required this.background,
  });

  final IconData icon;
  final String label;
  final String value;
  final Color color;
  final Color background;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        IconBadge(
          icon: icon,
          color: color,
          background: background,
          size: 32,
          iconSize: 18,
        ),
        const SizedBox(width: 7),
        Flexible(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                label,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: AppTextStyles.small.copyWith(fontSize: 12),
              ),
              const SizedBox(height: 2),
              FittedBox(
                fit: BoxFit.scaleDown,
                alignment: Alignment.centerLeft,
                child: Text(
                  value,
                  maxLines: 1,
                  style: AppTextStyles.dateTitle.copyWith(
                    color: color,
                    fontSize: 18,
                    fontFeatures: const [FontFeature.tabularFigures()],
                  ),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class AiFinanceInsightCard extends StatelessWidget {
  const AiFinanceInsightCard({super.key});

  @override
  Widget build(BuildContext context) {
    return CardPanel(
      radius: 18,
      borderColor: AppColors.line,
      padding: const EdgeInsets.fromLTRB(16, 18, 14, 18),
      child: SizedBox(
        height: 72,
        child: Row(
          children: [
            Container(
              width: 56,
              height: 56,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                boxShadow: const [
                  BoxShadow(
                    color: Color(0x1A1473FF),
                    blurRadius: 14,
                    offset: Offset(0, 6),
                  ),
                ],
              ),
              clipBehavior: Clip.antiAlias,
              child: Image.asset(
                AppAssets.aiFinanceInsightLogo,
                fit: BoxFit.cover,
              ),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('AI财务洞察', style: AppTextStyles.sectionTitle),
                  const SizedBox(height: 5),
                  Text.rich(
                    TextSpan(
                      text: '饲料成本较上月上升 ',
                      children: [
                        TextSpan(
                          text: '8%',
                          style: AppTextStyles.body.copyWith(
                            color: const Color(0xFFF05A24),
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                        const TextSpan(text: '，建议复查采购单价。'),
                      ],
                    ),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: AppTextStyles.body.copyWith(
                      color: const Color(0xFF475467),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 8),
            const Icon(
              LucideIcons.chevronRight,
              size: 22,
              color: AppColors.subtle,
            ),
          ],
        ),
      ),
    );
  }
}

class _LedgerPill extends StatelessWidget {
  const _LedgerPill({
    required this.text,
    this.icon,
    this.foreground = AppColors.muted,
    this.background = const Color(0xF2FFFFFF),
    this.borderColor = const Color(0x55D8E2EC),
  });

  final String text;
  final IconData? icon;
  final Color foreground;
  final Color background;
  final Color borderColor;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 30,
      padding: const EdgeInsets.symmetric(horizontal: 10),
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: borderColor),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, size: 14, color: foreground),
            const SizedBox(width: 4),
          ],
          Text(
            text,
            style: AppTextStyles.small.copyWith(
              color: foreground,
              fontSize: 13,
              height: 16 / 13,
              fontWeight: FontWeight.w800,
            ),
          ),
        ],
      ),
    );
  }
}

class _MetricDivider extends StatelessWidget {
  const _MetricDivider();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 1,
      height: 36,
      color: AppColors.lineSoft,
    );
  }
}
