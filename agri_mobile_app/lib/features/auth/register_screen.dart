import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../data/api/api_client.dart';
import 'auth_entry_page.dart';
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
    // 注册按钮和键盘提交共用入口，等待响应时避免重复创建账号。
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
      await widget.onRegister(
        phone: phoneController.text.trim(),
        password: passwordController.text,
        nickname: nicknameController.text.trim().isEmpty
            ? '农友'
            : nicknameController.text.trim(),
      );
    } catch (error) {
      if (!mounted) return;
      setState(() => errorMessage = ApiClient.userMessageFor(error));
    } finally {
      if (mounted) setState(() => isSubmitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return AuthEntryPage(
      title: '创建账号',
      subtitle: '先建账号，记录可以慢慢补',
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
              label: '设置密码',
              placeholder: '请设置6-16位密码',
              icon: LucideIcons.lockKeyhole,
              controller: passwordController,
              obscureText: true,
              showObscureToggle: true,
              textInputAction: TextInputAction.next,
              autofillHints: const [AutofillHints.newPassword],
              readOnly: isSubmitting,
              filled: true,
              height: 56,
              labelGap: 8,
            ),
            const SizedBox(height: 20),
            AuthInputField(
              label: '昵称',
              placeholder: '怎么称呼你（选填）',
              icon: LucideIcons.userRound,
              controller: nicknameController,
              textInputAction: TextInputAction.done,
              autofillHints: const [AutofillHints.nickname],
              onSubmitted: (_) => _submit(),
              readOnly: isSubmitting,
              filled: true,
              height: 56,
              labelGap: 8,
            ),
          ]),
        ),
        const SizedBox(height: 24),
        if (errorMessage != null) ...[
          AuthErrorBanner(message: errorMessage!),
          const SizedBox(height: 12),
        ],
        AuthEntrySubmitButton(
          label: '注册并进入',
          loadingLabel: '注册中',
          onTap: _submit,
          isLoading: isSubmitting,
        ),
        const SizedBox(height: 12),
        AuthEntrySwitchLink(
          prefix: '已有账号？',
          action: '去登录',
          onTap: isSubmitting ? null : widget.onLogin,
        ),
      ],
    );
  }
}
