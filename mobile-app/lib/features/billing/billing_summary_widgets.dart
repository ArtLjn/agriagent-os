part of 'billing_screen.dart';

class LedgerSummaryCard extends StatelessWidget {
  const LedgerSummaryCard({super.key});

  @override
  Widget build(BuildContext context) {
    return CardPanel(
      radius: 20,
      padding: const EdgeInsets.all(20),
      borderColor: const Color(0xFFD7E9FF),
      background: const Color(0xFFEEF7FF),
      child: SizedBox(
        height: 224,
        child: Stack(
          children: [
            Positioned(
              left: 50,
              right: -38,
              top: 20,
              height: 154,
              child: IgnorePointer(
                child: Opacity(
                  opacity: 0.76,
                  child: ShaderMask(
                    blendMode: BlendMode.dstIn,
                    shaderCallback: (bounds) {
                      return const LinearGradient(
                        begin: Alignment.topCenter,
                        end: Alignment.bottomCenter,
                        stops: [0, 0.48, 0.76],
                        colors: [
                          Colors.white,
                          Colors.white,
                          Colors.transparent,
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
            Positioned(
              left: 0,
              right: 0,
              top: 112,
              bottom: 0,
              child: DecoratedBox(
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topCenter,
                    end: Alignment.bottomCenter,
                    colors: [
                      const Color(0xFFEEF7FF).withValues(alpha: 0),
                      const Color(0xFFEEF7FF).withValues(alpha: 0.94),
                      const Color(0xFFEEF7FF),
                    ],
                  ),
                ),
              ),
            ),
            Positioned(
              left: 0,
              right: 112,
              top: 38,
              bottom: 112,
              child: DecoratedBox(
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(18),
                  gradient: const LinearGradient(
                    begin: Alignment.centerLeft,
                    end: Alignment.centerRight,
                    colors: [
                      Color(0xF2EEF7FF),
                      Color(0xCDEEF7FF),
                      Color(0x00EEF7FF),
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
                const SizedBox(height: 72),
                SizedBox(
                  height: 116,
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: const [
                      Expanded(
                        child: LedgerMetricColumn(
                          label: '收入(元)',
                          value: '28,650',
                          trendValue: '+12%',
                          color: Color(0xFF08A66A),
                        ),
                      ),
                      _MetricDivider(),
                      Expanded(
                        child: LedgerMetricColumn(
                          label: '支出(元)',
                          value: '18,240',
                          trendValue: '+8%',
                          color: Color(0xFFF05A24),
                        ),
                      ),
                      _MetricDivider(),
                      Expanded(
                        child: LedgerMetricColumn(
                          label: '欠款(元)',
                          value: '6,410',
                          trendValue: '-5%',
                          color: AppColors.purple,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class LedgerMetricColumn extends StatelessWidget {
  const LedgerMetricColumn({
    super.key,
    required this.label,
    required this.value,
    required this.trendValue,
    required this.color,
  });

  final String label;
  final String value;
  final String trendValue;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisAlignment: MainAxisAlignment.end,
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: AppTextStyles.small.copyWith(
            color: const Color(0xFF667085),
            fontSize: 13,
            height: 18 / 13,
          ),
        ),
        const SizedBox(height: 6),
        FittedBox(
          fit: BoxFit.scaleDown,
          alignment: Alignment.centerLeft,
          child: Text(
            value,
            maxLines: 1,
            style: AppTextStyles.metric.copyWith(
              color: color,
              fontSize: 30,
              height: 36 / 30,
              fontFeatures: const [FontFeature.tabularFigures()],
            ),
          ),
        ),
        const SizedBox(height: 5),
        FittedBox(
          fit: BoxFit.scaleDown,
          alignment: Alignment.centerLeft,
          child: Text.rich(
            TextSpan(
              text: '较上月 ',
              children: [
                TextSpan(
                  text: trendValue,
                  style: AppTextStyles.small.copyWith(
                    color: color,
                    fontSize: 13,
                    height: 18 / 13,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ],
            ),
            maxLines: 1,
            style: AppTextStyles.small.copyWith(
              color: const Color(0xFF667085),
              fontSize: 13,
              height: 18 / 13,
              fontWeight: FontWeight.w700,
            ),
          ),
        ),
        const SizedBox(height: 9),
        SizedBox(
          width: 70,
          height: 20,
          child: _SmallTrendLine(color: color),
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
      height: 88,
      margin: const EdgeInsets.symmetric(horizontal: 10),
      color: const Color(0xFFDDE7F3),
    );
  }
}

class _SmallTrendLine extends StatelessWidget {
  const _SmallTrendLine({required this.color});

  final Color color;

  @override
  Widget build(BuildContext context) {
    return CustomPaint(painter: _SmallTrendLinePainter(color));
  }
}

class _SmallTrendLinePainter extends CustomPainter {
  const _SmallTrendLinePainter(this.color);

  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final glowPaint = Paint()
      ..color = color.withValues(alpha: 0.10)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 5
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;
    final linePaint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.1
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;
    final path = Path()
      ..moveTo(0, size.height * 0.72)
      ..cubicTo(
        size.width * 0.15,
        size.height * 0.82,
        size.width * 0.22,
        size.height * 0.35,
        size.width * 0.36,
        size.height * 0.48,
      )
      ..cubicTo(
        size.width * 0.48,
        size.height * 0.58,
        size.width * 0.56,
        size.height * 0.24,
        size.width * 0.70,
        size.height * 0.36,
      )
      ..cubicTo(
        size.width * 0.84,
        size.height * 0.46,
        size.width * 0.88,
        size.height * 0.22,
        size.width,
        size.height * 0.16,
      );
    canvas.drawPath(path, glowPaint);
    canvas.drawPath(path, linePaint);
  }

  @override
  bool shouldRepaint(covariant _SmallTrendLinePainter oldDelegate) =>
      color != oldDelegate.color;
}
