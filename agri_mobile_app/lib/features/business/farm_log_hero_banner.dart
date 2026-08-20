import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';
import 'business_ui.dart';

class FarmLogHeroBanner extends StatelessWidget {
  const FarmLogHeroBanner({
    super.key,
    required this.title,
    required this.subtitle,
    required this.backgroundAsset,
  });

  final String title;
  final String subtitle;
  final String backgroundAsset;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 120,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: Colors.white),
        boxShadow: const [
          BoxShadow(
            color: Color(0x0A101828),
            blurRadius: 18,
            offset: Offset(0, 8),
          ),
        ],
      ),
      clipBehavior: Clip.antiAlias,
      child: Stack(
        fit: StackFit.expand,
        children: [
          Image.asset(
            backgroundAsset,
            fit: BoxFit.cover,
            alignment: Alignment.topCenter,
            errorBuilder: (_, __, ___) => const DecoratedBox(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [Color(0xFFEAF4FF), Color(0xFFFFF8E8)],
                ),
              ),
            ),
          ),
          DecoratedBox(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.centerLeft,
                end: Alignment.centerRight,
                colors: [
                  Colors.white.withValues(alpha: 0.94),
                  Colors.white.withValues(alpha: 0.74),
                  Colors.white.withValues(alpha: 0.22),
                  Colors.white.withValues(alpha: 0.04),
                ],
                stops: const [0, 0.46, 0.74, 1],
              ),
            ),
          ),
          Positioned(
            right: 18,
            bottom: 14,
            child: Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: businessBlue.withValues(alpha: 0.92),
                boxShadow: [
                  BoxShadow(
                    color: businessBlue.withValues(alpha: 0.18),
                    blurRadius: 18,
                    offset: const Offset(0, 8),
                  ),
                ],
              ),
              child: const Icon(
                LucideIcons.clipboardPenLine,
                color: Colors.white,
                size: 23,
              ),
            ),
          ),
          Positioned(
            left: 18,
            right: 96,
            top: 0,
            bottom: 0,
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppTextStyles.title.copyWith(
                    color: AppColors.ink,
                    fontSize: 24,
                    height: 30 / 24,
                    fontWeight: FontWeight.w900,
                  ),
                ),
                const SizedBox(height: 7),
                Text(
                  subtitle,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: AppTextStyles.body.copyWith(
                    color: AppColors.ink2.withValues(alpha: 0.72),
                    fontSize: 15,
                    height: 22 / 15,
                    fontWeight: FontWeight.w600,
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
