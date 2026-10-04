import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';
import '../../data/api/api_client.dart';
import 'auth_widgets.dart';
import 'auth_entry_page.dart';

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
    // 键盘和按钮共用入口，避免等待登录时重复发起请求。
    if (isSubmitting) return;
    if (phoneController.text.trim().isEmpty ||
        passwordController.text.isEmpty) {
      setState(() => errorMessage = '请填写手机号和密码');
      return;
    }
    FocusScope.of(context).unfocus();
    setState(() {
      isSubmitting = true;
      errorMessage = null;
    });
    try {
      await widget.onLogin(
        phone: phoneController.text.trim(),
        password: passwordController.text,
      );
    } catch (error) {
      if (!mounted) return;
      setState(() => errorMessage = ApiClient.userMessageFor(error));
    } finally {
      if (mounted) setState(() => isSubmitting = false);
    }
  }

  void _showPasswordHelp() {
    // 后端尚无密码重置接口，说明当前支持方式，避免留下无效入口。
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('找回密码'),
        content: const Text('当前版本暂不支持自助重置密码，请联系账号管理员协助处理。'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('知道了'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return AuthEntryPage(
      title: '欢迎回来',
      subtitle: '登录田掌柜，打理好你的每一天',
      children: [
        AutofillGroup(
          child: Column(children: [
            AuthInputField(
              label: '手机号',
              placeholder: '请输入手机号',
              icon: LucideIcons.smartphone,
              controller: phoneController,
              keyboardType: TextInputType.phone,
              textInputAction: TextInputAction.next,
              autofillHints: const [AutofillHints.username],
              readOnly: isSubmitting,
              filled: true,
              height: 56,
              labelGap: 8,
            ),
            const SizedBox(height: 20),
            AuthInputField(
              label: '密码',
              placeholder: '请输入密码',
              icon: LucideIcons.lockKeyhole,
              controller: passwordController,
              obscureText: true,
              showObscureToggle: true,
              textInputAction: TextInputAction.done,
              onSubmitted: (_) => _submit(),
              autofillHints: const [AutofillHints.password],
              readOnly: isSubmitting,
              filled: true,
              height: 56,
              labelGap: 8,
            ),
          ]),
        ),
        Align(
          alignment: Alignment.centerRight,
          child: TextButton(
            onPressed: isSubmitting ? null : _showPasswordHelp,
            style: TextButton.styleFrom(
              foregroundColor: AppColors.muted,
              minimumSize: const Size(44, 44),
              padding: const EdgeInsets.symmetric(horizontal: 4),
              textStyle: AppTextStyles.body,
            ),
            child: const Text('忘记密码'),
          ),
        ),
        if (errorMessage != null) ...[
          AuthErrorBanner(message: errorMessage!),
          const SizedBox(height: 12),
        ],
        AuthEntrySubmitButton(
          label: '登录',
          loadingLabel: '登录中',
          onTap: _submit,
          isLoading: isSubmitting,
        ),
        const SizedBox(height: 12),
        AuthEntrySwitchLink(
          prefix: '还没有账号？',
          action: '去注册',
          onTap: isSubmitting ? null : widget.onRegister,
        ),
      ],
    );
  }
}
