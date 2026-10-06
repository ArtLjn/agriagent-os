import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';

class AuthInputField extends StatefulWidget {
  const AuthInputField({
    super.key,
    required this.label,
    required this.placeholder,
    required this.icon,
    this.controller,
    this.trailing,
    this.readOnly = false,
    this.onTap,
    this.height = 52,
    this.labelGap = 10,
    this.labelFontSize = 15,
    this.obscureText = false,
    this.showObscureToggle = false,
    this.keyboardType,
    this.textInputAction,
    this.autofillHints,
    this.onSubmitted,
    this.filled = false,
  });

  final String label;
  final String placeholder;
  final IconData icon;
  final TextEditingController? controller;
  final Widget? trailing;
  final bool readOnly;
  final VoidCallback? onTap;
  final double height;
  final double labelGap;
  final double labelFontSize;
  final bool obscureText;
  final bool showObscureToggle;
  final TextInputType? keyboardType;
  final TextInputAction? textInputAction;
  final Iterable<String>? autofillHints;
  final ValueChanged<String>? onSubmitted;
  final bool filled;

  @override
  State<AuthInputField> createState() => _AuthInputFieldState();
}

class _AuthInputFieldState extends State<AuthInputField> {
  late final FocusNode _focusNode;
  late bool _obscured;

  @override
  void initState() {
    super.initState();
    _focusNode = FocusNode()..addListener(_handleFocusChanged);
    _obscured = widget.obscureText;
  }

  @override
  void dispose() {
    _focusNode
      ..removeListener(_handleFocusChanged)
      ..dispose();
    super.dispose();
  }

  void _handleFocusChanged() => setState(() {});

  @override
  Widget build(BuildContext context) {
    final borderColor = _focusNode.hasFocus ? AppColors.blue : AppColors.line;
    final fillColor = _focusNode.hasFocus
        ? AppColors.blueSoft.withValues(alpha: 0.42)
        : widget.filled
            ? AppColors.surface2
            : AppColors.surface;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          widget.label,
          style: widget.filled
              ? AppTextStyles.body.copyWith(color: AppColors.muted)
              : AppTextStyles.sectionTitle
                  .copyWith(fontSize: widget.labelFontSize),
        ),
        SizedBox(height: widget.labelGap),
        AnimatedContainer(
          duration: const Duration(milliseconds: 160),
          height: widget.height,
          padding: const EdgeInsets.symmetric(horizontal: 12),
          decoration: BoxDecoration(
            color: fillColor,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(
              color: widget.filled && !_focusNode.hasFocus
                  ? AppColors.lineSoft
                  : borderColor,
              width: _focusNode.hasFocus ? 1.5 : 1,
            ),
            boxShadow: _focusNode.hasFocus
                ? [
                    BoxShadow(
                      color: AppColors.blue.withValues(alpha: 0.08),
                      blurRadius: 12,
                      offset: const Offset(0, 4),
                    ),
                  ]
                : null,
          ),
          child: Row(
            children: [
              AnimatedContainer(
                duration: const Duration(milliseconds: 160),
                width: 32,
                height: 32,
                decoration: BoxDecoration(
                  color: widget.filled
                      ? Colors.transparent
                      : _focusNode.hasFocus
                          ? AppColors.blue.withValues(alpha: 0.12)
                          : AppColors.surface2,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(
                  widget.icon,
                  size: 18,
                  color:
                      _focusNode.hasFocus ? AppColors.blue : AppColors.subtle,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Semantics(
                  label: widget.label,
                  child: TextField(
                    controller: widget.controller,
                    focusNode: _focusNode,
                    readOnly: widget.readOnly,
                    onTap: widget.onTap,
                    onSubmitted: widget.onSubmitted,
                    keyboardType: widget.keyboardType,
                    textInputAction: widget.textInputAction,
                    autofillHints: widget.autofillHints,
                    obscureText: _obscured,
                    maxLines: 1,
                    cursorColor: AppColors.blue,
                    style: AppTextStyles.body.copyWith(
                      color: AppColors.ink,
                      fontSize: 15,
                    ),
                    decoration: InputDecoration(
                      border: InputBorder.none,
                      isDense: true,
                      contentPadding: EdgeInsets.zero,
                      hintText: widget.placeholder,
                      hintStyle: AppTextStyles.body.copyWith(
                        color: AppColors.subtle,
                        fontSize: 15,
                      ),
                    ),
                  ),
                ),
              ),
              if (widget.showObscureToggle) ...[
                const SizedBox(width: 4),
                IconButton(
                  onPressed: () => setState(() => _obscured = !_obscured),
                  icon: Icon(
                    _obscured ? LucideIcons.eyeOff : LucideIcons.eye,
                    size: 19,
                    color: AppColors.subtle,
                  ),
                  tooltip: _obscured ? '显示密码' : '隐藏密码',
                  padding: EdgeInsets.zero,
                  constraints:
                      const BoxConstraints(minWidth: 44, minHeight: 44),
                ),
              ] else if (widget.trailing != null) ...[
                const SizedBox(width: 8),
                widget.trailing!,
              ],
            ],
          ),
        ),
      ],
    );
  }
}

class AuthErrorBanner extends StatelessWidget {
  const AuthErrorBanner({super.key, required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      liveRegion: true,
      label: message,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        decoration: BoxDecoration(
          color: AppColors.redSoft,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppColors.red.withValues(alpha: 0.14)),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Padding(
              padding: EdgeInsets.only(top: 1),
              child: Icon(
                LucideIcons.circleAlert,
                size: 16,
                color: AppColors.red,
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                message,
                style: AppTextStyles.small.copyWith(color: AppColors.red),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
