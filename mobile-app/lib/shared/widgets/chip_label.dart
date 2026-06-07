import 'package:flutter/material.dart';

import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';

class ChipLabel extends StatelessWidget {
  const ChipLabel({
    super.key,
    required this.text,
    required this.background,
    required this.foreground,
  });

  const ChipLabel.blue(this.text, {super.key})
      : background = AppColors.blueSoft,
        foreground = AppColors.blue;

  const ChipLabel.teal(this.text, {super.key})
      : background = AppColors.tealSoft,
        foreground = AppColors.teal;

  const ChipLabel.neutral(this.text, {super.key})
      : background = AppColors.surface2,
        foreground = AppColors.muted;

  final String text;
  final Color background;
  final Color foreground;

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(minHeight: 26),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        text,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        style: AppTextStyles.small.copyWith(
          color: foreground,
          fontWeight: FontWeight.w800,
        ),
      ),
    );
  }
}
