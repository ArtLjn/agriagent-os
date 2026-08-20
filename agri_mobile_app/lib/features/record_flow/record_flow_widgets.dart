import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../shared/widgets/card_panel.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';

class FlowScaffold extends StatelessWidget {
  const FlowScaffold({
    super.key,
    required this.title,
    required this.children,
    this.subtitle,
    this.bottomBar,
    this.centerTitle = false,
    this.topTrailing,
    this.bottomPadding = 120,
  });

  final String title;
  final String? subtitle;
  final List<Widget> children;
  final Widget? bottomBar;
  final bool centerTitle;
  final Widget? topTrailing;
  final double bottomPadding;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: DecoratedBox(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [AppColors.backgroundTop, AppColors.background],
          ),
        ),
        child: SafeArea(
          child: Stack(
            children: [
              SingleChildScrollView(
                padding: EdgeInsets.fromLTRB(20, 8, 20, bottomPadding),
                child: Center(
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 430),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        FlowHeader(
                          title: title,
                          subtitle: subtitle,
                          centerTitle: centerTitle,
                          trailing: topTrailing,
                        ),
                        ...children,
                      ],
                    ),
                  ),
                ),
              ),
              if (bottomBar != null)
                Positioned(left: 0, right: 0, bottom: 0, child: bottomBar!),
            ],
          ),
        ),
      ),
    );
  }
}

class FlowHeader extends StatelessWidget {
  const FlowHeader({
    super.key,
    required this.title,
    this.subtitle,
    this.centerTitle = false,
    this.trailing,
  });

  final String title;
  final String? subtitle;
  final bool centerTitle;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: SizedBox(
        height: subtitle == null ? 48 : 68,
        child: Stack(
          alignment: centerTitle ? Alignment.topCenter : Alignment.topLeft,
          children: [
            Positioned(
              left: -8,
              top: 0,
              child: FlowBackButton(onTap: () => Navigator.of(context).pop()),
            ),
            Positioned.fill(
              left: centerTitle ? 52 : 58,
              right: centerTitle ? 52 : 0,
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: centerTitle
                    ? CrossAxisAlignment.center
                    : CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    textAlign: centerTitle ? TextAlign.center : TextAlign.left,
                    style: AppTextStyles.title.copyWith(fontSize: 21),
                  ),
                  if (subtitle != null) ...[
                    const SizedBox(height: 4),
                    Text(
                      subtitle!,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: AppTextStyles.body.copyWith(
                        color: AppColors.subtle,
                        fontSize: 13,
                      ),
                    ),
                  ],
                ],
              ),
            ),
            if (trailing != null)
              Positioned(right: 0, top: 2, child: trailing!),
          ],
        ),
      ),
    );
  }
}

class FlowBackButton extends StatelessWidget {
  const FlowBackButton({super.key, required this.onTap});

  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      child: const SizedBox(
        width: 48,
        height: 48,
        child: Icon(LucideIcons.arrowLeft, size: 26, color: AppColors.ink),
      ),
    );
  }
}

class StepIndicator extends StatelessWidget {
  const StepIndicator({super.key});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        children: [
          const _StepCircle(number: '1', active: true),
          const SizedBox(width: 7),
          Text(
            '识别完成',
            style: AppTextStyles.body.copyWith(
              color: AppColors.blue,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Container(
                height: 2, color: AppColors.blue.withValues(alpha: 0.5)),
          ),
          const SizedBox(width: 10),
          const _StepCircle(number: '2', active: false),
          const SizedBox(width: 7),
          Text(
            '确认保存',
            style: AppTextStyles.body.copyWith(
              color: AppColors.subtle,
              fontWeight: FontWeight.w800,
            ),
          ),
        ],
      ),
    );
  }
}

class _StepCircle extends StatelessWidget {
  const _StepCircle({required this.number, required this.active});

  final String number;
  final bool active;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 28,
      height: 28,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: active ? AppColors.blue : AppColors.subtle,
        boxShadow: active
            ? [
                BoxShadow(
                  color: AppColors.blue.withValues(alpha: 0.22),
                  blurRadius: 14,
                  offset: const Offset(0, 6),
                ),
              ]
            : null,
      ),
      child: Center(
        child: Text(
          number,
          style: AppTextStyles.body.copyWith(
            color: Colors.white,
            fontWeight: FontWeight.w800,
          ),
        ),
      ),
    );
  }
}

class FlowChip extends StatelessWidget {
  const FlowChip({
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
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 16, color: color),
          const SizedBox(width: 6),
          Text(
            label,
            style: AppTextStyles.body.copyWith(
              color: color,
              fontWeight: FontWeight.w800,
            ),
          ),
        ],
      ),
    );
  }
}

class FieldGroupCard extends StatelessWidget {
  const FieldGroupCard({
    super.key,
    required this.title,
    required this.icon,
    required this.color,
    required this.background,
    required this.rows,
  });

  final String title;
  final IconData icon;
  final Color color;
  final Color background;
  final List<FieldValueRow> rows;

  @override
  Widget build(BuildContext context) {
    return CardPanel(
      padding: const EdgeInsets.fromLTRB(14, 14, 14, 6),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              SoftIconTile(
                icon: icon,
                color: color,
                background: background,
                size: 38,
                iconSize: 20,
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  title,
                  style: AppTextStyles.title.copyWith(fontSize: 18),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          ...rows,
        ],
      ),
    );
  }
}

class FieldValueRow extends StatelessWidget {
  const FieldValueRow({
    super.key,
    required this.label,
    required this.value,
    this.editable = true,
  });

  final String label;
  final String value;
  final bool editable;

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(minHeight: 48),
      decoration: const BoxDecoration(
        border: Border(
          bottom: BorderSide(color: AppColors.lineSoft),
        ),
      ),
      child: Row(
        children: [
          SizedBox(
            width: 64,
            child: Text(
              label,
              style: AppTextStyles.body.copyWith(
                color: AppColors.muted,
                fontSize: 13,
              ),
            ),
          ),
          Expanded(
            child: Text(
              value,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: AppTextStyles.body.copyWith(
                fontSize: 14,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
          if (editable)
            const Icon(LucideIcons.pencil, size: 18, color: AppColors.subtle),
        ],
      ),
    );
  }
}

class FlowHintCard extends StatelessWidget {
  const FlowHintCard({super.key, required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: AppColors.blueSoft,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Row(
        children: [
          const Icon(LucideIcons.sparkles, color: AppColors.blue, size: 20),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              text,
              style: AppTextStyles.sectionTitle.copyWith(
                color: AppColors.blue,
                fontSize: 14,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class StickyActionBar extends StatelessWidget {
  const StickyActionBar({super.key, required this.children});

  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      top: false,
      child: Container(
        height: 74,
        padding: const EdgeInsets.fromLTRB(20, 8, 20, 8),
        decoration: const BoxDecoration(
          color: Colors.white,
          border: Border(top: BorderSide(color: AppColors.lineSoft)),
        ),
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 430),
            child: Row(children: children),
          ),
        ),
      ),
    );
  }
}

class FlowButton extends StatelessWidget {
  const FlowButton({
    super.key,
    required this.label,
    required this.onTap,
    this.primary = true,
    this.icon,
  });

  final String label;
  final VoidCallback onTap;
  final bool primary;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      child: Container(
        height: 46,
        decoration: BoxDecoration(
          color: primary ? AppColors.blue : AppColors.surface,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: primary ? AppColors.blue : AppColors.blue,
          ),
          boxShadow: primary
              ? [
                  BoxShadow(
                    color: AppColors.blue.withValues(alpha: 0.18),
                    blurRadius: 18,
                    offset: const Offset(0, 8),
                  ),
                ]
              : null,
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            if (icon != null) ...[
              Icon(icon,
                  size: 18, color: primary ? Colors.white : AppColors.blue),
              const SizedBox(width: 7),
            ],
            Flexible(
              child: Text(
                label,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: AppTextStyles.sectionTitle.copyWith(
                  color: primary ? Colors.white : AppColors.blue,
                  fontSize: 15,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class ContextPill extends StatelessWidget {
  const ContextPill({super.key});

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(bottom: 10),
        padding: const EdgeInsets.fromLTRB(10, 7, 14, 7),
        decoration: BoxDecoration(
          color: AppColors.blueSoft,
          borderRadius: BorderRadius.circular(999),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 28,
              height: 28,
              decoration: BoxDecoration(
                color: AppColors.blue,
                borderRadius: BorderRadius.circular(14),
              ),
              child: const Icon(LucideIcons.bot, color: Colors.white, size: 16),
            ),
            const SizedBox(width: 8),
            Text(
              'AI已帮你填好大部分',
              style: AppTextStyles.body.copyWith(
                color: AppColors.blue,
                fontWeight: FontWeight.w800,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class SegmentItem extends StatelessWidget {
  const SegmentItem({
    super.key,
    required this.label,
    required this.icon,
    this.selected = false,
  });

  final String label;
  final IconData icon;
  final bool selected;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 46,
      decoration: BoxDecoration(
        color: selected ? AppColors.blueSoft : Colors.transparent,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(
          color: selected
              ? AppColors.blue.withValues(alpha: 0.38)
              : AppColors.lineSoft,
        ),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon,
              size: 19, color: selected ? AppColors.blue : AppColors.muted),
          const SizedBox(width: 7),
          Flexible(
            child: Text(
              label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: AppTextStyles.sectionTitle.copyWith(
                color: selected ? AppColors.blue : AppColors.ink,
                fontSize: 14,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class EditSectionCard extends StatelessWidget {
  const EditSectionCard({
    super.key,
    required this.title,
    required this.icon,
    required this.children,
  });

  final String title;
  final IconData icon;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return CardPanel(
      padding: const EdgeInsets.all(13),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              SoftIconTile(
                icon: icon,
                color: AppColors.blue,
                background: AppColors.blueSoft,
                size: 36,
                iconSize: 19,
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  title,
                  style: AppTextStyles.title.copyWith(fontSize: 18),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          ...children,
        ],
      ),
    );
  }
}

class SoftIconTile extends StatelessWidget {
  const SoftIconTile({
    super.key,
    required this.icon,
    required this.color,
    required this.background,
    this.size = 46,
    this.iconSize = 23,
  });

  final IconData icon;
  final Color color;
  final Color background;
  final double size;
  final double iconSize;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(size / 3),
      ),
      child: Icon(icon, color: color, size: iconSize),
    );
  }
}

class SuccessEmblem extends StatelessWidget {
  const SuccessEmblem({super.key});

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 132,
      child: Stack(
        alignment: Alignment.center,
        children: [
          Container(
            width: 96,
            height: 96,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: RadialGradient(
                colors: [
                  AppColors.green.withValues(alpha: 0.22),
                  AppColors.blue.withValues(alpha: 0.16),
                  Colors.transparent,
                ],
              ),
            ),
          ),
          Container(
            width: 76,
            height: 76,
            decoration: BoxDecoration(
              color: AppColors.surface,
              shape: BoxShape.circle,
              border: Border.all(color: AppColors.green, width: 4),
              boxShadow: [
                BoxShadow(
                  color: AppColors.green.withValues(alpha: 0.2),
                  blurRadius: 24,
                  offset: const Offset(0, 10),
                ),
              ],
            ),
            child:
                const Icon(LucideIcons.check, color: AppColors.green, size: 40),
          ),
          const Positioned(
            left: 86,
            top: 34,
            child: Icon(LucideIcons.sparkles, color: AppColors.green, size: 18),
          ),
          const Positioned(
            right: 90,
            bottom: 32,
            child: Icon(LucideIcons.sparkles, color: AppColors.amber, size: 16),
          ),
        ],
      ),
    );
  }
}

class SummaryMetaItem extends StatelessWidget {
  const SummaryMetaItem({
    super.key,
    required this.icon,
    required this.label,
    required this.color,
  });

  final IconData icon;
  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Container(
          width: 24,
          height: 24,
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.12),
            borderRadius: BorderRadius.circular(10),
          ),
          child: Icon(icon, color: color, size: 15),
        ),
        const SizedBox(width: 6),
        Flexible(
          child: Text(
            label,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: AppTextStyles.body.copyWith(
              color: AppColors.muted,
              fontWeight: FontWeight.w700,
            ),
          ),
        ),
      ],
    );
  }
}

class SuccessActionCard extends StatelessWidget {
  const SuccessActionCard({
    super.key,
    required this.onAgain,
    required this.onLedger,
    required this.onHome,
  });

  final VoidCallback onAgain;
  final VoidCallback onLedger;
  final VoidCallback onHome;

  @override
  Widget build(BuildContext context) {
    return CardPanel(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('接下来可以', style: AppTextStyles.title.copyWith(fontSize: 18)),
          const SizedBox(height: 12),
          SuccessActionRow(
            label: '再记一笔',
            icon: LucideIcons.pencil,
            color: AppColors.blue,
            onTap: onAgain,
          ),
          const SizedBox(height: 8),
          SuccessActionRow(
            label: '查看账本',
            icon: LucideIcons.bookOpenCheck,
            color: AppColors.greenDark,
            onTap: onLedger,
          ),
          const SizedBox(height: 8),
          SuccessActionRow(
            label: '回到首页',
            icon: LucideIcons.home,
            color: AppColors.amber,
            onTap: onHome,
          ),
        ],
      ),
    );
  }
}

class SuccessActionRow extends StatelessWidget {
  const SuccessActionRow({
    super.key,
    required this.label,
    required this.icon,
    required this.color,
    required this.onTap,
  });

  final String label;
  final IconData icon;
  final Color color;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      child: Container(
        height: 48,
        padding: const EdgeInsets.symmetric(horizontal: 10),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: AppColors.line),
        ),
        child: Row(
          children: [
            Container(
              width: 34,
              height: 34,
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(icon, color: color, size: 19),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                label,
                style: AppTextStyles.body.copyWith(
                  fontSize: 15,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
            const Icon(
              LucideIcons.chevronRight,
              color: AppColors.subtle,
              size: 20,
            ),
          ],
        ),
      ),
    );
  }
}

class ManagerTipCard extends StatelessWidget {
  const ManagerTipCard({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.blueSoft,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.blue.withValues(alpha: 0.08)),
      ),
      child: Row(
        children: [
          const SoftIconTile(
            icon: LucideIcons.bot,
            color: AppColors.blue,
            background: AppColors.surface,
            size: 48,
            iconSize: 24,
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Text.rich(
              TextSpan(
                text: '小管家提示\n',
                style: AppTextStyles.sectionTitle.copyWith(
                  color: AppColors.blue,
                  fontSize: 15,
                ),
                children: [
                  TextSpan(
                    text: '下次可以直接说 买饲料花了多少钱',
                    style: AppTextStyles.body.copyWith(
                      color: AppColors.ink,
                      fontSize: 15,
                      height: 1.45,
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
