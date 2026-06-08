import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../shared/widgets/card_panel.dart';
import '../../shared/widgets/reference_page.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';

part 'yaya_panel_widgets.dart';
part 'yaya_robot_widgets.dart';

class YayaScreen extends StatelessWidget {
  const YayaScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Stack(
        fit: StackFit.expand,
        children: [
          Positioned.fill(
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(20, 10, 20, 148),
              child: Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 430),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: const [
                      _YayaHeader(),
                      SizedBox(height: 12),
                      _YayaHero(),
                      SizedBox(height: 12),
                      _BriefCard(),
                      SizedBox(height: 12),
                      _PromptQuestion(
                        icon: LucideIcons.sun,
                        title: '今天适合干什么',
                      ),
                      SizedBox(height: 10),
                      _PromptQuestion(
                        icon: LucideIcons.chartNoAxesColumnIncreasing,
                        title: '本月成本怎么看',
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
          Positioned(
            left: 20,
            right: 20,
            bottom: 84,
            child: Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 430),
                child: const Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    _ModeChips(),
                    SizedBox(height: 10),
                    _YayaComposer(),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _YayaHeader extends StatelessWidget {
  const _YayaHeader();

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 48,
      child: Row(
        children: [
          const HeaderIconButton(icon: LucideIcons.menu),
          const Spacer(),
          const FarmBrandMark(size: 30),
          const SizedBox(width: 8),
          Text(
            '农场管家',
            style: AppTextStyles.title.copyWith(fontSize: 19),
          ),
          const Spacer(),
          const HeaderIconButton(icon: LucideIcons.volume2),
          const SizedBox(width: 2),
          const HeaderIconButton(icon: LucideIcons.plus),
        ],
      ),
    );
  }
}

class _YayaHero extends StatelessWidget {
  const _YayaHero();

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 104,
      child: Row(
        children: [
          const SizedBox(
            width: 112,
            child: Center(child: _RobotAvatar(size: 90)),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text.rich(
                  TextSpan(
                    text: '周末愉快，我是',
                    children: [
                      TextSpan(
                        text: '芽芽',
                        style: AppTextStyles.title.copyWith(
                          color: AppColors.blue,
                          fontSize: 23,
                        ),
                      ),
                    ],
                  ),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: AppTextStyles.title.copyWith(fontSize: 23),
                ),
                const SizedBox(height: 6),
                Row(
                  children: [
                    Flexible(
                      child: Text(
                        '点击查看你的今日简报',
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: AppTextStyles.body.copyWith(
                          color: AppColors.muted,
                          fontSize: 14,
                        ),
                      ),
                    ),
                    const SizedBox(width: 4),
                    const Icon(
                      LucideIcons.chevronRight,
                      size: 20,
                      color: AppColors.subtle,
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
