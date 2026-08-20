import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';
import 'auth_widgets.dart';

class RegisterScreen extends StatefulWidget {
  const RegisterScreen({
    super.key,
    required this.onRegister,
    required this.onLogin,
  });

  final Future<void> Function({
    required String phone,
    required String password,
    required String nickname,
  }) onRegister;
  final VoidCallback onLogin;

  @override
  State<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends State<RegisterScreen> {
  final phoneController = TextEditingController();
  final passwordController = TextEditingController();
  final nicknameController = TextEditingController();
  var isSubmitting = false;
  String? errorMessage;

  @override
  void dispose() {
    phoneController.dispose();
    passwordController.dispose();
    nicknameController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (isSubmitting) return;
    setState(() {
      isSubmitting = true;
      errorMessage = null;
    });
    try {
      await widget.onRegister(
        phone: phoneController.text.trim(),
        password: passwordController.text,
        nickname: nicknameController.text.trim().isEmpty
            ? '农友'
            : nicknameController.text.trim(),
      );
    } catch (_) {
      if (!mounted) return;
      setState(() => errorMessage = '注册失败，请检查信息或稍后重试');
    } finally {
      if (mounted) setState(() => isSubmitting = false);
    }
  }

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
            AuthInputField(
              label: '手机号',
              placeholder: '请输入手机号',
              icon: LucideIcons.smartphone,
              controller: phoneController,
            ),
            const SizedBox(height: 20),
            AuthInputField(
              label: '设置密码',
              placeholder: '请设置6-16位密码',
              icon: LucideIcons.lockKeyhole,
              controller: passwordController,
              obscureText: true,
              trailing: Icon(
                LucideIcons.eyeOff,
                size: 20,
                color: AppColors.subtle,
              ),
            ),
            const SizedBox(height: 20),
            AuthInputField(
              label: '昵称',
              placeholder: '请输入昵称',
              icon: LucideIcons.userRound,
              controller: nicknameController,
            ),
            const SizedBox(height: 24),
            if (errorMessage != null) ...[
              Text(
                errorMessage!,
                textAlign: TextAlign.center,
                style: AppTextStyles.body.copyWith(color: AppColors.red),
              ),
              const SizedBox(height: 12),
            ],
            AuthPrimaryButton(
              label: isSubmitting ? '注册中' : '注册并进入',
              onTap: _submit,
            ),
            const SizedBox(height: 18),
            AuthTextLink(
              prefix: '已有账号？',
              action: '去登录',
              onTap: widget.onLogin,
            ),
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
