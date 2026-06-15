import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../shared/app_identity.dart';
import '../../shared/widgets/card_panel.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';

class AuthPage extends StatelessWidget {
  const AuthPage({
    super.key,
    required this.children,
    this.bottomPadding = 32,
  });

  final List<Widget> children;
  final double bottomPadding;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: DecoratedBox(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [
              Color(0xFFFFFFFF),
              Color(0xFFF0F6FF),
              AppColors.background
            ],
            stops: [0, 0.42, 1],
          ),
        ),
        child: SafeArea(
          child: SingleChildScrollView(
            padding: EdgeInsets.fromLTRB(24, 18, 24, bottomPadding),
            child: Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 430),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: children,
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class AuthBrandHeader extends StatelessWidget {
  const AuthBrandHeader({
    super.key,
    required this.title,
    required this.subtitle,
    this.compact = false,
  });

  final String title;
  final String subtitle;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    if (compact) {
      return SizedBox(
        height: 222,
        child: Stack(
          clipBehavior: Clip.none,
          children: [
            const Positioned(
              right: -30,
              top: -24,
              child: _FloatingCardsScene(width: 220, height: 150),
            ),
            Positioned(
              left: 0,
              top: 16,
              child: Row(
                children: [
                  const AuthLogo(size: 46),
                  const SizedBox(width: 12),
                  Text(
                    AppIdentity.displayName,
                    style: AppTextStyles.sectionTitle.copyWith(fontSize: 18),
                  ),
                ],
              ),
            ),
            Positioned(
              left: 0,
              right: 0,
              bottom: 28,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: const TextStyle(
                      color: AppColors.ink,
                      fontSize: 31,
                      height: 38 / 31,
                      fontWeight: FontWeight.w800,
                      letterSpacing: 0,
                    ),
                  ),
                  const SizedBox(height: 12),
                  Text(
                    subtitle,
                    style: AppTextStyles.body.copyWith(
                      color: AppColors.subtle,
                      fontSize: 18,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      );
    }

    return SizedBox(
      height: 286,
      child: Stack(
        clipBehavior: Clip.none,
        children: [
          const Positioned(
            right: -40,
            top: 14,
            child: _FloatingCardsScene(width: 238, height: 190),
          ),
          Positioned(
            left: 10,
            top: 56,
            child: AuthLogo(size: 78),
          ),
          Positioned(
            left: 0,
            right: 0,
            bottom: 24,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    color: AppColors.ink,
                    fontSize: 42,
                    height: 48 / 42,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 0,
                  ),
                ),
                const SizedBox(height: 12),
                Text(
                  subtitle,
                  style: AppTextStyles.body.copyWith(
                    color: AppColors.subtle,
                    fontSize: 18,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class SetupHero extends StatelessWidget {
  const SetupHero({super.key});

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 252,
      child: Stack(
        clipBehavior: Clip.none,
        children: [
          Positioned(
            left: -10,
            top: 18,
            child: Text(
              '完善农场信息',
              style: const TextStyle(
                color: AppColors.ink,
                fontSize: 32,
                height: 39 / 32,
                fontWeight: FontWeight.w800,
                letterSpacing: 0,
              ),
            ),
          ),
          Positioned(
            left: -8,
            top: 76,
            child: Text(
              '这些信息之后也可以修改',
              style: AppTextStyles.body.copyWith(
                color: AppColors.subtle,
                fontSize: 17,
              ),
            ),
          ),
          Positioned(
            left: 0,
            right: 0,
            bottom: 0,
            child: SizedBox(
              height: 138,
              child: Stack(
                children: [
                  Positioned.fill(
                    child: CustomPaint(painter: _SetupBlobPainter()),
                  ),
                  const Positioned(
                    left: 6,
                    bottom: 16,
                    child: _SetupFeatureCard(
                      icon: LucideIcons.cloudSun,
                      label: '天气',
                    ),
                  ),
                  const Positioned(
                    left: 130,
                    bottom: 36,
                    child: _SetupFeatureCard(
                      icon: LucideIcons.notebookText,
                      label: '记录',
                      emphasized: true,
                    ),
                  ),
                  const Positioned(
                    right: 8,
                    bottom: 16,
                    child: _SetupFeatureCard(
                      icon: LucideIcons.walletCards,
                      label: '账本',
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class AuthSurfaceCard extends StatelessWidget {
  const AuthSurfaceCard({
    super.key,
    required this.children,
    this.padding = const EdgeInsets.all(20),
  });

  final List<Widget> children;
  final EdgeInsets padding;

  @override
  Widget build(BuildContext context) {
    return CardPanel(
      radius: 24,
      padding: padding,
      borderColor: AppColors.line,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: children,
      ),
    );
  }
}

class AuthInputField extends StatelessWidget {
  const AuthInputField({
    super.key,
    required this.label,
    required this.placeholder,
    required this.icon,
    this.controller,
    this.trailing,
    this.readOnly = false,
    this.onTap,
    this.height = 52,
    this.labelGap = 10,
    this.labelFontSize = 15,
    this.obscureText = false,
  });

  final String label;
  final String placeholder;
  final IconData icon;
  final TextEditingController? controller;
  final Widget? trailing;
  final bool readOnly;
  final VoidCallback? onTap;
  final double height;
  final double labelGap;
  final double labelFontSize;
  final bool obscureText;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: AppTextStyles.sectionTitle.copyWith(fontSize: labelFontSize),
        ),
        SizedBox(height: labelGap),
        Container(
          height: height,
          padding: const EdgeInsets.symmetric(horizontal: 16),
          decoration: BoxDecoration(
            color: AppColors.surface,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: AppColors.line),
          ),
          child: Row(
            children: [
              Icon(icon, size: 20, color: AppColors.subtle),
              const SizedBox(width: 12),
              Expanded(
                child: Semantics(
                  label: label,
                  child: TextField(
                    controller: controller,
                    readOnly: readOnly,
                    onTap: onTap,
                    obscureText: obscureText,
                    maxLines: 1,
                    style: AppTextStyles.body.copyWith(
                      color: AppColors.ink,
                      fontSize: 15,
                    ),
                    decoration: InputDecoration(
                      border: InputBorder.none,
                      isDense: true,
                      contentPadding: EdgeInsets.zero,
                      hintText: placeholder,
                      hintStyle: AppTextStyles.body.copyWith(
                        color: AppColors.subtle,
                        fontSize: 15,
                      ),
                    ),
                  ),
                ),
              ),
              if (trailing != null) ...[
                const SizedBox(width: 10),
                trailing!,
              ],
            ],
          ),
        ),
      ],
    );
  }
}

class AuthPrimaryButton extends StatelessWidget {
  const AuthPrimaryButton({
    super.key,
    required this.label,
    required this.onTap,
  });

  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      child: Container(
        height: 52,
        decoration: BoxDecoration(
          color: AppColors.blue,
          borderRadius: BorderRadius.circular(14),
          boxShadow: const [
            BoxShadow(
              color: Color(0x1A2F73F6),
              blurRadius: 18,
              offset: Offset(0, 8),
            ),
          ],
        ),
        child: Center(
          child: Text(
            label,
            style: AppTextStyles.sectionTitle.copyWith(
              color: Colors.white,
              fontSize: 18,
            ),
          ),
        ),
      ),
    );
  }
}

class AuthTextLink extends StatelessWidget {
  const AuthTextLink({
    super.key,
    required this.prefix,
    required this.action,
    required this.onTap,
  });

  final String prefix;
  final String action;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 6),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              prefix,
              style: AppTextStyles.body.copyWith(color: AppColors.muted),
            ),
            const SizedBox(width: 6),
            Text(
              action,
              style: AppTextStyles.body.copyWith(
                color: AppColors.blue,
                fontWeight: FontWeight.w800,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class AuthLogo extends StatelessWidget {
  const AuthLogo({super.key, this.size = 64, this.accent = true});

  final double size;
  final bool accent;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(size * 0.24),
        boxShadow: const [
          BoxShadow(
            color: Color(0x10000000),
            blurRadius: 18,
            offset: Offset(0, 8),
          ),
        ],
      ),
      child: CustomPaint(painter: _AuthLogoPainter(accent: accent)),
    );
  }
}

class DataNotice extends StatelessWidget {
  const DataNotice({
    super.key,
    required this.text,
    this.topPadding = 20,
  });

  final String text;
  final double topPadding;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(top: topPadding),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(LucideIcons.shieldCheck, size: 18, color: AppColors.blue),
          const SizedBox(width: 8),
          Text(
            text,
            style: AppTextStyles.body.copyWith(color: AppColors.subtle),
          ),
        ],
      ),
    );
  }
}

class CapabilityChip extends StatelessWidget {
  const CapabilityChip({
    super.key,
    required this.label,
    required this.icon,
    required this.color,
    required this.background,
  });

  final String label;
  final IconData icon;
  final Color color;
  final Color background;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 48,
      padding: const EdgeInsets.symmetric(horizontal: 9),
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(17),
        border: Border.all(color: color.withValues(alpha: 0.14)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            width: 28,
            height: 28,
            decoration: BoxDecoration(
              color: color,
              borderRadius: BorderRadius.circular(14),
            ),
            child: Icon(icon, size: 16, color: Colors.white),
          ),
          const SizedBox(width: 6),
          Flexible(
            child: FittedBox(
              fit: BoxFit.scaleDown,
              child: Text(
                label,
                maxLines: 1,
                style: AppTextStyles.listTitle.copyWith(
                  color: color,
                  fontSize: 14,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _FloatingCardsScene extends StatelessWidget {
  const _FloatingCardsScene({required this.width, required this.height});

  final double width;
  final double height;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: width,
      height: height,
      child: Stack(
        clipBehavior: Clip.none,
        children: [
          Positioned.fill(child: CustomPaint(painter: _OrbitPainter())),
          Positioned(
            right: 8,
            top: 4,
            child: Transform.rotate(
              angle: 0.08,
              child: _MiniGlassCard(
                width: width * 0.58,
                height: height * 0.34,
                child: const _ChartGlyph(),
              ),
            ),
          ),
          Positioned(
            left: width * 0.18,
            top: height * 0.42,
            child: Transform.rotate(
              angle: -0.04,
              child: _MiniGlassCard(
                width: width * 0.45,
                height: height * 0.28,
                child: const _MetricGlyph(),
              ),
            ),
          ),
          Positioned(
            right: width * 0.02,
            bottom: height * 0.1,
            child: Container(
              width: height * 0.3,
              height: height * 0.3,
              decoration: BoxDecoration(
                color: AppColors.green.withValues(alpha: 0.75),
                borderRadius: BorderRadius.circular(16),
                boxShadow: [
                  BoxShadow(
                    color: AppColors.green.withValues(alpha: 0.2),
                    blurRadius: 18,
                    offset: const Offset(0, 8),
                  ),
                ],
              ),
              child: const Icon(LucideIcons.check, color: Colors.white),
            ),
          ),
        ],
      ),
    );
  }
}

class _MiniGlassCard extends StatelessWidget {
  const _MiniGlassCard({
    required this.width,
    required this.height,
    required this.child,
  });

  final double width;
  final double height;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: width,
      height: height,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.78),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: Colors.white.withValues(alpha: 0.9)),
        boxShadow: const [
          BoxShadow(
            color: Color(0x0F2F73F6),
            blurRadius: 20,
            offset: Offset(0, 10),
          ),
        ],
      ),
      child: child,
    );
  }
}

class _ChartGlyph extends StatelessWidget {
  const _ChartGlyph();

  @override
  Widget build(BuildContext context) {
    return CustomPaint(painter: _ChartGlyphPainter());
  }
}

class _MetricGlyph extends StatelessWidget {
  const _MetricGlyph();

  @override
  Widget build(BuildContext context) {
    return CustomPaint(painter: _MetricGlyphPainter());
  }
}

class _SetupFeatureCard extends StatelessWidget {
  const _SetupFeatureCard({
    required this.icon,
    required this.label,
    this.emphasized = false,
  });

  final IconData icon;
  final String label;
  final bool emphasized;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: emphasized ? 88 : 80,
      height: emphasized ? 96 : 84,
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppColors.lineSoft),
        boxShadow: const [
          BoxShadow(
            color: Color(0x0F000000),
            blurRadius: 18,
            offset: Offset(0, 8),
          ),
        ],
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, size: emphasized ? 32 : 28, color: AppColors.blue),
          const SizedBox(height: 8),
          Text(label, style: AppTextStyles.listTitle),
        ],
      ),
    );
  }
}

class _AuthLogoPainter extends CustomPainter {
  const _AuthLogoPainter({required this.accent});

  final bool accent;

  @override
  void paint(Canvas canvas, Size size) {
    final blue = Paint()
      ..color = AppColors.blue
      ..style = PaintingStyle.stroke
      ..strokeWidth = size.width * 0.13
      ..strokeCap = StrokeCap.round;
    final dot = Paint()..color = AppColors.blue;
    final green = Paint()..color = AppColors.green;

    canvas.drawArc(
      Rect.fromLTWH(
        size.width * 0.25,
        size.height * 0.32,
        size.width * 0.5,
        size.height * 0.44,
      ),
      0.15,
      2.85,
      false,
      blue,
    );
    canvas.drawCircle(
      Offset(size.width * 0.36, size.height * 0.36),
      size.width * 0.075,
      dot,
    );
    if (accent) {
      canvas.drawCircle(
        Offset(size.width * 0.66, size.height * 0.32),
        size.width * 0.075,
        green,
      );
      canvas.drawRRect(
        RRect.fromRectAndRadius(
          Rect.fromLTWH(
            size.width * 0.58,
            size.height * 0.45,
            size.width * 0.2,
            size.height * 0.08,
          ),
          Radius.circular(size.width * 0.04),
        ),
        green,
      );
    }
  }

  @override
  bool shouldRepaint(covariant _AuthLogoPainter oldDelegate) =>
      oldDelegate.accent != accent;
}

class _OrbitPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final blob = Paint()
      ..color = AppColors.blue.withValues(alpha: 0.08)
      ..style = PaintingStyle.fill;
    final orbit = Paint()
      ..color = Colors.white.withValues(alpha: 0.7)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.6;

    canvas.drawOval(
      Rect.fromCenter(
        center: Offset(size.width * 0.54, size.height * 0.56),
        width: size.width * 0.86,
        height: size.height * 0.72,
      ),
      blob,
    );
    canvas.drawArc(
      Rect.fromCenter(
        center: Offset(size.width * 0.58, size.height * 0.54),
        width: size.width * 1.02,
        height: size.height * 0.92,
      ),
      -0.6,
      4.2,
      false,
      orbit,
    );
  }

  @override
  bool shouldRepaint(covariant _OrbitPainter oldDelegate) => false;
}

class _ChartGlyphPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final blue = Paint()
      ..color = AppColors.blue.withValues(alpha: 0.7)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 3
      ..strokeCap = StrokeCap.round;
    final dot = Paint()..color = Colors.white;
    final points = [
      Offset(size.width * 0.12, size.height * 0.68),
      Offset(size.width * 0.34, size.height * 0.48),
      Offset(size.width * 0.54, size.height * 0.58),
      Offset(size.width * 0.76, size.height * 0.28),
    ];
    final path = Path()..moveTo(points.first.dx, points.first.dy);
    for (final point in points.skip(1)) {
      path.lineTo(point.dx, point.dy);
    }
    canvas.drawPath(path, blue);
    for (final point in points) {
      canvas.drawCircle(point, 4, dot);
      canvas.drawCircle(point, 2, Paint()..color = AppColors.blue);
    }
  }

  @override
  bool shouldRepaint(covariant _ChartGlyphPainter oldDelegate) => false;
}

class _MetricGlyphPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final blue = Paint()..color = AppColors.blue;
    final green = Paint()..color = AppColors.green;
    final gray = Paint()..color = const Color(0xFFC9D3E2);
    canvas.drawArc(
      Rect.fromLTWH(
          0, size.height * 0.08, size.height * 0.58, size.height * 0.58),
      -1.57,
      4.3,
      true,
      blue,
    );
    canvas.drawCircle(
      Offset(size.height * 0.29, size.height * 0.37),
      size.height * 0.16,
      Paint()..color = Colors.white,
    );
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromLTWH(
            size.width * 0.56, size.height * 0.18, size.width * 0.36, 6),
        const Radius.circular(999),
      ),
      gray,
    );
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromLTWH(
            size.width * 0.56, size.height * 0.48, size.width * 0.3, 6),
        const Radius.circular(999),
      ),
      green,
    );
  }

  @override
  bool shouldRepaint(covariant _MetricGlyphPainter oldDelegate) => false;
}

class _SetupBlobPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final blob = Paint()..color = AppColors.blue.withValues(alpha: 0.1);
    final path = Path()
      ..moveTo(size.width * 0.1, size.height * 0.75)
      ..cubicTo(size.width * 0.2, size.height * 0.08, size.width * 0.72,
          -size.height * 0.02, size.width * 0.85, size.height * 0.3)
      ..cubicTo(size.width * 1.02, size.height * 0.72, size.width * 0.56,
          size.height * 1.08, size.width * 0.18, size.height * 0.92)
      ..cubicTo(size.width * 0.04, size.height * 0.86, size.width * 0.04,
          size.height * 0.82, size.width * 0.1, size.height * 0.75)
      ..close();
    canvas.drawPath(path, blob);

    final line = Paint()
      ..color = AppColors.blue.withValues(alpha: 0.45)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2;
    final curve = Path()
      ..moveTo(size.width * 0.24, size.height * 0.62)
      ..cubicTo(size.width * 0.36, size.height * 0.36, size.width * 0.48,
          size.height * 0.38, size.width * 0.58, size.height * 0.55)
      ..cubicTo(size.width * 0.68, size.height * 0.72, size.width * 0.78,
          size.height * 0.56, size.width * 0.88, size.height * 0.42);
    canvas.drawPath(curve, line);
  }

  @override
  bool shouldRepaint(covariant _SetupBlobPainter oldDelegate) => false;
}
