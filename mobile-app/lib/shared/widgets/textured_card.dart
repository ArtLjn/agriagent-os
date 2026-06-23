import 'dart:math' as math;
import 'package:flutter/material.dart';

import '../../theme/app_colors.dart';

class TexturedCard extends StatelessWidget {
  const TexturedCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(20),
    this.radius = 24,
    this.accent,
    this.accentSoft,
    this.border,
    this.shadow = true,
    this.patternOpacity = 0.06,
  });

  final Widget child;
  final EdgeInsets padding;
  final double radius;
  final Color? accent;
  final Color? accentSoft;
  final Color? border;
  final bool shadow;
  final double patternOpacity;

  @override
  Widget build(BuildContext context) {
    final hasAccent = accent != null;
    return CustomPaint(
      painter: _TexturedPainter(
        accent: accent ?? const Color(0xFF9EB1C7),
        patternOpacity: patternOpacity,
      ),
      child: Container(
        padding: padding,
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [
              Colors.white,
              accentSoft ?? const Color(0xFFF4F7FB),
              const Color(0xFFEEF2F7),
            ],
            stops: const [0, 0.55, 1],
          ),
          borderRadius: BorderRadius.circular(radius),
          border: Border.all(color: border ?? AppColors.lineSoft),
          boxShadow: shadow
              ? [
                  BoxShadow(
                    color: hasAccent
                        ? (accent!.withValues(alpha: 0.10))
                        : const Color(0x08000000),
                    blurRadius: 18,
                    offset: const Offset(0, 8),
                  ),
                ]
              : null,
        ),
        child: child,
      ),
    );
  }
}

class _TexturedPainter extends CustomPainter {
  const _TexturedPainter({
    required this.accent,
    required this.patternOpacity,
  });

  final Color accent;
  final double patternOpacity;

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = accent.withValues(alpha: patternOpacity);

    const spacing = 14.0;
    const dotRadius = 1.1;

    for (var y = -spacing; y < size.height + spacing; y += spacing) {
      final rowOffset = ((y / spacing).round() % 2) * (spacing / 2);
      for (var x = -spacing; x < size.width + spacing; x += spacing) {
        canvas.drawCircle(
          Offset(x + rowOffset, y),
          dotRadius,
          paint,
        );
      }
    }

    final sparkle = Paint()
      ..color = Colors.white.withValues(alpha: 0.6)
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 14);
    canvas.drawCircle(
      Offset(size.width * 0.85, size.height * 0.15),
      32,
      sparkle,
    );

    final corner = Paint()
      ..color = accent.withValues(alpha: 0.18)
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 24);
    canvas.drawCircle(
      Offset(size.width + 18, -18),
      56,
      corner,
    );
  }

  @override
  bool shouldRepaint(covariant _TexturedPainter oldDelegate) =>
      oldDelegate.accent != accent || oldDelegate.patternOpacity != patternOpacity;
}

class GradientIconTile extends StatelessWidget {
  const GradientIconTile({
    super.key,
    required this.icon,
    required this.accent,
    this.size = 46,
    this.iconSize = 22,
    this.borderRadius = 14,
    this.shadowOpacity = 0.28,
  });

  final IconData icon;
  final Color accent;
  final double size;
  final double iconSize;
  final double borderRadius;
  final double shadowOpacity;

  @override
  Widget build(BuildContext context) {
    final gradAngle = math.pi / 4;
    return Container(
      width: size,
      height: size,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment(gradAngle * -1 * 0.5, -1),
          end: Alignment(gradAngle * 0.5, 1),
          colors: [
            accent,
            Color.lerp(accent, Colors.black, 0.18)!,
          ],
        ),
        borderRadius: BorderRadius.circular(borderRadius),
        boxShadow: [
          BoxShadow(
            color: accent.withValues(alpha: shadowOpacity),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Icon(icon, size: iconSize, color: Colors.white),
    );
  }
}
