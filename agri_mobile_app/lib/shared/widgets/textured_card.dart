import 'package:flutter/material.dart';

import '../../theme/app_colors.dart';

class TexturedCard extends StatelessWidget {
  const TexturedCard(
      {super.key,
      required this.child,
      this.padding = const EdgeInsets.all(20),
      this.radius = 24,
      this.accent});

  final Widget child;
  final EdgeInsets padding;
  final double radius;
  final Color? accent;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: padding,
      decoration: BoxDecoration(
        color: accent == null
            ? AppColors.surface
            : accent!.withValues(alpha: 0.05),
        borderRadius: BorderRadius.circular(radius),
        border: Border.all(
            color: accent == null
                ? AppColors.lineSoft
                : accent!.withValues(alpha: 0.08)),
      ),
      child: child,
    );
  }
}

class GradientIconTile extends StatelessWidget {
  const GradientIconTile(
      {super.key,
      required this.icon,
      required this.accent,
      this.size = 46,
      this.iconSize = 22,
      this.borderRadius = 14});

  final IconData icon;
  final Color accent;
  final double size;
  final double iconSize;
  final double borderRadius;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: accent.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(borderRadius),
      ),
      child: Icon(icon, size: iconSize, color: accent),
    );
  }
}
