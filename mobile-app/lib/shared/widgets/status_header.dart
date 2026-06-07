import 'package:flutter/material.dart';

import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';

class StatusHeader extends StatelessWidget {
  const StatusHeader({
    super.key,
    required this.title,
    required this.subtitle,
    required this.trailingIcon,
    this.leadingIcon,
    this.center = false,
  });

  final String title;
  final String subtitle;
  final IconData trailingIcon;
  final IconData? leadingIcon;
  final bool center;

  @override
  Widget build(BuildContext context) {
    final titleBlock = Column(
      crossAxisAlignment:
          center ? CrossAxisAlignment.center : CrossAxisAlignment.start,
      children: [
        Text(title, style: AppTextStyles.title),
        const SizedBox(height: 5),
        Text(subtitle, style: AppTextStyles.small.copyWith(fontSize: 12)),
      ],
    );

    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 10),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          if (leadingIcon != null)
            HeaderAction(icon: leadingIcon!)
          else
            titleBlock,
          if (leadingIcon != null) titleBlock,
          HeaderAction(icon: trailingIcon),
        ],
      ),
    );
  }
}

class HeaderAction extends StatelessWidget {
  const HeaderAction({super.key, required this.icon, this.onTap});

  final IconData icon;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return PressableScale(
      onTap: onTap,
      child: Container(
        width: 38,
        height: 38,
        decoration: BoxDecoration(
          color: AppColors.surface2,
          borderRadius: BorderRadius.circular(13),
        ),
        child: Icon(icon, size: 18, color: AppColors.blue),
      ),
    );
  }
}

class PressableScale extends StatefulWidget {
  const PressableScale({super.key, required this.child, this.onTap});

  final Widget child;
  final VoidCallback? onTap;

  @override
  State<PressableScale> createState() => _PressableScaleState();
}

class _PressableScaleState extends State<PressableScale> {
  bool _pressed = false;

  void _setPressed(bool value) {
    if (_pressed == value) return;
    setState(() => _pressed = value);
  }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: widget.onTap,
      onTapDown: (_) => _setPressed(true),
      onTapCancel: () => _setPressed(false),
      onTapUp: (_) => _setPressed(false),
      child: AnimatedScale(
        scale: _pressed ? 0.97 : 1,
        duration: const Duration(milliseconds: 120),
        curve: Curves.easeOutCubic,
        child: widget.child,
      ),
    );
  }
}
