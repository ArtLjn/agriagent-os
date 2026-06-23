part of 'billing_screen.dart';

class LedgerSummaryCard extends StatelessWidget {
  const LedgerSummaryCard({super.key, required this.model});

  final BillingViewModel model;

  @override
  Widget build(BuildContext context) {
    return _LedgerSectionCard(
      padding: const EdgeInsets.fromLTRB(20, 18, 20, 18),
      radius: 22,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 28,
                height: 28,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: AppColors.surface2,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Icon(
                  LucideIcons.wallet,
                  size: 15,
                  color: AppColors.ink2,
                ),
              ),
              const SizedBox(width: 10),
              const Expanded(
                child: Text(
                  '账本概览',
                  style: TextStyle(
                    color: AppColors.ink,
                    fontSize: 16,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 0,
                  ),
                ),
              ),
              const Text(
                '本年',
                style: TextStyle(
                  color: AppColors.subtle,
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  letterSpacing: 0.1,
                ),
              ),
            ],
          ),
          const SizedBox(height: 18),
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      '年度净收益',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        color: AppColors.muted,
                        fontSize: 12.5,
                        fontWeight: FontWeight.w600,
                        letterSpacing: 0,
                      ),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      model.netProfitText,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      softWrap: false,
                      style: TextStyle(
                        color: _netProfitColor(model),
                        fontSize: model.netProfitText.length > 12 ? 24 : 32,
                        fontWeight: FontWeight.w900,
                        height: 1,
                        letterSpacing: -0.4,
                        fontFeatures: const [
                          FontFeature.tabularFigures(),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 12),
              SizedBox(
                width: 96,
                height: 56,
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
          Container(
            height: 1,
            color: AppColors.lineSoft,
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(
                child: _MetricPlain(
                  label: '收入',
                  value: model.incomeText,
                  accent: _LedgerColors.income,
                ),
              ),
              Container(
                width: 1,
                height: 30,
                color: AppColors.lineSoft,
              ),
              Expanded(
                child: _MetricPlain(
                  label: '支出',
                  value: model.expenseText,
                  accent: _LedgerColors.expense,
                ),
              ),
              Container(
                width: 1,
                height: 30,
                color: AppColors.lineSoft,
              ),
              Expanded(
                child: _MetricPlain(
                  label: '欠款',
                  value: model.debtText,
                  accent: model.debtText == '¥0'
                      ? AppColors.muted
                      : _LedgerColors.debt,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _MetricPlain extends StatelessWidget {
  const _MetricPlain({
    required this.label,
    required this.value,
    required this.accent,
  });

  final String label;
  final String value;
  final Color accent;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          label,
          style: const TextStyle(
            color: AppColors.muted,
            fontSize: 11.5,
            fontWeight: FontWeight.w600,
            letterSpacing: 0,
          ),
        ),
        const SizedBox(height: 4),
        FittedBox(
          fit: BoxFit.scaleDown,
          alignment: Alignment.centerLeft,
          child: Text(
            value,
            maxLines: 1,
            style: TextStyle(
              color: accent,
              fontSize: 15,
              fontWeight: FontWeight.w800,
              letterSpacing: -0.2,
              fontFeatures: const [FontFeature.tabularFigures()],
            ),
          ),
        ),
      ],
    );
  }
}

class AiFinanceInsightCard extends StatelessWidget {
  const AiFinanceInsightCard({super.key, required this.model});

  final BillingViewModel model;

  @override
  Widget build(BuildContext context) {
    return _LedgerSectionCard(
      padding: const EdgeInsets.fromLTRB(16, 14, 12, 14),
      child: Row(
        children: [
          Container(
            width: 36,
            height: 36,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: AppColors.surface2,
              borderRadius: BorderRadius.circular(10),
            ),
            child: const Icon(
              LucideIcons.sparkles,
              color: AppColors.ink2,
              size: 17,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'AI 财务洞察',
                  style: TextStyle(
                    color: AppColors.ink,
                    fontSize: 15,
                    fontWeight: FontWeight.w800,
                    letterSpacing: -0.1,
                  ),
                ),
                const SizedBox(height: 3),
                Text(
                  model.insightText ?? '已读取本年收支数据，建议持续关注大额支出。',
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: AppColors.muted,
                    fontSize: 12.5,
                    height: 1.4,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 6),
          const Icon(
            LucideIcons.chevronRight,
            size: 16,
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

