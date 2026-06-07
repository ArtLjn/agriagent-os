import 'package:flutter/material.dart';

import '../../theme/app_colors.dart';

class CardPanel extends StatelessWidget {
  const CardPanel({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(16),
    this.background = AppColors.surface,
    this.borderColor = AppColors.line,
    this.gradient,
    this.shadow = true,
    this.radius = 22,
  });

  final Widget child;
  final EdgeInsets padding;
  final Color background;
  final Color borderColor;
  final Gradient? gradient;
  final bool shadow;
  final double radius;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: gradient == null ? background : null,
        gradient: gradient,
        borderRadius: BorderRadius.circular(radius),
        border: Border.all(color: borderColor),
        boxShadow: shadow
            ? const [
                BoxShadow(
                  color: Color(0x0A4078FF),
                  blurRadius: 34,
                  offset: Offset(0, 18),
                ),
                BoxShadow(
                  color: Color(0x08FFFFFF),
                  blurRadius: 1,
                  offset: Offset(0, 1),
                ),
              ]
            : null,
      ),
      child: Padding(padding: padding, child: child),
    );
  }
}
