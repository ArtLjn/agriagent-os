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
  });

  final Widget child;
  final EdgeInsets padding;
  final Color background;
  final Color borderColor;
  final Gradient? gradient;
  final bool shadow;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: gradient == null ? background : null,
        gradient: gradient,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: borderColor),
        boxShadow: shadow
            ? const [
                BoxShadow(
                  color: Color(0x0D101828),
                  blurRadius: 24,
                  offset: Offset(0, 10),
                ),
              ]
            : null,
      ),
      child: Padding(padding: padding, child: child),
    );
  }
}
