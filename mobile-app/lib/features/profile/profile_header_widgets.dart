part of 'profile_screen.dart';

class _ProfileCard extends StatelessWidget {
  const _ProfileCard({required this.model});

  final ProfileViewModel model;

  @override
  Widget build(BuildContext context) {
    return CardPanel(
      radius: 18,
      padding: const EdgeInsets.all(20),
      borderColor: const Color(0xFFDDEBFF),
      gradient: const LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [Colors.white, Color(0xFFEFFBF7)],
      ),
      child: Stack(
        children: [
          const Positioned(
            right: -16,
            bottom: -18,
            child: _ProfileLeafWatermark(),
          ),
          Row(
            children: [
              const _Avatar(),
              const SizedBox(width: 18),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      model.nickname,
                      style: AppTextStyles.metric.copyWith(
                        fontSize: 28,
                        height: 34 / 28,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      '${model.phone} · ${model.role}',
                      style:
                          AppTextStyles.body.copyWith(color: AppColors.muted),
                    ),
                    const SizedBox(height: 10),
                    Row(
                      children: [
                        const Icon(
                          LucideIcons.mapPin,
                          size: 18,
                          color: AppColors.greenDark,
                        ),
                        const SizedBox(width: 6),
                        Expanded(
                          child: Text(
                            model.city,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: AppTextStyles.body.copyWith(
                              color: AppColors.ink2,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 10),
                    StatusPill(
                      text: model.status,
                      color: AppColors.greenDark,
                      background: AppColors.greenSoft,
                    ),
                  ],
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _Avatar extends StatelessWidget {
  const _Avatar();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 88,
      height: 88,
      decoration: BoxDecoration(
        color: const Color(0xFFDDEBFF),
        borderRadius: BorderRadius.circular(44),
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(44),
        child: CustomPaint(painter: _AvatarPainter()),
      ),
    );
  }
}

class _ProfileLeafWatermark extends StatelessWidget {
  const _ProfileLeafWatermark();

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 130,
      height: 110,
      child: CustomPaint(painter: _ProfileLeafPainter()),
    );
  }
}

class _ProfileLeafPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()..color = AppColors.green.withValues(alpha: 0.12);
    canvas.drawOval(
      Rect.fromLTWH(
        size.width * 0.12,
        size.height * 0.34,
        size.width * 0.42,
        size.height * 0.70,
      ),
      paint,
    );
    canvas.drawOval(
      Rect.fromLTWH(
        size.width * 0.44,
        size.height * 0.05,
        size.width * 0.42,
        size.height * 0.78,
      ),
      paint,
    );
  }

  @override
  bool shouldRepaint(covariant _ProfileLeafPainter oldDelegate) => false;
}

class _AvatarPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final bg = Paint()..color = const Color(0xFFDDEBFF);
    final skin = Paint()..color = const Color(0xFFFFC29C);
    final cheek = Paint()
      ..color = const Color(0xFFFFA98D).withValues(alpha: 0.35);
    final hair = Paint()..color = const Color(0xFF141A24);
    final shirt = Paint()..color = AppColors.blue;
    final collar = Paint()..color = const Color(0xFF9CC3FF);
    final eye = Paint()..color = AppColors.ink;
    final smile = Paint()
      ..color = const Color(0xFFD6684C)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.6
      ..strokeCap = StrokeCap.round;

    canvas.drawCircle(center, size.width / 2, bg);
    canvas.drawOval(
      Rect.fromCenter(
        center: Offset(size.width / 2, size.height * 0.92),
        width: size.width * 0.78,
        height: size.height * 0.44,
      ),
      shirt,
    );
    canvas.drawCircle(
      Offset(size.width / 2, size.height * 0.43),
      size.width * 0.24,
      skin,
    );
    canvas.drawArc(
      Rect.fromCircle(
        center: Offset(size.width / 2, size.height * 0.35),
        radius: size.width * 0.245,
      ),
      3.05,
      3.2,
      true,
      hair,
    );
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromLTWH(
          size.width * 0.28,
          size.height * 0.25,
          size.width * 0.44,
          size.height * 0.16,
        ),
        Radius.circular(size.width * 0.08),
      ),
      hair,
    );
    canvas.drawCircle(
      Offset(size.width * 0.36, size.height * 0.46),
      3.2,
      cheek,
    );
    canvas.drawCircle(
      Offset(size.width * 0.64, size.height * 0.46),
      3.2,
      cheek,
    );
    canvas.drawCircle(Offset(size.width * 0.42, size.height * 0.42), 2, eye);
    canvas.drawCircle(Offset(size.width * 0.58, size.height * 0.42), 2, eye);
    canvas.drawArc(
      Rect.fromCenter(
        center: Offset(size.width / 2, size.height * 0.51),
        width: size.width * 0.16,
        height: size.height * 0.08,
      ),
      0.1,
      2.9,
      false,
      smile,
    );
    final collarPath = Path()
      ..moveTo(size.width * 0.42, size.height * 0.66)
      ..lineTo(size.width * 0.50, size.height * 0.75)
      ..lineTo(size.width * 0.58, size.height * 0.66)
      ..close();
    canvas.drawPath(collarPath, collar);
  }

  @override
  bool shouldRepaint(covariant _AvatarPainter oldDelegate) => false;
}
