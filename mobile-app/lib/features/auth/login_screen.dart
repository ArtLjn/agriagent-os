import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../shared/app_identity.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';
import 'auth_widgets.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({
    super.key,
    required this.onLogin,
    required this.onRegister,
  });

  final Future<void> Function({
    required String phone,
    required String password,
  }) onLogin;
  final VoidCallback onRegister;

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final phoneController = TextEditingController(text: '19083106293');
  final passwordController = TextEditingController(text: 'admin123');
  var isSubmitting = false;
  String? errorMessage;

  @override
  void dispose() {
    phoneController.dispose();
    passwordController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (isSubmitting) return;
    setState(() {
      isSubmitting = true;
      errorMessage = null;
    });
    try {
      await widget.onLogin(
        phone: phoneController.text.trim(),
        password: passwordController.text,
      );
    } catch (_) {
      if (!mounted) return;
      setState(() => errorMessage = '登录失败，请检查账号或稍后重试');
    } finally {
      if (mounted) setState(() => isSubmitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return AuthPage(
      children: [
        const AuthBrandHeader(
          title: AppIdentity.displayName,
          subtitle: '把农场记录得更轻松',
        ),
        const SizedBox(height: 14),
        AuthSurfaceCard(
          children: [
            AuthInputField(
              label: '手机号',
              placeholder: '请输入手机号',
              icon: LucideIcons.smartphone,
              controller: phoneController,
            ),
            const SizedBox(height: 24),
            AuthInputField(
              label: '密码',
              placeholder: '请输入密码',
              icon: LucideIcons.lockKeyhole,
              controller: passwordController,
              obscureText: true,
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
            if (errorMessage != null) ...[
              Text(
                errorMessage!,
                textAlign: TextAlign.center,
                style: AppTextStyles.body.copyWith(color: AppColors.red),
              ),
              const SizedBox(height: 12),
            ],
            AuthPrimaryButton(
              label: isSubmitting ? '登录中' : '登录',
              onTap: _submit,
            ),
            const SizedBox(height: 22),
            AuthTextLink(
              prefix: '还没有账号？',
              action: '去注册',
              onTap: widget.onRegister,
            ),
          ],
        ),
        const DataNotice(text: '数据仅用于你的农场记录', topPadding: 28),
      ],
    );
  }
}
