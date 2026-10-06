import 'package:flutter/material.dart';

import '../app_identity.dart';
import '../assets/app_assets.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';

class ReferencePage extends StatelessWidget {
  const ReferencePage({
    super.key,
    required this.children,
    this.headerTrailing,
    this.showHeaderLogo = true,
    this.bottomPadding = 32,
    this.overlay,
    this.title,
    this.subtitle,
  });

  final List<Widget> children;
  final Widget? headerTrailing;
  final bool showHeaderLogo;
  final double bottomPadding;
  final Widget? overlay;
  final String? title;
  final String? subtitle;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: SafeArea(
        child: Stack(
          children: [
            SingleChildScrollView(
              padding: EdgeInsets.fromLTRB(24, 16, 24, bottomPadding),
              child: Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 430),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      ReferenceHeader(
                        trailing: headerTrailing,
                        showLogo: showHeaderLogo,
                        title: title,
                        subtitle: subtitle,
                      ),
                      ...children,
                    ],
                  ),
                ),
              ),
            ),
            if (overlay != null)
              Positioned(
                left: 20,
                right: 20,
                bottom: 92,
                child: overlay!,
              ),
          ],
        ),
      ),
    );
  }
}

class ReferenceHeader extends StatelessWidget {
  const ReferenceHeader(
      {super.key,
      this.trailing,
      this.showLogo = true,
      this.title,
      this.subtitle});

  final Widget? trailing;
  final bool showLogo;
  final String? title;
  final String? subtitle;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        if (showLogo) ...[
          const FarmBrandMark(size: 40),
          const SizedBox(width: 12),
        ],
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title ?? AppIdentity.displayName,
                  style: AppTextStyles.title),
              const SizedBox(height: 4),
              Text(subtitle ?? '你的农场经营助手', style: AppTextStyles.small),
            ],
          ),
        ),
        if (trailing != null) trailing!,
      ],
    );
  }
}

class FarmBrandLockup extends StatelessWidget {
  const FarmBrandLockup({super.key, this.height = 42});

  final double height;

  @override
  Widget build(BuildContext context) {
    final width = height * 3.5;
    return Align(
      alignment: Alignment.centerLeft,
      child: Semantics(
        label: AppIdentity.displayName,
        image: true,
        child: ExcludeSemantics(
          child: Image.asset(
            AppAssets.brandLockup,
            width: width,
            height: height,
            fit: BoxFit.contain,
            errorBuilder: (_, __, ___) => Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                FarmBrandMark(size: height),
                const SizedBox(width: 10),
                const Text(
                  AppIdentity.displayName,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppTextStyles.title,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class FarmBrandMark extends StatelessWidget {
  const FarmBrandMark({super.key, this.size = 38});

  final double size;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: size,
      height: size,
      child: Image.asset(
        AppAssets.brandLogo,
        fit: BoxFit.contain,
        errorBuilder: (_, __, ___) => CustomPaint(painter: _FarmBrandPainter()),
      ),
    );
  }
}

class _FarmBrandPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width;
    final h = size.height;
    final green = Paint()..color = AppColors.green;
    final greenDark = Paint()..color = const Color(0xFF0AAE73);
    final blue = Paint()..color = AppColors.blue;
    final blueDark = Paint()..color = AppColors.blueDark;
    final sun = Paint()..color = AppColors.amber;

    canvas.drawCircle(Offset(w * 0.78, h * 0.17), w * 0.14, sun);

    final leftLeaf = Path()
      ..moveTo(w * 0.10, h * 0.32)
      ..quadraticBezierTo(w * 0.36, h * 0.12, w * 0.52, h * 0.42)
      ..quadraticBezierTo(w * 0.28, h * 0.48, w * 0.10, h * 0.32)
      ..close();
    canvas.drawPath(leftLeaf, green);

    final rightLeaf = Path()
      ..moveTo(w * 0.54, h * 0.42)
      ..quadraticBezierTo(w * 0.68, h * 0.15, w * 0.94, h * 0.28)
      ..quadraticBezierTo(w * 0.78, h * 0.52, w * 0.54, h * 0.42)
      ..close();
    canvas.drawPath(rightLeaf, greenDark);

    final blueWave = Path()
      ..moveTo(w * 0.08, h * 0.68)
      ..quadraticBezierTo(w * 0.36, h * 0.48, w * 0.62, h * 0.60)
      ..quadraticBezierTo(w * 0.40, h * 0.73, w * 0.10, h * 0.82)
      ..close();
    canvas.drawPath(blueWave, blue);

    final darkWave = Path()
      ..moveTo(w * 0.34, h * 0.84)
      ..quadraticBezierTo(w * 0.62, h * 0.58, w * 0.94, h * 0.58)
      ..quadraticBezierTo(w * 0.74, h * 0.84, w * 0.36, h * 0.92)
      ..close();
    canvas.drawPath(darkWave, blueDark);
  }

  @override
  bool shouldRepaint(covariant _FarmBrandPainter oldDelegate) => false;
}

class IconBadge extends StatelessWidget {
  const IconBadge({
    super.key,
    required this.icon,
    required this.color,
    required this.background,
    this.size = 42,
    this.iconSize = 20,
  });

  final IconData icon;
  final Color color;
  final Color background;
  final double size;
  final double iconSize;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(size <= 36 ? 10 : 12),
      ),
      child: Icon(icon, size: iconSize, color: color),
    );
  }
}

class StatusPill extends StatelessWidget {
  const StatusPill({
    super.key,
    required this.text,
    required this.color,
    required this.background,
  });

  final String text;
  final Color color;
  final Color background;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        text,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        style: AppTextStyles.small.copyWith(
          color: color,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}
