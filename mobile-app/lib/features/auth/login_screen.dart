import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';
import 'auth_widgets.dart';

class LoginScreen extends StatelessWidget {
  const LoginScreen({
    super.key,
    required this.onLogin,
    required this.onRegister,
  });

  final VoidCallback onLogin;
  final VoidCallback onRegister;

  @override
  Widget build(BuildContext context) {
    return AuthPage(
      children: [
        const AuthBrandHeader(
          title: '农场管家',
          subtitle: '把农场记录得更轻松',
        ),
        const SizedBox(height: 14),
        AuthSurfaceCard(
          children: [
            const AuthInputField(
              label: '手机号',
              placeholder: '请输入手机号',
              icon: LucideIcons.smartphone,
            ),
            const SizedBox(height: 24),
            const AuthInputField(
              label: '密码',
              placeholder: '请输入密码',
              icon: LucideIcons.lockKeyhole,
              trailing: Icon(
                LucideIcons.eyeOff,
                size: 20,
                color: AppColors.subtle,
              ),
            ),
            const SizedBox(height: 10),
            Align(
              alignment: Alignment.centerRight,
              child: Text(
                '忘记密码',
                style: AppTextStyles.body.copyWith(
                  color: AppColors.blue,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ),
            const SizedBox(height: 28),
            AuthPrimaryButton(label: '登录', onTap: onLogin),
            const SizedBox(height: 22),
            AuthTextLink(
              prefix: '还没有账号？',
              action: '去注册',
              onTap: onRegister,
            ),
          ],
        ),
        const DataNotice(text: '数据仅用于你的农场记录', topPadding: 28),
      ],
    );
  }
}
