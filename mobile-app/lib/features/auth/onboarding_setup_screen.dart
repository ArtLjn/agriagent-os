import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';
import 'auth_widgets.dart';

class OnboardingSetupScreen extends StatelessWidget {
  const OnboardingSetupScreen({
    super.key,
    required this.onStart,
    required this.onSkip,
  });

  final VoidCallback onStart;
  final VoidCallback onSkip;

  @override
  Widget build(BuildContext context) {
    return AuthPage(
      bottomPadding: 22,
      children: [
        const SetupHero(),
        AuthSurfaceCard(
          padding: const EdgeInsets.all(18),
          children: [
            const AuthInputField(
              label: '农场名称',
              placeholder: '请输入农场名称',
              icon: LucideIcons.building2,
              height: 48,
              labelGap: 8,
              labelFontSize: 14,
            ),
            const SizedBox(height: 14),
            const AuthInputField(
              label: '所在城市',
              placeholder: '请选择所在城市',
              icon: LucideIcons.mapPin,
              height: 48,
              labelGap: 8,
              labelFontSize: 14,
              trailing: Icon(
                LucideIcons.chevronRight,
                size: 22,
                color: AppColors.subtle,
              ),
            ),
            const SizedBox(height: 14),
            const AuthInputField(
              label: '默认天气城市',
              placeholder: '请选择默认天气城市',
              icon: LucideIcons.cloud,
              height: 48,
              labelGap: 8,
              labelFontSize: 14,
              trailing: Icon(
                LucideIcons.chevronRight,
                size: 22,
                color: AppColors.subtle,
              ),
            ),
            const SizedBox(height: 14),
            const AuthInputField(
              label: '身份',
              placeholder: '农场负责人',
              icon: LucideIcons.circleUserRound,
              height: 48,
              labelGap: 8,
              labelFontSize: 14,
              trailing: Icon(
                LucideIcons.chevronDown,
                size: 22,
                color: AppColors.subtle,
              ),
            ),
            const SizedBox(height: 18),
            AuthPrimaryButton(label: '开始使用', onTap: onStart),
            const SizedBox(height: 10),
            GestureDetector(
              behavior: HitTestBehavior.opaque,
              onTap: onSkip,
              child: Center(
                child: Padding(
                  padding: const EdgeInsets.symmetric(vertical: 6),
                  child: Text(
                    '稍后再说',
                    style: AppTextStyles.body.copyWith(
                      color: AppColors.subtle,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
        const DataNotice(text: '可稍后在我的中修改', topPadding: 14),
      ],
    );
  }
}
