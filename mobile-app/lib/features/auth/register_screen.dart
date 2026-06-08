import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';
import 'auth_widgets.dart';

class RegisterScreen extends StatelessWidget {
  const RegisterScreen({
    super.key,
    required this.onRegister,
    required this.onLogin,
  });

  final VoidCallback onRegister;
  final VoidCallback onLogin;

  @override
  Widget build(BuildContext context) {
    return AuthPage(
      children: [
        const AuthBrandHeader(
          title: '创建账号',
          subtitle: '先建账号，记录可以慢慢补',
          compact: true,
        ),
        AuthSurfaceCard(
          children: [
            const AuthInputField(
              label: '手机号',
              placeholder: '请输入手机号',
              icon: LucideIcons.smartphone,
            ),
            const SizedBox(height: 20),
            const AuthInputField(
              label: '设置密码',
              placeholder: '请设置6-16位密码',
              icon: LucideIcons.lockKeyhole,
              trailing: Icon(
                LucideIcons.eyeOff,
                size: 20,
                color: AppColors.subtle,
              ),
            ),
            const SizedBox(height: 20),
            const AuthInputField(
              label: '昵称',
              placeholder: '请输入昵称',
              icon: LucideIcons.userRound,
            ),
            const SizedBox(height: 24),
            AuthPrimaryButton(label: '注册并进入', onTap: onRegister),
            const SizedBox(height: 18),
            AuthTextLink(prefix: '已有账号？', action: '去登录', onTap: onLogin),
            const SizedBox(height: 6),
            Text(
              'MVP功能全部免费',
              textAlign: TextAlign.center,
              style: AppTextStyles.body.copyWith(color: AppColors.subtle),
            ),
          ],
        ),
        const SizedBox(height: 26),
        const Row(
          children: [
            Expanded(
              child: CapabilityChip(
                label: '手动记录',
                icon: LucideIcons.pencil,
                color: AppColors.blue,
                background: AppColors.blueSoft,
              ),
            ),
            SizedBox(width: 10),
            Expanded(
              child: CapabilityChip(
                label: 'AI帮填',
                icon: LucideIcons.sparkles,
                color: AppColors.greenDark,
                background: AppColors.greenSoft,
              ),
            ),
            SizedBox(width: 10),
            Expanded(
              child: CapabilityChip(
                label: '账本提醒',
                icon: LucideIcons.bell,
                color: AppColors.amber,
                background: AppColors.amberSoft,
              ),
            ),
          ],
        ),
      ],
    );
  }
}
