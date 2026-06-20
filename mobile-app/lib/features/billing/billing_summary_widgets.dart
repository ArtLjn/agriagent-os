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
                  const SizedBox(height: 8),
                  Text(
                    '本年收支结构 · 待收款 ${model.debtText}',
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
                                  color: _netProfitColor(model),
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
                      SizedBox(
                        width: 102,
                        height: 60,
                        child: CustomPaint(
                          painter: _LedgerSparklinePainter(
                            data: model.monthlyTrend,
                            lineColor: _netProfitColor(model),
                          ),
                        ),
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
      height: 56,
      padding: const EdgeInsets.fromLTRB(10, 8, 10, 8),
      decoration: BoxDecoration(
        color: background.withValues(alpha: 0.55),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Row(
            children: [
              Icon(icon, size: 13, color: color),
              const SizedBox(width: 4),
              Expanded(
                child: Text(
                  label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppTextStyles.small.copyWith(
                    color: AppColors.muted,
                    fontSize: 11.5,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ],
          ),
          FittedBox(
            fit: BoxFit.scaleDown,
            alignment: Alignment.centerLeft,
            child: Text(
              value,
              maxLines: 1,
              style: AppTextStyles.dateTitle.copyWith(
                color: color,
                fontSize: 16,
                fontWeight: FontWeight.w800,
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
      padding: const EdgeInsets.fromLTRB(16, 14, 14, 14),
      child: Row(
        children: [
          Container(
            width: 38,
            height: 38,
            decoration: BoxDecoration(
              color: _LedgerColors.blueSoft,
              shape: BoxShape.circle,
            ),
            child: const Icon(
              LucideIcons.chartNoAxesCombined,
              color: _LedgerColors.debt,
              size: 19,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'AI财务洞察',
                  style: AppTextStyles.sectionTitle.copyWith(
                    color: _LedgerColors.ink,
                    fontSize: 16,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 3),
                Text.rich(
                  TextSpan(
                    text: model.insightText ?? '已读取本年收支数据，建议持续关注大额支出。',
                  ),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: AppTextStyles.small.copyWith(
                    color: AppColors.muted,
                    fontSize: 12.5,
                    height: 1.35,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 6),
          const Icon(
            LucideIcons.chevronRight,
            size: 18,
            color: AppColors.subtle,
          ),
        ],
      ),
    );
  }
}

class _LedgerSparklinePainter extends CustomPainter {
  const _LedgerSparklinePainter({
    required this.data,
    required this.lineColor,
  });

  final List<double> data;
  final Color lineColor;

  @override
  void paint(Canvas canvas, Size size) {
    if (data.isEmpty) return;

    final points = _buildPoints(size);
    if (points.length < 2) {
      final center = Offset(size.width / 2, size.height / 2);
      canvas.drawCircle(center, 3.6, Paint()..color = lineColor);
      return;
    }

    final fillPaint = Paint()
      ..shader = LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        colors: [lineColor.withValues(alpha: 0.18), lineColor.withValues(alpha: 0)],
      ).createShader(Offset.zero & size);
    final linePaint = Paint()
      ..color = lineColor
      ..strokeWidth = 2.4
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;

    final line = Path()..moveTo(points.first.dx, points.first.dy);
    for (final point in points.skip(1)) {
      line.lineTo(point.dx, point.dy);
    }
    final fill = Path.from(line)
      ..lineTo(points.last.dx, size.height)
      ..lineTo(points.first.dx, size.height)
      ..close();

    canvas.drawPath(fill, fillPaint);
    canvas.drawPath(line, linePaint);

    canvas.drawCircle(points.last, 3.6, Paint()..color = Colors.white);
    canvas.drawCircle(points.last, 3.6, linePaint);
  }

  List<Offset> _buildPoints(Size size) {
    final count = data.length;
    if (count == 1) {
      return [Offset(size.width / 2, size.height / 2)];
    }
    final minVal = data.reduce((a, b) => a < b ? a : b);
    final maxVal = data.reduce((a, b) => a > b ? a : b);
    final span = (maxVal - minVal).abs();
    final padX = size.width * 0.04;
    final usableW = size.width - padX * 2;
    final stepX = count > 1 ? usableW / (count - 1) : 0.0;
    final padY = size.height * 0.18;
    final usableH = size.height - padY * 2;

    return List.generate(count, (i) {
      final dx = padX + stepX * i;
      final normalized = span == 0 ? 0.5 : (data[i] - minVal) / span;
      final dy = padY + (1 - normalized) * usableH;
      return Offset(dx, dy);
    });
  }

  @override
  bool shouldRepaint(covariant _LedgerSparklinePainter oldDelegate) {
    return lineColor != oldDelegate.lineColor ||
        !_listEquals(data, oldDelegate.data);
  }

  bool _listEquals(List<double> a, List<double> b) {
    if (a.length != b.length) return false;
    for (var i = 0; i < a.length; i++) {
      if (a[i] != b[i]) return false;
    }
    return true;
  }
}

Color _netProfitColor(BillingViewModel model) {
  if (model.isDeficit) return _LedgerColors.negative;
  if (model.netProfitText == '¥0') return _LedgerColors.ink;
  return _LedgerColors.income;
}

class _LedgerPill extends StatelessWidget {
  const _LedgerPill({
    required this.text,
    this.foreground = const Color(0xFFDCEBFF),
    this.background = const Color(0x1AFFFFFF),
    this.borderColor = const Color(0x22FFFFFF),
  });

  final String text;
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
