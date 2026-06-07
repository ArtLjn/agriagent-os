import 'package:flutter/material.dart';

import '../../theme/app_colors.dart';

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
      width: 70,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 48,
            height: 48,
            decoration: BoxDecoration(
              color: background,
              borderRadius: BorderRadius.circular(18),
              border: Border.all(color: Colors.white.withValues(alpha: 0.8)),
            ),
            child: Icon(icon, size: 22, color: foreground),
          ),
          const SizedBox(height: 7),
          Text(
            label,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            textAlign: TextAlign.center,
            style: const TextStyle(
              color: AppColors.ink,
              fontSize: 11,
              height: 15 / 11,
              fontWeight: FontWeight.w800,
              letterSpacing: 0,
            ),
          ),
        ],
      ),
    );
  }
}
