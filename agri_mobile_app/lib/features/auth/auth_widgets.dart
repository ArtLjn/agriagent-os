import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../shared/app_identity.dart';
import '../../shared/assets/app_assets.dart';
import '../../shared/widgets/card_panel.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';

class AuthPage extends StatelessWidget {
  const AuthPage({
    super.key,
    required this.children,
    this.bottomPadding = 32,
  });

  final List<Widget> children;
  final double bottomPadding;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      resizeToAvoidBottomInset: true,
      body: DecoratedBox(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [
              Color(0xFFF9FCFF),
              Color(0xFFF1F7FF),
              AppColors.background
            ],
            stops: [0, 0.52, 1],
          ),
        ),
        child: Stack(
          children: [
            const Positioned.fill(
                child: IgnorePointer(
                    child: CustomPaint(
              painter: _AuthBackdropPainter(),
            ))),
            SafeArea(
              child: SingleChildScrollView(
                keyboardDismissBehavior:
                    ScrollViewKeyboardDismissBehavior.onDrag,
                padding: EdgeInsets.fromLTRB(20, 16, 20, bottomPadding),
                child: Center(
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 430),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: children,
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class AuthBrandHeader extends StatelessWidget {
  const AuthBrandHeader({
    super.key,
    required this.title,
    required this.subtitle,
    this.compact = false,
  });

  final String title;
  final String subtitle;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    if (compact) {
      return SizedBox(
        height: 148,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _AuthBrandRow(compact: true),
            const Spacer(),
            _AuthTitle(title: title, subtitle: subtitle, compact: true),
          ],
        ),
      );
    }

    return SizedBox(
      height: 166,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const _AuthBrandRow(showName: false),
          const Spacer(),
          _AuthTitle(title: title, subtitle: subtitle),
        ],
      ),
    );
  }
}

class _AuthBrandRow extends StatelessWidget {
  const _AuthBrandRow({this.compact = false, this.showName = true});

  final bool compact;
  final bool showName;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        AuthLogo(size: compact ? 42 : 48),
        if (showName) ...[
          const SizedBox(width: 12),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                AppIdentity.displayName,
                style: AppTextStyles.sectionTitle.copyWith(
                  fontSize: compact ? 17 : 18,
                ),
              ),
              Text(
                AppIdentity.tagline,
                style: AppTextStyles.small.copyWith(color: AppColors.subtle),
              ),
            ],
          ),
        ],
        const Spacer(),
        SizedBox(
          width: compact ? 104 : 122,
          height: compact ? 76 : 86,
          child: _FloatingCardsScene(
            width: compact ? 104 : 122,
            height: compact ? 76 : 86,
          ),
        ),
      ],
    );
  }
}

class _AuthTitle extends StatelessWidget {
  const _AuthTitle({
    required this.title,
    required this.subtitle,
    this.compact = false,
  });

  final String title;
  final String subtitle;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: TextStyle(
            color: AppColors.ink,
            fontSize: compact ? 28 : 30,
            height: compact ? 34 / 28 : 36 / 30,
            fontWeight: FontWeight.w800,
          ),
        ),
        const SizedBox(height: 6),
        Text(
          subtitle,
          style: AppTextStyles.body.copyWith(
            color: AppColors.subtle,
            fontSize: compact ? 14 : 15,
          ),
        ),
      ],
    );
  }
}

class SetupHero extends StatelessWidget {
  const SetupHero({super.key});

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 252,
      child: Stack(
        clipBehavior: Clip.none,
        children: [
          Positioned(
            left: -10,
            top: 18,
            child: Text(
              '完善农场信息',
              style: const TextStyle(
                color: AppColors.ink,
                fontSize: 32,
                height: 39 / 32,
                fontWeight: FontWeight.w800,
                letterSpacing: 0,
              ),
            ),
          ),
          Positioned(
            left: -8,
            top: 76,
            child: Text(
              '这些信息之后也可以修改',
              style: AppTextStyles.body.copyWith(
                color: AppColors.subtle,
                fontSize: 17,
              ),
            ),
          ),
          Positioned(
            left: 0,
            right: 0,
            bottom: 0,
            child: SizedBox(
              height: 138,
              child: Stack(
                children: [
                  Positioned.fill(
                    child: CustomPaint(painter: _SetupBlobPainter()),
                  ),
                  const Positioned(
                    left: 6,
                    bottom: 16,
                    child: _SetupFeatureCard(
                      icon: LucideIcons.cloudSun,
                      label: '天气',
                    ),
                  ),
                  const Positioned(
                    left: 130,
                    bottom: 36,
                    child: _SetupFeatureCard(
                      icon: LucideIcons.notebookText,
                      label: '记录',
                      emphasized: true,
                    ),
                  ),
                  const Positioned(
                    right: 8,
                    bottom: 16,
                    child: _SetupFeatureCard(
                      icon: LucideIcons.walletCards,
                      label: '账本',
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class AuthSurfaceCard extends StatelessWidget {
  const AuthSurfaceCard({
    super.key,
    required this.children,
    this.padding = const EdgeInsets.all(20),
  });

  final List<Widget> children;
  final EdgeInsets padding;

  @override
  Widget build(BuildContext context) {
    return CardPanel(
      radius: 24,
      padding: padding,
      borderColor: AppColors.line,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: children,
      ),
    );
  }
}

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
        : AppColors.surface;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          widget.label,
          style: AppTextStyles.sectionTitle
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
              color: borderColor,
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
                  color: _focusNode.hasFocus
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
                      const BoxConstraints(minWidth: 40, minHeight: 40),
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

class AuthPrimaryButton extends StatelessWidget {
  const AuthPrimaryButton({
    super.key,
    required this.label,
    required this.onTap,
    this.isLoading = false,
  });

  final String label;
  final VoidCallback onTap;
  final bool isLoading;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 54,
      child: Semantics(
        button: true,
        enabled: !isLoading,
        label: label,
        onTap: isLoading ? null : onTap,
        child: GestureDetector(
          behavior: HitTestBehavior.opaque,
          onTap: isLoading ? null : onTap,
          child: Container(
            height: 54,
            decoration: BoxDecoration(
              color: AppColors.blue,
              borderRadius: BorderRadius.circular(16),
              boxShadow: const [
                BoxShadow(
                  color: Color(0x1A2F73F6),
                  blurRadius: 18,
                  offset: Offset(0, 8),
                ),
              ],
            ),
            child: Center(
              child: isLoading
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(
                        strokeWidth: 2.2,
                        color: Colors.white,
                      ),
                    )
                  : Text(
                      label,
                      style: AppTextStyles.sectionTitle.copyWith(
                        color: Colors.white,
                        fontSize: 17,
                      ),
                    ),
            ),
          ),
        ),
      ),
    );
  }
}

class AuthTextLink extends StatelessWidget {
  const AuthTextLink({
    super.key,
    required this.prefix,
    required this.action,
    required this.onTap,
  });

  final String prefix;
  final String action;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      child: Semantics(
        button: true,
        label: '$prefix$action',
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 6),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(
                prefix,
                style: AppTextStyles.body.copyWith(color: AppColors.muted),
              ),
              const SizedBox(width: 6),
              Text(
                action,
                style: AppTextStyles.body.copyWith(
                  color: AppColors.blue,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ],
          ),
        ),
      ),
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

class AuthLogo extends StatelessWidget {
  const AuthLogo({super.key, this.size = 64, this.accent = true});

  final double size;
  final bool accent;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(size * 0.24),
        boxShadow: const [
          BoxShadow(
            color: Color(0x10000000),
            blurRadius: 18,
            offset: Offset(0, 8),
          ),
        ],
      ),
      child: Padding(
        padding: EdgeInsets.all(size * 0.12),
        child: Image.asset(
          AppAssets.brandLogo,
          fit: BoxFit.contain,
          errorBuilder: (context, error, stackTrace) =>
              CustomPaint(painter: _AuthLogoPainter(accent: accent)),
        ),
      ),
    );
  }
}

class DataNotice extends StatelessWidget {
  const DataNotice({
    super.key,
    required this.text,
    this.topPadding = 20,
  });

  final String text;
  final double topPadding;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(top: topPadding),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(LucideIcons.shieldCheck, size: 18, color: AppColors.blue),
          const SizedBox(width: 8),
          Text(
            text,
            style: AppTextStyles.body.copyWith(color: AppColors.subtle),
          ),
        ],
      ),
    );
  }
}

class _AuthBackdropPainter extends CustomPainter {
  const _AuthBackdropPainter();

  @override
  void paint(Canvas canvas, Size size) {
    final blueGlow = Paint()..color = AppColors.blue.withValues(alpha: 0.045);
    final greenGlow = Paint()..color = AppColors.green.withValues(alpha: 0.035);
    final line = Paint()
      ..color = AppColors.blue.withValues(alpha: 0.09)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.2;

    canvas.drawCircle(
      Offset(size.width * 0.98, size.height * 0.06),
      size.width * 0.34,
      blueGlow,
    );
    canvas.drawCircle(
      Offset(size.width * 0.02, size.height * 0.88),
      size.width * 0.26,
      greenGlow,
    );
    canvas.drawArc(
      Rect.fromCenter(
        center: Offset(size.width * 0.92, size.height * 0.18),
        width: size.width * 0.58,
        height: size.width * 0.58,
      ),
      2.1,
      1.8,
      false,
      line,
    );
  }

  @override
  bool shouldRepaint(covariant _AuthBackdropPainter oldDelegate) => false;
}

class CapabilityChip extends StatelessWidget {
  const CapabilityChip({
    super.key,
    required this.label,
    required this.icon,
    required this.color,
    required this.background,
  });

  final String label;
  final IconData icon;
  final Color color;
  final Color background;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 48,
      padding: const EdgeInsets.symmetric(horizontal: 9),
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(17),
        border: Border.all(color: color.withValues(alpha: 0.14)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            width: 28,
            height: 28,
            decoration: BoxDecoration(
              color: color,
              borderRadius: BorderRadius.circular(14),
            ),
            child: Icon(icon, size: 16, color: Colors.white),
          ),
          const SizedBox(width: 6),
          Flexible(
            child: FittedBox(
              fit: BoxFit.scaleDown,
              child: Text(
                label,
                maxLines: 1,
                style: AppTextStyles.listTitle.copyWith(
                  color: color,
                  fontSize: 14,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _FloatingCardsScene extends StatelessWidget {
  const _FloatingCardsScene({required this.width, required this.height});

  final double width;
  final double height;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: width,
      height: height,
      child: Stack(
        clipBehavior: Clip.none,
        children: [
          Positioned.fill(child: CustomPaint(painter: _OrbitPainter())),
          Positioned(
            right: 8,
            top: 4,
            child: Transform.rotate(
              angle: 0.08,
              child: _MiniGlassCard(
                width: width * 0.58,
                height: height * 0.34,
                child: const _ChartGlyph(),
              ),
            ),
          ),
          Positioned(
            left: width * 0.18,
            top: height * 0.42,
            child: Transform.rotate(
              angle: -0.04,
              child: _MiniGlassCard(
                width: width * 0.45,
                height: height * 0.28,
                child: const _MetricGlyph(),
              ),
            ),
          ),
          Positioned(
            right: width * 0.02,
            bottom: height * 0.1,
            child: Container(
              width: height * 0.3,
              height: height * 0.3,
              decoration: BoxDecoration(
                color: AppColors.green.withValues(alpha: 0.75),
                borderRadius: BorderRadius.circular(16),
                boxShadow: [
                  BoxShadow(
                    color: AppColors.green.withValues(alpha: 0.2),
                    blurRadius: 18,
                    offset: const Offset(0, 8),
                  ),
                ],
              ),
              child: const Icon(LucideIcons.check, color: Colors.white),
            ),
          ),
        ],
      ),
    );
  }
}

class _MiniGlassCard extends StatelessWidget {
  const _MiniGlassCard({
    required this.width,
    required this.height,
    required this.child,
  });

  final double width;
  final double height;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: width,
      height: height,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.78),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: Colors.white.withValues(alpha: 0.9)),
        boxShadow: const [
          BoxShadow(
            color: Color(0x0F2F73F6),
            blurRadius: 20,
            offset: Offset(0, 10),
          ),
        ],
      ),
      child: child,
    );
  }
}

class _ChartGlyph extends StatelessWidget {
  const _ChartGlyph();

  @override
  Widget build(BuildContext context) {
    return CustomPaint(painter: _ChartGlyphPainter());
  }
}

class _MetricGlyph extends StatelessWidget {
  const _MetricGlyph();

  @override
  Widget build(BuildContext context) {
    return CustomPaint(painter: _MetricGlyphPainter());
  }
}

class _SetupFeatureCard extends StatelessWidget {
  const _SetupFeatureCard({
    required this.icon,
    required this.label,
    this.emphasized = false,
  });

  final IconData icon;
  final String label;
  final bool emphasized;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: emphasized ? 88 : 80,
      height: emphasized ? 96 : 84,
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppColors.lineSoft),
        boxShadow: const [
          BoxShadow(
            color: Color(0x0F000000),
            blurRadius: 18,
            offset: Offset(0, 8),
          ),
        ],
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, size: emphasized ? 32 : 28, color: AppColors.blue),
          const SizedBox(height: 8),
          Text(label, style: AppTextStyles.listTitle),
        ],
      ),
    );
  }
}

class _AuthLogoPainter extends CustomPainter {
  const _AuthLogoPainter({required this.accent});

  final bool accent;

  @override
  void paint(Canvas canvas, Size size) {
    final blue = Paint()
      ..color = AppColors.blue
      ..style = PaintingStyle.stroke
      ..strokeWidth = size.width * 0.13
      ..strokeCap = StrokeCap.round;
    final dot = Paint()..color = AppColors.blue;
    final green = Paint()..color = AppColors.green;

    canvas.drawArc(
      Rect.fromLTWH(
        size.width * 0.25,
        size.height * 0.32,
        size.width * 0.5,
        size.height * 0.44,
      ),
      0.15,
      2.85,
      false,
      blue,
    );
    canvas.drawCircle(
      Offset(size.width * 0.36, size.height * 0.36),
      size.width * 0.075,
      dot,
    );
    if (accent) {
      canvas.drawCircle(
        Offset(size.width * 0.66, size.height * 0.32),
        size.width * 0.075,
        green,
      );
      canvas.drawRRect(
        RRect.fromRectAndRadius(
          Rect.fromLTWH(
            size.width * 0.58,
            size.height * 0.45,
            size.width * 0.2,
            size.height * 0.08,
          ),
          Radius.circular(size.width * 0.04),
        ),
        green,
      );
    }
  }

  @override
  bool shouldRepaint(covariant _AuthLogoPainter oldDelegate) =>
      oldDelegate.accent != accent;
}

class _OrbitPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final blob = Paint()
      ..color = AppColors.blue.withValues(alpha: 0.08)
      ..style = PaintingStyle.fill;
    final orbit = Paint()
      ..color = Colors.white.withValues(alpha: 0.7)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.6;

    canvas.drawOval(
      Rect.fromCenter(
        center: Offset(size.width * 0.54, size.height * 0.56),
        width: size.width * 0.86,
        height: size.height * 0.72,
      ),
      blob,
    );
    canvas.drawArc(
      Rect.fromCenter(
        center: Offset(size.width * 0.58, size.height * 0.54),
        width: size.width * 1.02,
        height: size.height * 0.92,
      ),
      -0.6,
      4.2,
      false,
      orbit,
    );
  }

  @override
  bool shouldRepaint(covariant _OrbitPainter oldDelegate) => false;
}

class _ChartGlyphPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final blue = Paint()
      ..color = AppColors.blue.withValues(alpha: 0.7)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 3
      ..strokeCap = StrokeCap.round;
    final dot = Paint()..color = Colors.white;
    final points = [
      Offset(size.width * 0.12, size.height * 0.68),
      Offset(size.width * 0.34, size.height * 0.48),
      Offset(size.width * 0.54, size.height * 0.58),
      Offset(size.width * 0.76, size.height * 0.28),
    ];
    final path = Path()..moveTo(points.first.dx, points.first.dy);
    for (final point in points.skip(1)) {
      path.lineTo(point.dx, point.dy);
    }
    canvas.drawPath(path, blue);
    for (final point in points) {
      canvas.drawCircle(point, 4, dot);
      canvas.drawCircle(point, 2, Paint()..color = AppColors.blue);
    }
  }

  @override
  bool shouldRepaint(covariant _ChartGlyphPainter oldDelegate) => false;
}

class _MetricGlyphPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final blue = Paint()..color = AppColors.blue;
    final green = Paint()..color = AppColors.green;
    final gray = Paint()..color = const Color(0xFFC9D3E2);
    canvas.drawArc(
      Rect.fromLTWH(
          0, size.height * 0.08, size.height * 0.58, size.height * 0.58),
      -1.57,
      4.3,
      true,
      blue,
    );
    canvas.drawCircle(
      Offset(size.height * 0.29, size.height * 0.37),
      size.height * 0.16,
      Paint()..color = Colors.white,
    );
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromLTWH(
            size.width * 0.56, size.height * 0.18, size.width * 0.36, 6),
        const Radius.circular(999),
      ),
      gray,
    );
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromLTWH(
            size.width * 0.56, size.height * 0.48, size.width * 0.3, 6),
        const Radius.circular(999),
      ),
      green,
    );
  }

  @override
  bool shouldRepaint(covariant _MetricGlyphPainter oldDelegate) => false;
}

class _SetupBlobPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final blob = Paint()..color = AppColors.blue.withValues(alpha: 0.1);
    final path = Path()
      ..moveTo(size.width * 0.1, size.height * 0.75)
      ..cubicTo(size.width * 0.2, size.height * 0.08, size.width * 0.72,
          -size.height * 0.02, size.width * 0.85, size.height * 0.3)
      ..cubicTo(size.width * 1.02, size.height * 0.72, size.width * 0.56,
          size.height * 1.08, size.width * 0.18, size.height * 0.92)
      ..cubicTo(size.width * 0.04, size.height * 0.86, size.width * 0.04,
          size.height * 0.82, size.width * 0.1, size.height * 0.75)
      ..close();
    canvas.drawPath(path, blob);

    final line = Paint()
      ..color = AppColors.blue.withValues(alpha: 0.45)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2;
    final curve = Path()
      ..moveTo(size.width * 0.24, size.height * 0.62)
      ..cubicTo(size.width * 0.36, size.height * 0.36, size.width * 0.48,
          size.height * 0.38, size.width * 0.58, size.height * 0.55)
      ..cubicTo(size.width * 0.68, size.height * 0.72, size.width * 0.78,
          size.height * 0.56, size.width * 0.88, size.height * 0.42);
    canvas.drawPath(curve, line);
  }

  @override
  bool shouldRepaint(covariant _SetupBlobPainter oldDelegate) => false;
}
