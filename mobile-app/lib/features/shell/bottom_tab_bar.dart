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
        width: 340,
        height: 58,
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
        decoration: BoxDecoration(
          color: Colors.white.withValues(alpha: 0.96),
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: AppColors.lineSoft),
          boxShadow: const [
            BoxShadow(
              color: Color(0x14092642),
              blurRadius: 26,
              offset: Offset(0, 12),
            ),
          ],
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: List.generate(_tabs.length, (index) {
            final spec = _tabs[index];
            final selected = selectedIndex == index;
            return NormalTab(
              label: spec.label,
              icon: spec.icon,
              selected: selected,
              assistant: index == 2,
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
    this.assistant = false,
    required this.onTap,
  });

  final String label;
  final IconData icon;
  final bool selected;
  final bool assistant;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final color = selected ? AppColors.blue : AppColors.subtle;
    return PressableScale(
      onTap: onTap,
      child: AnimatedContainer(
        width: 58,
        height: 48,
        duration: const Duration(milliseconds: 160),
        curve: Curves.easeOutCubic,
        decoration: BoxDecoration(
          color: selected ? AppColors.blueSoft : Colors.transparent,
          borderRadius: BorderRadius.circular(14),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              icon,
              size: assistant ? 20 : (selected ? 20 : 19),
              color: color,
              weight: selected ? 700 : 400,
            ),
            const SizedBox(height: 3),
            Text(
              label,
              style: AppTextStyles.tab.copyWith(
                color: color,
                fontWeight: selected ? FontWeight.w900 : FontWeight.w600,
              ),
            ),
          ],
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
