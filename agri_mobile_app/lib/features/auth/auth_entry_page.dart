import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../shared/app_identity.dart';
import '../../shared/assets/app_assets.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';

/// 登录和注册共用视觉骨架，认证请求和表单状态仍由各页面管理。
class AuthEntryPage extends StatelessWidget {
  const AuthEntryPage({
    super.key,
    required this.title,
    required this.subtitle,
    required this.children,
  });

  final String title;
  final String subtitle;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    final keyboardOpen = MediaQuery.viewInsetsOf(context).bottom > 0;
    return Scaffold(
      backgroundColor: AppColors.surface,
      body: SafeArea(
        child: LayoutBuilder(builder: (context, constraints) {
          // 同一屏幕采用相同布局；键盘弹出后让出插画空间给表单。
          final compact = constraints.maxHeight < 760;
          return SingleChildScrollView(
            keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
            padding: const EdgeInsets.fromLTRB(28, 20, 28, 24),
            child: Center(
              child: ConstrainedBox(
                constraints: BoxConstraints(
                  maxWidth: 430,
                  minHeight:
                      (constraints.maxHeight - 44).clamp(0, double.infinity),
                ),
                child: IntrinsicHeight(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      const _EntryBrand(),
                      SizedBox(height: compact ? 20 : 32),
                      if (!keyboardOpen) ...[
                        _FarmWelcome(height: compact ? 160 : 192),
                        SizedBox(height: compact ? 24 : 32),
                      ],
                      Text(title,
                          style: AppTextStyles.title.copyWith(
                              fontSize: 24, fontWeight: FontWeight.w600)),
                      const SizedBox(height: 8),
                      Text(subtitle,
                          style: AppTextStyles.body
                              .copyWith(color: AppColors.muted)),
                      const SizedBox(height: 24),
                      ...children,
                      const Spacer(),
                      const SizedBox(height: 24),
                      const _EntryFooter(),
                    ],
                  ),
                ),
              ),
            ),
          );
        }),
      ),
    );
  }
}

class AuthEntrySubmitButton extends StatelessWidget {
  const AuthEntrySubmitButton({
    super.key,
    required this.label,
    required this.loadingLabel,
    required this.onTap,
    this.isLoading = false,
  });

  final String label;
  final String loadingLabel;
  final VoidCallback onTap;
  final bool isLoading;

  @override
  Widget build(BuildContext context) {
    return FilledButton(
      onPressed: isLoading ? null : onTap,
      style: FilledButton.styleFrom(
        backgroundColor: AppColors.blue,
        disabledBackgroundColor: AppColors.blue,
        foregroundColor: AppColors.surface,
        minimumSize: const Size.fromHeight(56),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      ),
      child: isLoading
          ? SizedBox(
              width: 20,
              height: 20,
              child: CircularProgressIndicator(
                  strokeWidth: 2,
                  color: AppColors.surface,
                  semanticsLabel: loadingLabel),
            )
          : Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(label,
                    style: const TextStyle(
                        fontSize: 16, fontWeight: FontWeight.w600)),
                const SizedBox(width: 12),
                const Icon(LucideIcons.arrowRight, size: 18),
              ],
            ),
    );
  }
}

class AuthEntrySwitchLink extends StatelessWidget {
  const AuthEntrySwitchLink({
    super.key,
    required this.prefix,
    required this.action,
    required this.onTap,
  });

  final String prefix;
  final String action;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return TextButton(
      onPressed: onTap,
      style: TextButton.styleFrom(minimumSize: const Size.fromHeight(48)),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(prefix,
              style: AppTextStyles.body.copyWith(color: AppColors.muted)),
          const SizedBox(width: 4),
          Text(action,
              style: AppTextStyles.body.copyWith(color: AppColors.blue)),
        ],
      ),
    );
  }
}

class _EntryBrand extends StatelessWidget {
  const _EntryBrand();

  @override
  Widget build(BuildContext context) {
    return Row(
      key: const ValueKey('auth-entry-brand'),
      children: [
        Image.asset(AppAssets.brandLogo, width: 40, height: 40),
        const SizedBox(width: 12),
        Text(AppIdentity.displayName, style: AppTextStyles.sectionTitle),
        const Spacer(),
        Text('你的农场经营助手', style: AppTextStyles.small),
      ],
    );
  }
}

class _FarmWelcome extends StatelessWidget {
  const _FarmWelcome({required this.height});

  final double height;

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      key: const ValueKey('auth-entry-hero'),
      borderRadius: BorderRadius.circular(24),
      child: Container(
        height: height,
        color: AppColors.blueSoft,
        child: Stack(
          children: [
            Positioned(
              right: -12,
              bottom: -8,
              child: ExcludeSemantics(
                child: Image.asset(AppAssets.homeHeroFarm,
                    width: 280, height: 140, fit: BoxFit.contain),
              ),
            ),
            Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('耕耘有记录\n收获心里有数',
                      style: AppTextStyles.title.copyWith(
                          fontSize: 22,
                          height: 1.45,
                          fontWeight: FontWeight.w600,
                          color: AppColors.navy)),
                  const SizedBox(height: 8),
                  Text('把农场记录得更轻松',
                      style:
                          AppTextStyles.small.copyWith(color: AppColors.muted)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _EntryFooter extends StatelessWidget {
  const _EntryFooter();

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(LucideIcons.shieldCheck,
                size: 14, color: AppColors.muted),
            const SizedBox(width: 8),
            Flexible(child: Text('数据仅用于你的农场记录', style: AppTextStyles.small)),
          ],
        ),
        const SizedBox(height: 8),
        Text('每一份耕耘，都值得被记住', style: AppTextStyles.small),
      ],
    );
  }
}
