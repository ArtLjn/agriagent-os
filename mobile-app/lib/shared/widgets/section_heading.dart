import 'package:flutter/material.dart';

import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';

class SectionHeading extends StatelessWidget {
  const SectionHeading({super.key, required this.title, this.action});

  final String title;
  final String? action;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(title, style: AppTextStyles.sectionTitle),
        if (action != null)
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
            decoration: BoxDecoration(
              color: AppColors.blueSoft,
              borderRadius: BorderRadius.circular(999),
            ),
            child: Text(
              action!,
              style: const TextStyle(
                color: AppColors.blue,
                fontSize: 11,
                fontWeight: FontWeight.w800,
                letterSpacing: 0,
              ),
            ),
          ),
      ],
    );
  }
}
