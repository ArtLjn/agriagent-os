part of 'billing_screen.dart';

class LedgerSummaryCard extends StatelessWidget {
  const LedgerSummaryCard({super.key, required this.model});

  final BillingViewModel model;

  @override
  Widget build(BuildContext context) {
    return _LedgerSectionCard(
      padding: EdgeInsets.zero,
      radius: 22,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(22),
        child: Column(
          children: [
            Container(
              padding: const EdgeInsets.fromLTRB(18, 17, 18, 16),
              decoration: const BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [
                    Color(0xFFF4FAFF),
                    Color(0xFFEAF4FF),
                  ],
                ),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Row(
                          children: [
                            Text(
                              '资金概览',
                              style: AppTextStyles.dateTitle.copyWith(
                                color: _LedgerColors.ink,
                                fontSize: 20,
                              ),
                            ),
                            const SizedBox(width: 10),
                            const _LedgerPill(
                              text: '本年',
                              foreground: AppColors.blue,
                              background: Colors.white,
                              borderColor: Color(0xFFDDEBFF),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(width: 12),
                      const _LedgerPill(
                        text: '智能复盘',
                        icon: LucideIcons.sparkles,
                        foreground: AppColors.blue,
                        background: Colors.white,
                        borderColor: Color(0xFFDDEBFF),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Text(
                    '本年支出结构与待收款状态',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: AppTextStyles.small.copyWith(
                      color: AppColors.muted,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(18, 18, 18, 18),
              child: Column(
                children: [
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              '年度净收益',
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: AppTextStyles.small.copyWith(
                                color: AppColors.muted,
                                fontWeight: FontWeight.w800,
                              ),
                            ),
                            const SizedBox(height: 5),
                            FittedBox(
                              fit: BoxFit.scaleDown,
                              alignment: Alignment.centerLeft,
                              child: Text(
                                model.netProfitText,
                                maxLines: 1,
                                softWrap: false,
                                style: AppTextStyles.metric.copyWith(
                                  color: _LedgerColors.ink,
                                  fontSize: 42,
                                  height: 1,
                                  fontFeatures: const [
                                    FontFeature.tabularFigures(),
                                  ],
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(width: 18),
                      const SizedBox(
                        width: 102,
                        height: 60,
                        child: CustomPaint(painter: _LedgerSparklinePainter()),
                      ),
                    ],
                  ),
                  const SizedBox(height: 18),
                  _LedgerMetricsPanel(model: model),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _LedgerMetricsPanel extends StatelessWidget {
  const _LedgerMetricsPanel({required this.model});

  final BillingViewModel model;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: LedgerMetricColumn(
            icon: LucideIcons.trendingUp,
            label: '收入',
            value: model.incomeText,
            color: _LedgerColors.income,
            background: _LedgerColors.greenSoft,
          ),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: LedgerMetricColumn(
            icon: LucideIcons.arrowDownToLine,
            label: '支出',
            value: model.expenseText,
            color: _LedgerColors.expense,
            background: _LedgerColors.amberSoft,
          ),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: LedgerMetricColumn(
            icon: LucideIcons.badgeAlert,
            label: '欠款',
            value: model.debtText,
            color: _LedgerColors.debt,
            background: _LedgerColors.blueSoft,
          ),
        ),
      ],
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
    return Container(
      height: 72,
      padding: const EdgeInsets.fromLTRB(10, 10, 10, 9),
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: AppColors.lineSoft),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, size: 15, color: color),
              const SizedBox(width: 5),
              Expanded(
                child: Text(
                  label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppTextStyles.small.copyWith(
                    color: AppColors.muted,
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ],
          ),
          const Spacer(),
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
    );
  }
}

class AiFinanceInsightCard extends StatelessWidget {
  const AiFinanceInsightCard({super.key, required this.model});

  final BillingViewModel model;

  @override
  Widget build(BuildContext context) {
    return _LedgerSectionCard(
      padding: const EdgeInsets.fromLTRB(18, 16, 16, 16),
      child: SizedBox(
        height: 72,
        child: Row(
          children: [
            Container(
              width: 50,
              height: 50,
              decoration: BoxDecoration(
                color: _LedgerColors.blueSoft,
                shape: BoxShape.circle,
              ),
              child: const Icon(
                LucideIcons.chartNoAxesCombined,
                color: _LedgerColors.debt,
                size: 24,
              ),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Text(
                        'AI财务洞察',
                        style: AppTextStyles.sectionTitle.copyWith(
                          color: _LedgerColors.ink,
                          fontSize: 17,
                        ),
                      ),
                      const SizedBox(width: 8),
                      Container(
                        height: 22,
                        padding: const EdgeInsets.symmetric(horizontal: 8),
                        decoration: BoxDecoration(
                          color: const Color(0xFFF8FAFC),
                          borderRadius: BorderRadius.circular(999),
                          border: Border.all(color: _LedgerColors.line),
                        ),
                        child: Center(
                          child: Text(
                            '智能复盘',
                            style: AppTextStyles.small.copyWith(
                              color: AppColors.blue,
                              fontSize: 11,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 5),
                  Text.rich(
                    TextSpan(
                      text: model.insightText ?? '已读取本年收支数据，建议持续关注大额支出。',
                    ),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: AppTextStyles.body.copyWith(
                      color: AppColors.ink2,
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

class _LedgerSparklinePainter extends CustomPainter {
  const _LedgerSparklinePainter();

  @override
  void paint(Canvas canvas, Size size) {
    final fillPaint = Paint()
      ..shader = const LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        colors: [Color(0x242F73F6), Color(0x002F73F6)],
      ).createShader(Offset.zero & size);
    final linePaint = Paint()
      ..color = _LedgerColors.primary
      ..strokeWidth = 2.4
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;

    final points = [
      Offset(size.width * 0.04, size.height * 0.66),
      Offset(size.width * 0.22, size.height * 0.48),
      Offset(size.width * 0.40, size.height * 0.56),
      Offset(size.width * 0.58, size.height * 0.30),
      Offset(size.width * 0.78, size.height * 0.38),
      Offset(size.width * 0.96, size.height * 0.18),
    ];
    final line = Path()..moveTo(points.first.dx, points.first.dy);
    for (final point in points.skip(1)) {
      line.lineTo(point.dx, point.dy);
    }
    final fill = Path.from(line)
      ..lineTo(size.width * 0.96, size.height)
      ..lineTo(size.width * 0.04, size.height)
      ..close();

    canvas.drawPath(fill, fillPaint);
    canvas.drawPath(line, linePaint);
    for (final point in [points.first, points.last]) {
      canvas.drawCircle(point, 3.6, Paint()..color = Colors.white);
      canvas.drawCircle(point, 3.6, linePaint);
    }
  }

  @override
  bool shouldRepaint(covariant _LedgerSparklinePainter oldDelegate) => false;
}

class _LedgerPill extends StatelessWidget {
  const _LedgerPill({
    required this.text,
    this.icon,
    this.foreground = const Color(0xFFDCEBFF),
    this.background = const Color(0x1AFFFFFF),
    this.borderColor = const Color(0x22FFFFFF),
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
  const _MetricDivider({this.height = 36});

  final double height;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 1,
      height: height,
      color: AppColors.lineSoft,
    );
  }
}
