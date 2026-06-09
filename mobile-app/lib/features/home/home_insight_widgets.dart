part of 'home_screen.dart';

class _InsightGrid extends StatelessWidget {
  const _InsightGrid({required this.model});

  final HomeViewModel model;

  @override
  Widget build(BuildContext context) {
    return GridView.count(
      crossAxisCount: 2,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      mainAxisSpacing: 12,
      crossAxisSpacing: 12,
      childAspectRatio: 1.18,
      children: [
        _MoneyInsightCard(value: model.unsettledLaborText),
        _CostInsightCard(value: model.workOrderCountText),
        _ProgressInsightCard(value: model.headline),
        _RiskInsightCard(value: '${model.riskText}待关注'),
      ],
    );
  }
}

class _MoneyInsightCard extends StatelessWidget {
  const _MoneyInsightCard({required this.value});

  final String value;

  @override
  Widget build(BuildContext context) {
    return CardPanel(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('资金概览', style: AppTextStyles.sectionTitle),
          const Spacer(),
          Row(
            children: [
              const IconBadge(
                icon: LucideIcons.walletCards,
                color: AppColors.blue,
                background: AppColors.blueSoft,
                size: 40,
                iconSize: 22,
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '未结人工',
                      style: AppTextStyles.small.copyWith(fontSize: 13),
                    ),
                    Text(
                      value,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: AppTextStyles.dateTitle.copyWith(
                        color: AppColors.blue,
                        fontSize: 25,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          const SizedBox(height: 24, child: _Sparkline(color: AppColors.blue)),
        ],
      ),
    );
  }
}

class _CostInsightCard extends StatelessWidget {
  const _CostInsightCard({required this.value});

  final String value;

  @override
  Widget build(BuildContext context) {
    return CardPanel(
      padding: const EdgeInsets.all(14),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('成本分析', style: AppTextStyles.sectionTitle),
                const Spacer(),
                Text('作业', style: AppTextStyles.small.copyWith(fontSize: 13)),
                Text(
                  value,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppTextStyles.dateTitle.copyWith(
                    color: AppColors.greenDark,
                    fontSize: 26,
                  ),
                ),
                Text('待跟进', style: AppTextStyles.small.copyWith(fontSize: 13)),
              ],
            ),
          ),
          const SizedBox(width: 8),
          const _DonutProgress(value: 0.68),
        ],
      ),
    );
  }
}

class _ProgressInsightCard extends StatelessWidget {
  const _ProgressInsightCard({required this.value});

  final String value;

  @override
  Widget build(BuildContext context) {
    return CardPanel(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('茬口进度', style: AppTextStyles.sectionTitle),
          const Spacer(),
          Text('今日建议', style: AppTextStyles.small.copyWith(fontSize: 13)),
          Text(
            value,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: AppTextStyles.dateTitle.copyWith(
              color: AppColors.greenDark,
              fontSize: 26,
            ),
          ),
          const SizedBox(height: 10),
          ClipRRect(
            borderRadius: BorderRadius.circular(999),
            child: LinearProgressIndicator(
              value: 0.68,
              minHeight: 8,
              backgroundColor: AppColors.greenSoft,
              valueColor: const AlwaysStoppedAnimation(AppColors.greenDark),
            ),
          ),
        ],
      ),
    );
  }
}

class _RiskInsightCard extends StatelessWidget {
  const _RiskInsightCard({required this.value});

  final String value;

  @override
  Widget build(BuildContext context) {
    return CardPanel(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: const [
              Expanded(child: Text('风险预警', style: AppTextStyles.sectionTitle)),
              Icon(
                LucideIcons.chevronRight,
                size: 20,
                color: AppColors.subtle,
              ),
            ],
          ),
          const Spacer(),
          Text(
            value,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: AppTextStyles.dateTitle.copyWith(
              color: const Color(0xFFFF6500),
              fontSize: 23,
            ),
          ),
          const SizedBox(height: 14),
          Row(
            children: List.generate(4, (index) {
              return Container(
                width: 9,
                height: 9,
                margin: const EdgeInsets.only(right: 14),
                decoration: BoxDecoration(
                  color: index == 0
                      ? const Color(0xFFFF6500)
                      : const Color(0xFFDDE4EE),
                  shape: BoxShape.circle,
                ),
              );
            }),
          ),
        ],
      ),
    );
  }
}

class _Sparkline extends StatelessWidget {
  const _Sparkline({required this.color});

  final Color color;

  @override
  Widget build(BuildContext context) {
    return CustomPaint(painter: _SparklinePainter(color));
  }
}

class _SparklinePainter extends CustomPainter {
  const _SparklinePainter(this.color);

  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final line = Paint()
      ..color = color
      ..strokeWidth = 2.5
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;
    final fill = Paint()
      ..shader = LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        colors: [color.withValues(alpha: 0.16), color.withValues(alpha: 0)],
      ).createShader(Offset.zero & size);
    final points = [
      Offset(0, size.height * 0.72),
      Offset(size.width * 0.10, size.height * 0.82),
      Offset(size.width * 0.20, size.height * 0.48),
      Offset(size.width * 0.30, size.height * 0.64),
      Offset(size.width * 0.42, size.height * 0.55),
      Offset(size.width * 0.54, size.height * 0.66),
      Offset(size.width * 0.66, size.height * 0.36),
      Offset(size.width * 0.78, size.height * 0.48),
      Offset(size.width * 0.90, size.height * 0.23),
      Offset(size.width, size.height * 0.28),
    ];
    final path = Path()..moveTo(points.first.dx, points.first.dy);
    for (final point in points.skip(1)) {
      path.lineTo(point.dx, point.dy);
    }
    final fillPath = Path.from(path)
      ..lineTo(size.width, size.height)
      ..lineTo(0, size.height)
      ..close();
    canvas.drawPath(fillPath, fill);
    canvas.drawPath(path, line);
  }

  @override
  bool shouldRepaint(covariant _SparklinePainter oldDelegate) =>
      color != oldDelegate.color;
}

class _DonutProgress extends StatelessWidget {
  const _DonutProgress({required this.value});

  final double value;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 74,
      height: 74,
      child: Stack(
        alignment: Alignment.center,
        children: [
          CustomPaint(
              size: const Size.square(74), painter: _DonutPainter(value)),
          Text(
            '8%',
            style: AppTextStyles.sectionTitle.copyWith(
              color: AppColors.greenDark,
              fontSize: 18,
            ),
          ),
        ],
      ),
    );
  }
}

class _DonutPainter extends CustomPainter {
  const _DonutPainter(this.value);

  final double value;

  @override
  void paint(Canvas canvas, Size size) {
    final rect = Offset.zero & size;
    final stroke = size.width * 0.16;
    final base = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = stroke
      ..strokeCap = StrokeCap.butt
      ..color = AppColors.greenSoft;
    final progress = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = stroke
      ..strokeCap = StrokeCap.butt
      ..shader = const SweepGradient(
        colors: [Color(0xFFBDEFD4), AppColors.greenDark],
      ).createShader(rect);
    canvas.drawCircle(rect.center, (size.width - stroke) / 2, base);
    canvas.drawArc(
      rect.deflate(stroke / 2),
      -1.57,
      6.28 * value,
      false,
      progress,
    );
  }

  @override
  bool shouldRepaint(covariant _DonutPainter oldDelegate) =>
      value != oldDelegate.value;
}
