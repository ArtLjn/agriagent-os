import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../theme/app_colors.dart';
import '../../theme/app_theme.dart';
import '../../theme/app_text_styles.dart';

class AppBottomTabBar extends StatelessWidget {
  const AppBottomTabBar(
      {super.key, required this.selectedIndex, required this.onChanged});

  final int selectedIndex;
  final ValueChanged<int> onChanged;

  static const _tabs = [
    _TabSpec('首页', LucideIcons.house),
    _TabSpec('记录', LucideIcons.clipboardList),
    _TabSpec('芽芽', LucideIcons.bot),
    _TabSpec('账本', LucideIcons.receiptJapaneseYen),
    _TabSpec('我的', LucideIcons.user),
  ];

  @override
  Widget build(BuildContext context) {
    return Material(
      color: AppColors.surface,
      child: DecoratedBox(
        decoration: const BoxDecoration(
            border: Border(top: BorderSide(color: AppColors.lineSoft))),
        child: SafeArea(
          top: false,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
            child: LayoutBuilder(builder: (context, constraints) {
              final duration = MediaQuery.disableAnimationsOf(context)
                  ? Duration.zero
                  : AppMotion.tabDuration;
              final itemWidth = constraints.maxWidth / _tabs.length;
              return Stack(children: [
                AnimatedPositioned(
                  key: const ValueKey('tab-active-indicator'),
                  duration: duration,
                  curve: AppMotion.curve,
                  left: itemWidth * selectedIndex + (itemWidth - 54) / 2,
                  top: 4,
                  width: 54,
                  height: 34,
                  child: IgnorePointer(
                      child: DecoratedBox(
                          decoration: BoxDecoration(
                              color: AppColors.blueSoft,
                              borderRadius: BorderRadius.circular(12)))),
                ),
                Row(
                    children: List.generate(_tabs.length, (index) {
                  final selected = selectedIndex == index;
                  return Expanded(
                      child: Semantics(
                    selected: selected,
                    button: true,
                    label: _tabs[index].label,
                    child: InkWell(
                      onTap: () => onChanged(index),
                      borderRadius: BorderRadius.circular(16),
                      child: ExcludeSemantics(
                          child: Padding(
                        padding: const EdgeInsets.symmetric(vertical: 4),
                        child: TweenAnimationBuilder<Color?>(
                          tween: ColorTween(
                              end: selected
                                  ? AppColors.blue
                                  : AppColors.tabMuted),
                          duration: duration,
                          curve: AppMotion.curve,
                          builder: (context, color, _) =>
                              Column(mainAxisSize: MainAxisSize.min, children: [
                            AnimatedScale(
                              scale: selected ? 1.06 : 1,
                              duration: duration,
                              curve: AppMotion.curve,
                              child: Padding(
                                  padding: const EdgeInsets.symmetric(
                                      horizontal: 16, vertical: 6),
                                  child: Icon(_tabs[index].icon,
                                      size: 22, color: color)),
                            ),
                            const SizedBox(height: 4),
                            Text(_tabs[index].label,
                                style:
                                    AppTextStyles.tab.copyWith(color: color)),
                          ]),
                        ),
                      )),
                    ),
                  ));
                })),
              ]);
            }),
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
