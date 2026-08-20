import 'package:flutter/material.dart';

import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';

enum IconTone { blue, cyan, teal, green, amber }

class AppIconTile extends StatelessWidget {
  const AppIconTile({
    super.key,
    required this.icon,
    required this.label,
    this.tone = IconTone.blue,
  });

  final IconData icon;
  final String label;
  final IconTone tone;

  Color get foreground => switch (tone) {
        IconTone.blue => AppColors.blue,
        IconTone.cyan => AppColors.cyan,
        IconTone.teal => AppColors.teal,
        IconTone.green => AppColors.green,
        IconTone.amber => AppColors.amber,
      };

  Color get background => switch (tone) {
        IconTone.blue => AppColors.blueSoft,
        IconTone.cyan => AppColors.cyanSoft,
        IconTone.teal => AppColors.tealSoft,
        IconTone.green => AppColors.greenSoft,
        IconTone.amber => AppColors.amberSoft,
      };

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 76,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 56,
            height: 56,
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: AppColors.lineSoft),
              boxShadow: const [
                BoxShadow(
                  color: Color(0x08000000),
                  blurRadius: 12,
                  offset: Offset(0, 4),
                ),
              ],
            ),
            child: Center(
              child: Container(
                width: 32,
                height: 32,
                decoration: BoxDecoration(
                  color: background,
                  borderRadius: BorderRadius.circular(9),
                ),
                child: Icon(icon, size: 20, color: foreground),
              ),
            ),
          ),
          const SizedBox(height: 8),
          Text(
            label,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            textAlign: TextAlign.center,
            style: AppTextStyles.small.copyWith(
              color: AppColors.ink,
              fontSize: 11,
              fontWeight: FontWeight.w800,
            ),
          ),
        ],
      ),
    );
  }
}
