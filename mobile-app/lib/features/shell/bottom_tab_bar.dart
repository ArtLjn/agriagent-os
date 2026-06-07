import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../shared/widgets/status_header.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';

class AppBottomTabBar extends StatelessWidget {
  const AppBottomTabBar({
    super.key,
    required this.selectedIndex,
    required this.onChanged,
  });

  final int selectedIndex;
  final ValueChanged<int> onChanged;

  static const _tabs = [
    _TabSpec('首页', LucideIcons.layoutDashboard),
    _TabSpec('工作台', LucideIcons.briefcaseBusiness),
    _TabSpec('芽芽', LucideIcons.bot),
    _TabSpec('账单', LucideIcons.receipt),
    _TabSpec('我的', LucideIcons.user),
  ];

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Container(
        width: 335,
        height: 68,
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 9),
        decoration: BoxDecoration(
          color: Colors.white.withValues(alpha: 0.94),
          borderRadius: BorderRadius.circular(26),
          border: Border.all(color: Colors.white.withValues(alpha: 0.82)),
          boxShadow: const [
            BoxShadow(
              color: Color(0x1A24405F),
              blurRadius: 34,
              offset: Offset(0, 16),
            ),
          ],
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: List.generate(_tabs.length, (index) {
            final spec = _tabs[index];
            final selected = selectedIndex == index;
            if (index == 2) {
              return YayaTab(
                label: spec.label,
                icon: spec.icon,
                selected: selected,
                onTap: () => onChanged(index),
              );
            }
            return NormalTab(
              label: spec.label,
              icon: spec.icon,
              selected: selected,
              onTap: () => onChanged(index),
            );
          }),
        ),
      ),
    );
  }
}

class NormalTab extends StatelessWidget {
  const NormalTab({
    super.key,
    required this.label,
    required this.icon,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final IconData icon;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final color = selected ? AppColors.blue : AppColors.muted;
    return PressableScale(
      onTap: onTap,
      child: AnimatedContainer(
        width: 56,
        height: 50,
        duration: const Duration(milliseconds: 180),
        curve: Curves.easeOutCubic,
        decoration: BoxDecoration(
          color: selected ? AppColors.blueSoft : Colors.transparent,
          borderRadius: BorderRadius.circular(18),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, size: 18, color: color),
            const SizedBox(height: 4),
            Text(label, style: AppTextStyles.tab.copyWith(color: color)),
          ],
        ),
      ),
    );
  }
}

class YayaTab extends StatelessWidget {
  const YayaTab({
    super.key,
    required this.label,
    required this.icon,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final IconData icon;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Transform.translate(
      offset: const Offset(0, -10),
      child: PressableScale(
        onTap: onTap,
        child: SizedBox(
          width: 55,
          height: 50,
          child: Stack(
            clipBehavior: Clip.none,
            alignment: Alignment.topCenter,
            children: [
              Positioned(
                top: -2,
                child: AnimatedContainer(
                  width: 50,
                  height: 50,
                  duration: const Duration(milliseconds: 220),
                  curve: Curves.easeOutCubic,
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(18),
                    border: Border.all(color: Colors.white, width: 3),
                    gradient: LinearGradient(
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                      colors: selected
                          ? const [AppColors.blue, AppColors.cyan]
                          : const [
                              Colors.white,
                              Color(0xFFEAF2FF),
                              Color(0xFFDFE9FF),
                            ],
                    ),
                    boxShadow: const [
                      BoxShadow(
                        color: Color(0x334078FF),
                        blurRadius: 22,
                        offset: Offset(0, 10),
                      ),
                    ],
                  ),
                  child: Icon(
                    icon,
                    size: 22,
                    color: selected ? Colors.white : AppColors.blue,
                  ),
                ),
              ),
              Positioned(
                bottom: 0,
                child: Text(
                  label,
                  style: AppTextStyles.tab.copyWith(color: AppColors.blue),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _TabSpec {
  const _TabSpec(this.label, this.icon);

  final String label;
  final IconData icon;
}
