part of 'yaya_screen.dart';

class _RobotAvatar extends StatelessWidget {
  const _RobotAvatar({required this.size});

  final double size;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: size,
      height: size,
      child: Stack(
        alignment: Alignment.center,
        children: [
          Positioned.fill(child: CustomPaint(painter: _OrbitPainter())),
          Container(
            width: size * 0.68,
            height: size * 0.68,
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [Color(0xFFFFFFFF), Color(0xFFE9F3FF)],
              ),
              borderRadius: BorderRadius.circular(size * 0.26),
              boxShadow: const [
                BoxShadow(
                  color: Color(0x14000000),
                  blurRadius: 18,
                  offset: Offset(0, 8),
                ),
              ],
            ),
            child: Center(
              child: Container(
                width: size * 0.42,
                height: size * 0.25,
                decoration: BoxDecoration(
                  color: AppColors.navy,
                  borderRadius: BorderRadius.circular(size * 0.13),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    _Eye(size: size * 0.07),
                    SizedBox(width: size * 0.09),
                    _Eye(size: size * 0.07),
                  ],
                ),
              ),
            ),
          ),
          Positioned(
            top: size * 0.02,
            child: Icon(
              LucideIcons.sprout,
              color: AppColors.green,
              size: size * 0.30,
            ),
          ),
          Positioned(
            bottom: size * 0.18,
            child: Icon(
              LucideIcons.leaf,
              color: AppColors.green,
              size: size * 0.17,
            ),
          ),
        ],
      ),
    );
  }
}

class _OrbitPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final orbit = Paint()
      ..color = const Color(0xFF8BD7FF).withValues(alpha: 0.65)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2;
    final dot = Paint()..color = AppColors.blue;
    final bars = Paint()
      ..color = AppColors.blue.withValues(alpha: 0.9)
      ..strokeWidth = 4
      ..strokeCap = StrokeCap.round;

    canvas.drawArc(
      Rect.fromLTWH(10, 18, size.width - 20, size.height - 36),
      2.8,
      4.6,
      false,
      orbit,
    );
    canvas.drawCircle(Offset(size.width * 0.83, size.height * 0.34), 4, dot);
    for (var i = 0; i < 4; i++) {
      final x = size.width * (0.08 + i * 0.055);
      final bottom = size.height * 0.58;
      canvas.drawLine(
        Offset(x, bottom),
        Offset(x, bottom - 10 - i * 4),
        bars,
      );
    }
  }

  @override
  bool shouldRepaint(covariant _OrbitPainter oldDelegate) => false;
}

class _Eye extends StatelessWidget {
  const _Eye({required this.size});

  final double size;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: const BoxDecoration(
        color: Color(0xFF38C7FF),
        shape: BoxShape.circle,
      ),
    );
  }
}
