import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../data/api/api_models.dart';
import '../../data/repositories/business_repository.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';
import '../shell/bottom_tab_bar.dart';

const businessBlue = Color(0xFF1677FF);
const businessBlueDark = Color(0xFF2462D9);
const businessCardRadius = 18.0;
const businessGreen = Color(0xFF28B76C);
const businessGreenDark = Color(0xFF16885A);

class BusinessPageFrame extends StatelessWidget {
  const BusinessPageFrame({
    super.key,
    required this.title,
    required this.children,
    this.trailingIcon,
    this.trailingOnTap,
    this.bottomBar,
    this.showBottomTabs = false,
    this.onBottomTabChanged,
    this.bottomOverlay,
  });

  final String title;
  final IconData? trailingIcon;
  final VoidCallback? trailingOnTap;
  final List<Widget> children;
  final Widget? bottomBar;
  final bool showBottomTabs;
  final ValueChanged<int>? onBottomTabChanged;
  final Widget? bottomOverlay;

  @override
  Widget build(BuildContext context) {
    final bottomPadding = bottomBar != null
        ? 188.0
        : showBottomTabs
            ? 160.0
            : 32.0;
    return Scaffold(
      backgroundColor: AppColors.background,
      bottomNavigationBar: showBottomTabs
          ? AppBottomTabBar(
              selectedIndex: 1,
              onChanged: onBottomTabChanged ?? (_) {},
            )
          : bottomBar,
      body: Stack(
        children: [
          DecoratedBox(
            decoration: const BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [Colors.white, AppColors.background],
              ),
            ),
            child: SafeArea(
              child: SingleChildScrollView(
                padding: EdgeInsets.fromLTRB(14, 8, 14, bottomPadding),
                child: Center(
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 430),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        BusinessHeader(
                          title: title,
                          trailingIcon: trailingIcon,
                          trailingOnTap: trailingOnTap,
                        ),
                        const SizedBox(height: 16),
                        for (final child in children) ...[
                          child,
                          const SizedBox(height: 13),
                        ],
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
          if (bottomOverlay != null)
            Positioned(
              left: 14,
              right: 14,
              bottom: showBottomTabs ? 74 : 24,
              child: SafeArea(
                top: false,
                child: bottomOverlay!,
              ),
            ),
        ],
      ),
    );
  }
}

class BusinessHeader extends StatelessWidget {
  const BusinessHeader({
    super.key,
    required this.title,
    this.trailingIcon,
    this.trailingOnTap,
  });

  final String title;
  final IconData? trailingIcon;
  final VoidCallback? trailingOnTap;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 48,
      child: Row(
        children: [
          HeaderIconButton(
            icon: LucideIcons.chevronLeft,
            onTap: () {
              final navigator = Navigator.of(context);
              if (navigator.canPop()) navigator.pop();
            },
          ),
          Expanded(
            child: Text(
              title,
              textAlign: TextAlign.center,
              style: const TextStyle(
                color: AppColors.ink,
                fontSize: 22,
                height: 28 / 22,
                fontWeight: FontWeight.w800,
                letterSpacing: 0,
              ),
            ),
          ),
          HeaderIconButton(
            icon: trailingIcon ?? LucideIcons.moreHorizontal,
            onTap: trailingOnTap,
          ),
        ],
      ),
    );
  }
}

class BusinessHeroBanner extends StatelessWidget {
  const BusinessHeroBanner({
    super.key,
    required this.title,
    required this.subtitle,
    required this.asset,
    required this.accent,
    required this.tags,
    this.metric,
  });

  final String title;
  final String subtitle;
  final String asset;
  final Color accent;
  final List<String> tags;
  final String? metric;

  @override
  Widget build(BuildContext context) {
    final hasMetric = metric != null;
    return LayoutBuilder(
      builder: (context, constraints) {
        final isCompact = constraints.maxWidth < 380;
        return Container(
          height: hasMetric ? 188 : 166,
          padding: EdgeInsets.fromLTRB(
            isCompact ? 18 : 22,
            18,
            isCompact ? 16 : 18,
            16,
          ),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(20),
            gradient: const LinearGradient(
              begin: Alignment.centerLeft,
              end: Alignment.centerRight,
              colors: [
                Color(0xFFD8ECFF),
                Color(0xFFEEF7FF),
                Color(0xFFCFE4FF),
              ],
            ),
            border: Border.all(color: Colors.white),
            boxShadow: const [
              BoxShadow(
                color: Color(0x0F2F73F6),
                blurRadius: 24,
                offset: Offset(0, 12),
              ),
            ],
          ),
          clipBehavior: Clip.antiAlias,
          child: hasMetric
              ? _MetricHeroContent(
                  title: title,
                  subtitle: subtitle,
                  asset: asset,
                  accent: accent,
                  metric: metric!,
                )
              : _ManualLedgerHeroContent(
                  asset: asset,
                  accent: accent,
                  tags: tags.take(3).toList(),
                  compact: isCompact,
                ),
        );
      },
    );
  }
}

class _MetricHeroContent extends StatelessWidget {
  const _MetricHeroContent({
    required this.title,
    required this.subtitle,
    required this.asset,
    required this.accent,
    required this.metric,
  });

  final String title;
  final String subtitle;
  final String asset;
  final Color accent;
  final String metric;

  @override
  Widget build(BuildContext context) {
    return Stack(
      clipBehavior: Clip.hardEdge,
      children: [
        const Positioned(
          left: -28,
          bottom: -18,
          child: _SoftHill(width: 168, height: 54),
        ),
        const Positioned(
          left: 172,
          bottom: 18,
          child: _SoftSprout(),
        ),
        const Positioned(
          right: 154,
          top: 46,
          child: _YuanMark(),
        ),
        Positioned(
          right: -4,
          top: 2,
          bottom: 2,
          child: IgnorePointer(
            child: Image.asset(
              asset,
              width: 176,
              fit: BoxFit.contain,
              errorBuilder: (_, __, ___) => Icon(
                LucideIcons.leaf,
                size: 96,
                color: accent.withValues(alpha: 0.7),
              ),
            ),
          ),
        ),
        Positioned.fill(
          right: 150,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  color: businessBlueDark,
                  fontSize: 27,
                  height: 33 / 27,
                  fontWeight: FontWeight.w900,
                  letterSpacing: 0,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                subtitle,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: AppTextStyles.body.copyWith(
                  color: const Color(0xFF234B82),
                  fontSize: 15,
                  height: 21 / 15,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 12),
              Text(
                metric,
                style: TextStyle(
                  color: accent,
                  fontSize: 35,
                  height: 40 / 35,
                  fontWeight: FontWeight.w900,
                  letterSpacing: 0,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _ManualLedgerHeroContent extends StatelessWidget {
  const _ManualLedgerHeroContent({
    required this.asset,
    required this.accent,
    required this.tags,
    required this.compact,
  });

  final String asset;
  final Color accent;
  final List<String> tags;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    return Stack(
      clipBehavior: Clip.hardEdge,
      children: [
        Positioned(
          right: compact ? -34 : -24,
          top: -8,
          bottom: -10,
          child: IgnorePointer(
            child: Opacity(
              opacity: 0.82,
              child: Image.asset(
                asset,
                width: compact ? 176 : 198,
                fit: BoxFit.contain,
                errorBuilder: (_, __, ___) => Icon(
                  LucideIcons.leaf,
                  size: 92,
                  color: accent.withValues(alpha: 0.7),
                ),
              ),
            ),
          ),
        ),
        Positioned.fill(
          child: DecoratedBox(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.centerLeft,
                end: Alignment.centerRight,
                colors: [
                  Colors.white.withValues(alpha: 0.10),
                  Colors.white.withValues(alpha: 0.52),
                  Colors.white.withValues(alpha: 0.0),
                ],
                stops: const [0, 0.54, 1],
              ),
            ),
          ),
        ),
        Positioned(
          left: 0,
          right: compact ? 102 : 126,
          top: 10,
          child: Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (final tag in tags)
                SoftPill(
                  text: _compactBannerTag(tag),
                  color: accent,
                  background: Colors.white.withValues(alpha: 0.88),
                ),
            ],
          ),
        ),
        Positioned(
          left: 0,
          right: compact ? 118 : 148,
          bottom: 6,
          child: Text(
            '清晰记录每一笔农场收支',
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: AppTextStyles.title.copyWith(
              color: businessBlueDark,
              fontSize: compact ? 22 : 24,
              height: 30 / 24,
              fontWeight: FontWeight.w900,
            ),
          ),
        ),
      ],
    );
  }
}

class _YuanMark extends StatelessWidget {
  const _YuanMark();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 52,
      height: 52,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        border:
            Border.all(color: Colors.white.withValues(alpha: 0.72), width: 4),
        color: Colors.white.withValues(alpha: 0.12),
      ),
      child: Text(
        '￥',
        style: AppTextStyles.title.copyWith(
          color: Colors.white,
          fontSize: 25,
          fontWeight: FontWeight.w900,
        ),
      ),
    );
  }
}

class _SoftHill extends StatelessWidget {
  const _SoftHill({required this.width, required this.height});

  final double width;
  final double height;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: width,
      height: height,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(999),
        color: Colors.white.withValues(alpha: 0.20),
      ),
    );
  }
}

class _SoftSprout extends StatelessWidget {
  const _SoftSprout();

  @override
  Widget build(BuildContext context) {
    return Icon(
      LucideIcons.sprout,
      size: 56,
      color: businessBlue.withValues(alpha: 0.22),
    );
  }
}

class CycleSummaryBanner extends StatelessWidget {
  const CycleSummaryBanner({
    super.key,
    required this.asset,
    required this.cycleCount,
    required this.totalAreaText,
    required this.currentStageText,
    required this.activeCount,
    required this.plannedCount,
    required this.endedCount,
  });

  final String asset;
  final int cycleCount;
  final String totalAreaText;
  final String currentStageText;
  final int activeCount;
  final int plannedCount;
  final int endedCount;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 206,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFFDDF7ED), Color(0xFFEAF8FF), Color(0xFFDDF4E8)],
        ),
        border: Border.all(color: Colors.white),
        boxShadow: const [
          BoxShadow(
            color: Color(0x07101828),
            blurRadius: 16,
            offset: Offset(0, 7),
          ),
        ],
      ),
      clipBehavior: Clip.antiAlias,
      child: Stack(
        children: [
          Positioned(
            left: 0,
            right: 0,
            top: 0,
            bottom: 0,
            child: Opacity(
              opacity: 0.5,
              child: Image.asset(
                asset,
                fit: BoxFit.cover,
                alignment: Alignment.center,
                errorBuilder: (_, __, ___) => const SizedBox.shrink(),
              ),
            ),
          ),
          Positioned.fill(
            child: DecoratedBox(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  colors: [
                    Colors.white.withValues(alpha: 0.74),
                    Colors.white.withValues(alpha: 0.34),
                    Colors.white.withValues(alpha: 0.1),
                  ],
                  stops: const [0, 0.42, 1],
                ),
              ),
            ),
          ),
          Positioned(
            left: 10,
            right: 26,
            top: 12,
            height: 104,
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                Expanded(
                  child: _CycleMetric(label: '茬口数', value: '$cycleCount'),
                ),
                Expanded(
                  child: _CycleMetric(label: '总面积', value: totalAreaText),
                ),
                Expanded(
                  child: _CycleMetric(
                    label: '当前阶段',
                    value: currentStageText,
                    valueFontSize: 23,
                  ),
                ),
              ],
            ),
          ),
          Positioned(
            left: 18,
            right: 18,
            bottom: 14,
            child: _CycleStatusBar(
              activeCount: activeCount,
              plannedCount: plannedCount,
              endedCount: endedCount,
            ),
          ),
        ],
      ),
    );
  }
}

class _CycleStatusBar extends StatelessWidget {
  const _CycleStatusBar({
    required this.activeCount,
    required this.plannedCount,
    required this.endedCount,
  });

  final int activeCount;
  final int plannedCount;
  final int endedCount;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 50,
      padding: const EdgeInsets.symmetric(horizontal: 10),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.78),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: Colors.white.withValues(alpha: 0.86)),
      ),
      child: Row(
        children: [
          Expanded(
            child: _CycleChip(
              icon: LucideIcons.sprout,
              label: '在种 $activeCount',
              color: businessGreen,
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: _CycleChip(
              icon: LucideIcons.calendarDays,
              label: '计划 $plannedCount',
              color: businessBlue,
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: _CycleChip(
              icon: LucideIcons.circleCheck,
              label: '已结束 $endedCount',
              color: AppColors.subtle,
            ),
          ),
        ],
      ),
    );
  }
}

class TemplateLibraryBanner extends StatelessWidget {
  const TemplateLibraryBanner({
    super.key,
    required this.asset,
    required this.templateCount,
  });

  final String asset;
  final int templateCount;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 112,
      padding: const EdgeInsets.fromLTRB(18, 14, 18, 14),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        gradient: const LinearGradient(
          begin: Alignment.centerLeft,
          end: Alignment.centerRight,
          colors: [Color(0xFFE8F9EC), Color(0xFFF3FBFF), Color(0xFFE6F4FF)],
        ),
        border: Border.all(color: Colors.white),
        boxShadow: const [
          BoxShadow(
            color: Color(0x07101828),
            blurRadius: 16,
            offset: Offset(0, 7),
          ),
        ],
      ),
      clipBehavior: Clip.antiAlias,
      child: Stack(
        children: [
          const Positioned(
            right: -8,
            top: -24,
            child: _SoftCircle(size: 112, color: Color(0xFFE7F4FF)),
          ),
          Row(
            children: [
              SizedBox(
                width: 94,
                child: Transform.translate(
                  offset: const Offset(-8, 2),
                  child: Image.asset(
                    asset,
                    height: 82,
                    fit: BoxFit.contain,
                    errorBuilder: (_, __, ___) => const Icon(
                      LucideIcons.bookOpenText,
                      color: AppColors.green,
                      size: 64,
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.only(top: 6),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '模板库',
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: AppTextStyles.title.copyWith(
                          color: AppColors.ink,
                          fontSize: 24,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                      const SizedBox(height: 7),
                      Text(
                        templateCount == 0
                            ? '还没有作物模板，可新建模板后复用'
                            : '已创建 $templateCount 个作物模板，生成茬口更快',
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: AppTextStyles.body.copyWith(
                          color: AppColors.ink2,
                          fontSize: 13,
                          height: 18 / 13,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class WorkerSummaryBanner extends StatelessWidget {
  const WorkerSummaryBanner({
    super.key,
    required this.asset,
    required this.unpaidText,
    required this.workerCount,
    required this.monthlyWorkCount,
    required this.relatedCycleCount,
  });

  final String asset;
  final String unpaidText;
  final int workerCount;
  final int monthlyWorkCount;
  final int relatedCycleCount;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 166,
      padding: const EdgeInsets.fromLTRB(20, 18, 20, 14),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFFE5F8EE), Color(0xFFEAF8F4), Color(0xFFDFF5EE)],
        ),
        border: Border.all(color: Colors.white),
        boxShadow: const [
          BoxShadow(
            color: Color(0x07101828),
            blurRadius: 16,
            offset: Offset(0, 7),
          ),
        ],
      ),
      clipBehavior: Clip.antiAlias,
      child: Stack(
        children: [
          const Positioned(
            left: 4,
            top: 8,
            child: Icon(
              LucideIcons.usersRound,
              color: Color(0xFF12A06B),
              size: 30,
            ),
          ),
          Positioned(
            right: 10,
            top: 20,
            child: Opacity(
              opacity: 0.72,
              child: Image.asset(
                asset,
                width: 102,
                fit: BoxFit.contain,
                errorBuilder: (_, __, ___) => const SizedBox.shrink(),
              ),
            ),
          ),
          Positioned(
            left: 42,
            top: 7,
            child: Text(
              '全场人工',
              style: AppTextStyles.title.copyWith(
                color: const Color(0xFF12483C),
                fontSize: 22,
                fontWeight: FontWeight.w900,
              ),
            ),
          ),
          Positioned(
            left: 0,
            right: 0,
            bottom: 4,
            child: Row(
              children: [
                Expanded(
                  child: _WorkerMetric(
                    label: '未结',
                    value: unpaidText,
                    unit: '元',
                    color: AppColors.red,
                  ),
                ),
                const _VerticalSoftDivider(),
                Expanded(
                  child: _WorkerMetric(
                    label: '工人',
                    value: '$workerCount',
                    unit: '',
                    color: AppColors.ink,
                  ),
                ),
                const _VerticalSoftDivider(),
                Expanded(
                  child: _WorkerMetric(
                    label: '本月用工',
                    value: '$monthlyWorkCount',
                    unit: '',
                    color: AppColors.ink,
                  ),
                ),
                const _VerticalSoftDivider(),
                Expanded(
                  child: _WorkerMetric(
                    label: '相关茬口',
                    value: '$relatedCycleCount',
                    unit: '',
                    color: AppColors.ink,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _WorkerMetric extends StatelessWidget {
  const _WorkerMetric({
    required this.label,
    required this.value,
    required this.unit,
    required this.color,
  });

  final String label;
  final String value;
  final String unit;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        Text(
          label,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: AppTextStyles.small.copyWith(
            color: AppColors.ink2,
            fontSize: 13,
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(height: 8),
        RichText(
          maxLines: 1,
          text: TextSpan(
            text: value,
            style: AppTextStyles.metric.copyWith(
              color: color,
              fontSize: 27,
              fontWeight: FontWeight.w900,
            ),
            children: [
              if (unit.isNotEmpty)
                TextSpan(
                  text: unit,
                  style: AppTextStyles.body.copyWith(
                    color: color,
                    fontSize: 15,
                    fontWeight: FontWeight.w900,
                  ),
                ),
            ],
          ),
        ),
      ],
    );
  }
}

class _VerticalSoftDivider extends StatelessWidget {
  const _VerticalSoftDivider();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 1,
      height: 46,
      color: const Color(0xFFCFE7DF),
    );
  }
}

class _SoftCircle extends StatelessWidget {
  const _SoftCircle({required this.size, required this.color});

  final double size;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(shape: BoxShape.circle, color: color),
    );
  }
}

class _CycleMetric extends StatelessWidget {
  const _CycleMetric({
    required this.label,
    required this.value,
    this.valueFontSize = 25,
  });

  final String label;
  final String value;
  final double valueFontSize;

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Text(
          label,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          textAlign: TextAlign.center,
          style: AppTextStyles.small.copyWith(
            color: AppColors.ink2,
            fontSize: 13,
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(height: 6),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 2),
          child: FittedBox(
            fit: BoxFit.scaleDown,
            child: Text(
              value,
              maxLines: 1,
              textAlign: TextAlign.center,
              style: TextStyle(
                color: const Color(0xFF0A9B63),
                fontSize: valueFontSize,
                height: 30 / valueFontSize,
                fontWeight: FontWeight.w900,
                letterSpacing: 0,
              ),
            ),
          ),
        ),
      ],
    );
  }
}

class _CycleChip extends StatelessWidget {
  const _CycleChip({
    required this.icon,
    required this.label,
    required this.color,
  });

  final IconData icon;
  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 40,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.9),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, size: 15, color: color),
          const SizedBox(width: 5),
          Flexible(
            child: Text(
              label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: AppTextStyles.body.copyWith(
                color: AppColors.ink2,
                fontSize: 13,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

String _compactBannerTag(String tag) {
  return tag;
}

class BusinessCard extends StatelessWidget {
  const BusinessCard({
    super.key,
    required this.child,
    this.padding = EdgeInsets.zero,
  });

  final Widget child;
  final EdgeInsets padding;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: padding,
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(businessCardRadius),
        border: Border.all(color: AppColors.lineSoft),
        boxShadow: const [
          BoxShadow(
            color: Color(0x07101828),
            blurRadius: 16,
            offset: Offset(0, 7),
          ),
        ],
      ),
      child: child,
    );
  }
}

class BusinessCardHeader extends StatelessWidget {
  const BusinessCardHeader({
    super.key,
    required this.title,
    required this.icon,
    this.trailing,
  });

  final String title;
  final IconData icon;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 12),
      child: Row(
        children: [
          Container(
            width: 5,
            height: 24,
            decoration: BoxDecoration(
              color:
                  icon == LucideIcons.handCoins || icon == LucideIcons.userRound
                      ? businessBlue
                      : businessGreen,
              borderRadius: BorderRadius.circular(999),
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              title,
              style: AppTextStyles.sectionTitle.copyWith(
                fontSize: 18,
                height: 24 / 18,
                fontWeight: FontWeight.w900,
              ),
            ),
          ),
          if (trailing != null) trailing!,
        ],
      ),
    );
  }
}

class FormRowsCard extends StatelessWidget {
  const FormRowsCard({
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
    return BusinessCard(
      child: Column(
        children: [
          BusinessCardHeader(title: title, icon: icon),
          ...children,
        ],
      ),
    );
  }
}

class BusinessFormRow extends StatelessWidget {
  const BusinessFormRow({
    super.key,
    required this.label,
    required this.value,
    this.controller,
    this.large = false,
    this.chevron = false,
    this.keyboardType,
    this.onTap,
    this.hintText,
  });

  final String label;
  final String value;
  final TextEditingController? controller;
  final bool large;
  final bool chevron;
  final TextInputType? keyboardType;
  final VoidCallback? onTap;
  final String? hintText;

  @override
  Widget build(BuildContext context) {
    final field = controller == null
        ? Text(
            value,
            maxLines: large ? 2 : 1,
            overflow: TextOverflow.ellipsis,
            textAlign: TextAlign.right,
            style: TextStyle(
              color: AppColors.ink,
              fontSize: large ? 27 : 16,
              height: large ? 33 / 27 : 23 / 16,
              fontWeight: large ? FontWeight.w900 : FontWeight.w600,
              letterSpacing: 0,
            ),
          )
        : TextField(
            controller: controller,
            keyboardType: keyboardType,
            textAlign: TextAlign.right,
            style: TextStyle(
              color: AppColors.ink,
              fontSize: large ? 27 : 16,
              height: large ? 33 / 27 : 23 / 16,
              fontWeight: large ? FontWeight.w900 : FontWeight.w600,
              letterSpacing: 0,
            ),
            decoration: InputDecoration(
              hintText: hintText ?? (value.isEmpty ? null : value),
              hintStyle: AppTextStyles.body.copyWith(
                color: AppColors.subtle,
                fontWeight: FontWeight.w500,
              ),
              border: InputBorder.none,
              isDense: true,
              contentPadding: EdgeInsets.zero,
            ),
          );

    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(0),
      child: Container(
        constraints: BoxConstraints(minHeight: large ? 74 : 56),
        padding: const EdgeInsets.symmetric(horizontal: 16),
        decoration: const BoxDecoration(
          border: Border(bottom: BorderSide(color: AppColors.lineSoft)),
        ),
        child: Row(
          children: [
            SizedBox(
              width: 116,
              child: Text(
                label,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  color: large ? AppColors.ink : AppColors.muted,
                  fontSize: large ? 19 : 16,
                  height: 23 / 16,
                  fontWeight: large ? FontWeight.w800 : FontWeight.w600,
                  letterSpacing: 0,
                ),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(child: field),
            if (chevron) ...[
              const SizedBox(width: 8),
              const Icon(LucideIcons.chevronRight,
                  size: 22, color: AppColors.subtle),
            ],
          ],
        ),
      ),
    );
  }
}

Future<T?> showBusinessPickerSheet<T extends ApiRecord>({
  required BuildContext context,
  required String title,
  required Future<PageResult<T>> future,
  required String Function(T item) titleFor,
  required String Function(T item) subtitleFor,
  int? selectedId,
  String? subtitle,
  String loadingText = '正在加载',
  String errorText = '加载失败，请稍后再试',
  String emptyText = '暂无可选项',
  IconData Function(T item)? leadingIconFor,
  Color Function(T item)? accentFor,
}) {
  return showModalBottomSheet<T>(
    context: context,
    backgroundColor: Colors.transparent,
    isScrollControlled: true,
    builder: (context) {
      return SafeArea(
        top: false,
        child: Container(
          margin: const EdgeInsets.fromLTRB(12, 0, 12, 12),
          constraints: BoxConstraints(
            maxHeight: MediaQuery.sizeOf(context).height * 0.72,
          ),
          padding: const EdgeInsets.fromLTRB(16, 10, 16, 16),
          decoration: const BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.vertical(top: Radius.circular(26)),
            boxShadow: [
              BoxShadow(
                color: Color(0x1A10271D),
                blurRadius: 26,
                offset: Offset(0, -10),
              ),
            ],
          ),
          child: FutureBuilder<PageResult<T>>(
            future: future,
            builder: (context, snapshot) {
              final items = snapshot.data?.items ?? <T>[];
              return Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Center(
                    child: Container(
                      width: 38,
                      height: 4,
                      decoration: BoxDecoration(
                        color: AppColors.line,
                        borderRadius: BorderRadius.circular(999),
                      ),
                    ),
                  ),
                  const SizedBox(height: 14),
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              title,
                              style: AppTextStyles.sectionTitle.copyWith(
                                fontSize: 20,
                                height: 26 / 20,
                                fontWeight: FontWeight.w900,
                              ),
                            ),
                            if (subtitle != null) ...[
                              const SizedBox(height: 4),
                              Text(
                                subtitle,
                                style: AppTextStyles.body.copyWith(
                                  color: AppColors.muted,
                                  fontSize: 13,
                                  height: 18 / 13,
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                            ],
                          ],
                        ),
                      ),
                      IconButton(
                        visualDensity: VisualDensity.compact,
                        onPressed: () => Navigator.of(context).pop(),
                        icon: const Icon(LucideIcons.x, size: 20),
                      ),
                    ],
                  ),
                  const SizedBox(height: 14),
                  if (snapshot.connectionState == ConnectionState.waiting)
                    _BusinessPickerMessage(
                      text: loadingText,
                      loading: true,
                    )
                  else if (snapshot.hasError)
                    _BusinessPickerMessage(text: errorText)
                  else if (items.isEmpty)
                    _BusinessPickerMessage(text: emptyText)
                  else
                    Flexible(
                      child: ListView.separated(
                        shrinkWrap: true,
                        itemCount: items.length,
                        separatorBuilder: (_, __) => const SizedBox(height: 10),
                        itemBuilder: (context, index) {
                          final item = items[index];
                          final selected = item.id == selectedId;
                          final accent = accentFor?.call(item) ?? businessGreen;
                          return _BusinessPickerTile<T>(
                            item: item,
                            title: titleFor(item),
                            subtitle: subtitleFor(item),
                            selected: selected,
                            accent: accent,
                            icon:
                                leadingIconFor?.call(item) ?? LucideIcons.leaf,
                          );
                        },
                      ),
                    ),
                ],
              );
            },
          ),
        ),
      );
    },
  );
}

class _BusinessPickerTile<T extends ApiRecord> extends StatelessWidget {
  const _BusinessPickerTile({
    required this.item,
    required this.title,
    required this.subtitle,
    required this.selected,
    required this.accent,
    required this.icon,
  });

  final T item;
  final String title;
  final String subtitle;
  final bool selected;
  final Color accent;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: () => Navigator.of(context).pop(item),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 160),
          constraints: const BoxConstraints(minHeight: 72),
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color:
                selected ? accent.withValues(alpha: 0.08) : AppColors.surface3,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(
              color: selected
                  ? accent.withValues(alpha: 0.42)
                  : AppColors.lineSoft,
            ),
          ),
          child: Row(
            children: [
              Container(
                width: 42,
                height: 42,
                decoration: BoxDecoration(
                  color: accent.withValues(alpha: selected ? 0.16 : 0.10),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Icon(icon, color: accent, size: 21),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: AppTextStyles.listTitle.copyWith(
                        fontSize: 16,
                        height: 22 / 16,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                    if (subtitle.isNotEmpty) ...[
                      const SizedBox(height: 3),
                      Text(
                        subtitle,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: AppTextStyles.body.copyWith(
                          color: AppColors.muted,
                          fontSize: 13,
                          height: 18 / 13,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
              const SizedBox(width: 10),
              Container(
                width: 30,
                height: 30,
                decoration: BoxDecoration(
                  color: selected ? accent : Colors.white,
                  shape: BoxShape.circle,
                  border: Border.all(
                    color: selected
                        ? accent
                        : AppColors.subtle.withValues(alpha: 0.28),
                  ),
                ),
                child: Icon(
                  selected ? LucideIcons.check : LucideIcons.chevronRight,
                  color: selected ? Colors.white : AppColors.subtle,
                  size: selected ? 17 : 18,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _BusinessPickerMessage extends StatelessWidget {
  const _BusinessPickerMessage({required this.text, this.loading = false});

  final String text;
  final bool loading;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 28),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (loading) ...[
            const SizedBox(
              width: 24,
              height: 24,
              child: CircularProgressIndicator(strokeWidth: 2.6),
            ),
            const SizedBox(height: 12),
          ],
          Text(
            text,
            textAlign: TextAlign.center,
            style: AppTextStyles.body.copyWith(
              color: AppColors.muted,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }
}

class CyclePickerFormRow extends StatefulWidget {
  const CyclePickerFormRow({
    super.key,
    required this.repository,
    required this.selectedCycleId,
    required this.selectedCycleName,
    required this.onSelected,
    this.label = '关联茬口',
  });

  final BusinessRepository repository;
  final int? selectedCycleId;
  final String selectedCycleName;
  final ValueChanged<ApiRecord> onSelected;
  final String label;

  @override
  State<CyclePickerFormRow> createState() => _CyclePickerFormRowState();
}

class _CyclePickerFormRowState extends State<CyclePickerFormRow> {
  late Future<PageResult<ApiRecord>> _cyclesFuture;

  @override
  void initState() {
    super.initState();
    _cyclesFuture = widget.repository.listCycles();
  }

  Future<void> _showPicker() async {
    final result = await showBusinessPickerSheet<ApiRecord>(
      context: context,
      title: '选择茬口',
      subtitle: '选择后自动关联农事、工资和账本记录',
      future: _cyclesFuture,
      selectedId: widget.selectedCycleId,
      loadingText: '正在加载茬口',
      errorText: '茬口加载失败，请稍后再试',
      emptyText: '还没有茬口，先新建一个生产批次',
      titleFor: _cycleDisplayName,
      subtitleFor: _cycleSubtitle,
      leadingIconFor: (_) => LucideIcons.layers,
      accentFor: (_) => businessGreen,
    );
    if (result != null) widget.onSelected(result);
  }

  @override
  Widget build(BuildContext context) {
    final selectedText = widget.selectedCycleName.trim();
    return BusinessFormRow(
      label: widget.label,
      value: selectedText.isEmpty ? '选择茬口' : selectedText,
      chevron: true,
      onTap: _showPicker,
    );
  }
}

String _cycleDisplayName(ApiRecord record) {
  return _firstNonEmpty([record.json['name']], fallback: '未命名茬口');
}

String _cycleSubtitle(ApiRecord record) {
  final fieldName = _firstNonEmpty([record.json['field_name']]);
  final crop = _firstNonEmpty([record.json['crop_name']]);
  final stage = _firstNonEmpty([record.json['current_stage_name']]);
  final status = _firstNonEmpty([record.json['status']]);
  return [fieldName, crop, stage, status]
      .where((item) => item.isNotEmpty)
      .join(' · ');
}

String _firstNonEmpty(List<Object?> values, {String fallback = ''}) {
  for (final value in values) {
    final text = '$value'.trim();
    if (value != null && text.isNotEmpty && text != 'null') return text;
  }
  return fallback;
}

class SegmentedFormRow extends StatelessWidget {
  const SegmentedFormRow({
    super.key,
    required this.label,
    required this.options,
    required this.value,
    required this.onChanged,
  });

  final String label;
  final Map<String, String> options;
  final String value;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(minHeight: 66),
      padding: const EdgeInsets.fromLTRB(16, 9, 16, 9),
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: AppColors.lineSoft)),
      ),
      child: Row(
        children: [
          SizedBox(
            width: 116,
            child: Text(
              label,
              style: AppTextStyles.sectionTitle.copyWith(
                fontSize: 16,
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
          Expanded(
            child: Container(
              padding: const EdgeInsets.all(3),
              decoration: BoxDecoration(
                color: AppColors.surface2,
                borderRadius: BorderRadius.circular(15),
                border: Border.all(color: AppColors.line),
              ),
              child: Row(
                children: options.entries.map((entry) {
                  final selected = entry.key == value;
                  return Expanded(
                    child: GestureDetector(
                      onTap: () => onChanged(entry.key),
                      child: AnimatedContainer(
                        duration: const Duration(milliseconds: 160),
                        height: 40,
                        alignment: Alignment.center,
                        decoration: BoxDecoration(
                          color: selected ? businessBlue : Colors.transparent,
                          borderRadius: BorderRadius.circular(13),
                          boxShadow: selected
                              ? [
                                  BoxShadow(
                                    color: businessBlue.withValues(alpha: 0.22),
                                    blurRadius: 12,
                                    offset: const Offset(0, 5),
                                  ),
                                ]
                              : null,
                        ),
                        child: Text(
                          entry.value,
                          style: AppTextStyles.listTitle.copyWith(
                            color: selected ? Colors.white : AppColors.ink,
                            fontSize: 15,
                            fontWeight: FontWeight.w900,
                          ),
                        ),
                      ),
                    ),
                  );
                }).toList(),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class AssistEntryCard extends StatelessWidget {
  const AssistEntryCard({
    super.key,
    required this.text,
    this.icon = LucideIcons.sparkles,
  });

  final String text;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 58,
      padding: const EdgeInsets.symmetric(horizontal: 16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFFCFE1FF)),
        boxShadow: const [
          BoxShadow(
            color: Color(0x082F73F6),
            blurRadius: 16,
            offset: Offset(0, 8),
          ),
        ],
      ),
      child: Row(
        children: [
          Container(
            width: 38,
            height: 38,
            decoration: const BoxDecoration(
              shape: BoxShape.circle,
              gradient:
                  LinearGradient(colors: [businessBlue, Color(0xFF58A6FF)]),
            ),
            child: Icon(icon, color: Colors.white, size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              text,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: AppTextStyles.sectionTitle.copyWith(
                color: businessBlue,
                fontSize: 17,
                fontWeight: FontWeight.w900,
              ),
            ),
          ),
          const Icon(LucideIcons.chevronRight, color: businessBlue, size: 22),
        ],
      ),
    );
  }
}

class BottomActions extends StatelessWidget {
  const BottomActions({
    super.key,
    required this.secondaryLabel,
    required this.primaryLabel,
    required this.onPrimary,
    this.onSecondary,
    this.showTabs = false,
    this.onBottomTabChanged,
  });

  final String secondaryLabel;
  final String primaryLabel;
  final VoidCallback onPrimary;
  final VoidCallback? onSecondary;
  final bool showTabs;
  final ValueChanged<int>? onBottomTabChanged;

  @override
  Widget build(BuildContext context) {
    final actions = Container(
      padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
      decoration: const BoxDecoration(
        color: Colors.white,
        border: Border(top: BorderSide(color: AppColors.lineSoft)),
      ),
      child: Row(
        children: [
          Expanded(
            child: FilledActionButton(
              label: secondaryLabel,
              foreground: businessBlue,
              background: Colors.white,
              borderColor: businessBlue,
              onTap: onSecondary,
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: FilledActionButton(
              label: primaryLabel,
              foreground: Colors.white,
              background: businessBlue,
              borderColor: businessBlue,
              onTap: onPrimary,
            ),
          ),
        ],
      ),
    );

    if (!showTabs) return SafeArea(top: false, child: actions);
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        actions,
        AppBottomTabBar(
          selectedIndex: 1,
          onChanged: onBottomTabChanged ?? (_) {},
        ),
      ],
    );
  }
}

class FilledActionButton extends StatelessWidget {
  const FilledActionButton({
    super.key,
    required this.label,
    required this.foreground,
    required this.background,
    required this.borderColor,
    this.onTap,
    this.icon,
    this.height = 52,
  });

  final String label;
  final Color foreground;
  final Color background;
  final Color borderColor;
  final VoidCallback? onTap;
  final IconData? icon;
  final double height;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      child: Container(
        height: height,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: background,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: borderColor),
          boxShadow: background == businessBlue
              ? [
                  BoxShadow(
                    color: businessBlue.withValues(alpha: 0.22),
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
              Icon(icon, color: foreground, size: height < 44 ? 19 : 21),
              SizedBox(width: height < 44 ? 6 : 8),
            ],
            Text(
              label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: AppTextStyles.sectionTitle.copyWith(
                color: foreground,
                fontSize: height < 44 ? 14 : 16,
                fontWeight: FontWeight.w900,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class SoftPill extends StatelessWidget {
  const SoftPill({
    super.key,
    required this.text,
    required this.color,
    required this.background,
  });

  final String text;
  final Color color;
  final Color background;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: color.withValues(alpha: 0.12)),
      ),
      child: Text(
        text,
        style: AppTextStyles.small.copyWith(
          color: color,
          fontWeight: FontWeight.w900,
        ),
      ),
    );
  }
}

class AssetAvatar extends StatelessWidget {
  const AssetAvatar({
    super.key,
    required this.asset,
    this.size = 86,
    this.background = const Color(0xFFFAF8EF),
  });

  final String asset;
  final double size;
  final Color background;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: background,
        border: Border.all(color: AppColors.lineSoft),
      ),
      clipBehavior: Clip.antiAlias,
      child: Image.asset(
        asset,
        fit: BoxFit.cover,
        errorBuilder: (_, __, ___) => const Icon(
          LucideIcons.leaf,
          color: AppColors.green,
        ),
      ),
    );
  }
}

class CropIllustrationAvatar extends StatelessWidget {
  const CropIllustrationAvatar({
    super.key,
    required this.asset,
    this.size = 96,
  });

  final String asset;
  final double size;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      padding: const EdgeInsets.all(7),
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFFFFFCF3), Color(0xFFEFFAF1)],
        ),
        border: Border.all(color: const Color(0xFFE6EFE9)),
        boxShadow: const [
          BoxShadow(
            color: Color(0x0A163C2E),
            blurRadius: 12,
            offset: Offset(0, 5),
          ),
        ],
      ),
      clipBehavior: Clip.antiAlias,
      child: Image.asset(
        asset,
        fit: BoxFit.contain,
        errorBuilder: (_, __, ___) => const Icon(
          LucideIcons.leaf,
          color: AppColors.green,
        ),
      ),
    );
  }
}

class MiniStageTimeline extends StatelessWidget {
  const MiniStageTimeline({
    super.key,
    required this.stages,
    this.activeIndex = 2,
    this.compact = false,
  });

  final List<String> stages;
  final int activeIndex;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: compact ? 40 : 58,
      child: Row(
        children: [
          for (var index = 0; index < stages.length; index++) ...[
            Expanded(
              child: Column(
                children: [
                  Row(
                    children: [
                      if (index != 0)
                        Expanded(
                          child: Container(
                            height: 2,
                            color: index <= activeIndex
                                ? businessGreen
                                : AppColors.line,
                          ),
                        ),
                      Container(
                        width: compact ? 24 : 30,
                        height: compact ? 24 : 30,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: index <= activeIndex
                              ? AppColors.greenSoft
                              : AppColors.blueSoft,
                          border: Border.all(
                            color: index <= activeIndex
                                ? businessGreen.withValues(alpha: 0.28)
                                : businessBlue.withValues(alpha: 0.24),
                          ),
                        ),
                        child: Icon(
                          _stageIcon(index),
                          size: compact ? 13 : 15,
                          color: index <= activeIndex
                              ? businessGreen
                              : businessBlue,
                        ),
                      ),
                      if (index != stages.length - 1)
                        Expanded(
                          child: Container(
                            height: 2,
                            color: index < activeIndex
                                ? businessGreen
                                : AppColors.line,
                          ),
                        ),
                    ],
                  ),
                  if (!compact) ...[
                    const SizedBox(height: 5),
                    Text(
                      stages[index],
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      textAlign: TextAlign.center,
                      style: AppTextStyles.small.copyWith(
                        color: AppColors.ink2,
                        fontSize: 10,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  IconData _stageIcon(int index) {
    const icons = [
      LucideIcons.sprout,
      LucideIcons.leaf,
      LucideIcons.flower2,
      LucideIcons.apple,
      LucideIcons.circleDot,
      LucideIcons.badgeCheck,
    ];
    return icons[index % icons.length];
  }
}

class FloatingCreateButton extends StatelessWidget {
  const FloatingCreateButton({
    super.key,
    required this.label,
    required this.onTap,
  });

  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: GestureDetector(
        onTap: onTap,
        child: Container(
          width: 270,
          height: 52,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(999),
            gradient: const LinearGradient(
              colors: [Color(0xFF40C6B8), businessBlue],
            ),
            boxShadow: [
              BoxShadow(
                color: businessBlue.withValues(alpha: 0.24),
                blurRadius: 16,
                offset: const Offset(0, 8),
              ),
            ],
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(LucideIcons.circlePlus, color: Colors.white, size: 25),
              const SizedBox(width: 10),
              Text(
                label,
                style: AppTextStyles.sectionTitle.copyWith(
                  color: Colors.white,
                  fontSize: 18,
                  fontWeight: FontWeight.w900,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class CycleCreateFab extends StatelessWidget {
  const CycleCreateFab({
    super.key,
    required this.label,
    required this.onTap,
  });

  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.centerRight,
      child: GestureDetector(
        onTap: onTap,
        child: Container(
          height: 52,
          constraints: const BoxConstraints(minWidth: 148),
          padding: const EdgeInsets.fromLTRB(9, 0, 17, 0),
          decoration: BoxDecoration(
            color: const Color(0xFFF7FFF9).withValues(alpha: 0.98),
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: const Color(0xFFC8F1D7)),
            boxShadow: [
              BoxShadow(
                color: const Color(0xFF0F8F5A).withValues(alpha: 0.14),
                blurRadius: 20,
                offset: const Offset(0, 10),
              ),
            ],
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                width: 36,
                height: 36,
                decoration: BoxDecoration(
                  color: businessGreen,
                  borderRadius: BorderRadius.circular(12),
                  boxShadow: [
                    BoxShadow(
                      color: businessGreen.withValues(alpha: 0.24),
                      blurRadius: 12,
                      offset: const Offset(0, 6),
                    ),
                  ],
                ),
                child: const Icon(
                  LucideIcons.plus,
                  color: Colors.white,
                  size: 21,
                ),
              ),
              const SizedBox(width: 10),
              Text(
                label,
                style: AppTextStyles.sectionTitle.copyWith(
                  color: const Color(0xFF123D2D),
                  fontSize: 16,
                  fontWeight: FontWeight.w900,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class HeaderIconButton extends StatelessWidget {
  const HeaderIconButton({super.key, required this.icon, this.onTap});

  final IconData icon;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      child: SizedBox(
        width: 46,
        height: 46,
        child: Icon(icon, size: 27, color: AppColors.ink),
      ),
    );
  }
}

class SearchFieldCard extends StatelessWidget {
  const SearchFieldCard({
    super.key,
    required this.text,
    this.controller,
    this.onChanged,
  });

  final String text;
  final TextEditingController? controller;
  final ValueChanged<String>? onChanged;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 54,
      padding: const EdgeInsets.symmetric(horizontal: 15),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(17),
        border: Border.all(color: AppColors.lineSoft),
      ),
      child: Row(
        children: [
          const Icon(LucideIcons.search, size: 20, color: AppColors.subtle),
          const SizedBox(width: 10),
          Expanded(
            child: controller == null && onChanged == null
                ? Text(
                    text,
                    style: AppTextStyles.body.copyWith(
                      color: AppColors.subtle,
                      fontSize: 15,
                    ),
                  )
                : TextField(
                    controller: controller,
                    onChanged: onChanged,
                    textInputAction: TextInputAction.search,
                    decoration: InputDecoration.collapsed(
                      hintText: text,
                      hintStyle: AppTextStyles.body.copyWith(
                        color: AppColors.subtle,
                        fontSize: 15,
                      ),
                    ),
                    style: AppTextStyles.body.copyWith(
                      color: AppColors.ink,
                      fontSize: 15,
                    ),
                  ),
          ),
        ],
      ),
    );
  }
}

class ChipRail extends StatelessWidget {
  const ChipRail({
    super.key,
    required this.items,
    this.activeIndex = 0,
    this.activeColor = businessBlue,
    this.onSelected,
  });

  final List<String> items;
  final int activeIndex;
  final Color activeColor;
  final ValueChanged<int>? onSelected;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        children: [
          for (var i = 0; i < items.length; i++) ...[
            GestureDetector(
              behavior: HitTestBehavior.opaque,
              onTap: onSelected == null ? null : () => onSelected!(i),
              child: SoftPill(
                text: items[i],
                color: i == activeIndex ? activeColor : AppColors.ink2,
                background: i == activeIndex
                    ? activeColor.withValues(alpha: 0.10)
                    : Colors.white,
              ),
            ),
            const SizedBox(width: 8),
          ],
        ],
      ),
    );
  }
}

class LoadingCard extends StatelessWidget {
  const LoadingCard({super.key});

  @override
  Widget build(BuildContext context) {
    return const BusinessCard(
      padding: EdgeInsets.all(20),
      child: Center(child: CircularProgressIndicator(strokeWidth: 2.4)),
    );
  }
}

class AiLandscapeBanner extends StatelessWidget {
  const AiLandscapeBanner({
    super.key,
    required this.title,
    required this.subtitle,
    required this.asset,
    this.avatarAsset,
    this.accent = businessBlue,
  });

  final String title;
  final String subtitle;
  final String asset;
  final String? avatarAsset;
  final Color accent;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 120,
      padding: const EdgeInsets.fromLTRB(18, 16, 18, 14),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(18),
        gradient: LinearGradient(
          colors: [
            accent.withValues(alpha: 0.12),
            Colors.white,
            AppColors.green.withValues(alpha: 0.12),
          ],
        ),
        border: Border.all(color: Colors.white),
        boxShadow: const [
          BoxShadow(
            color: Color(0x07101828),
            blurRadius: 16,
            offset: Offset(0, 7),
          ),
        ],
      ),
      child: Stack(
        children: [
          Positioned(
            right: -18,
            bottom: -22,
            child: Opacity(
              opacity: avatarAsset == null ? 0.72 : 0.42,
              child: Image.asset(
                asset,
                width: avatarAsset == null ? 170 : 150,
                fit: BoxFit.contain,
                errorBuilder: (_, __, ___) => const SizedBox.shrink(),
              ),
            ),
          ),
          Row(
            children: [
              if (avatarAsset != null) ...[
                AssetAvatar(asset: avatarAsset!, size: 72),
                const SizedBox(width: 14),
              ] else ...[
                Container(
                  width: 56,
                  height: 56,
                  decoration: const BoxDecoration(
                    shape: BoxShape.circle,
                    gradient: LinearGradient(
                        colors: [businessBlue, Color(0xFF4BA6FF)]),
                  ),
                  child: const Icon(LucideIcons.sparkles,
                      color: Colors.white, size: 28),
                ),
                const SizedBox(width: 14),
              ],
              Expanded(
                child: Padding(
                  padding:
                      EdgeInsets.only(right: avatarAsset == null ? 76 : 72),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        title,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: AppTextStyles.title.copyWith(
                          fontSize: 22,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                      const SizedBox(height: 6),
                      Text(
                        subtitle,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: AppTextStyles.body.copyWith(
                          color: AppColors.muted,
                          fontSize: avatarAsset == null ? 15 : 14,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class StageEditRow extends StatelessWidget {
  const StageEditRow({
    super.key,
    required this.index,
    required this.title,
    required this.days,
    required this.color,
  });

  final int index;
  final String title;
  final String days;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 56,
      margin: const EdgeInsets.fromLTRB(14, 0, 14, 8),
      padding: const EdgeInsets.symmetric(horizontal: 14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.lineSoft),
      ),
      child: Row(
        children: [
          const Icon(LucideIcons.gripVertical,
              color: AppColors.subtle, size: 20),
          const SizedBox(width: 10),
          Container(
            width: 30,
            height: 30,
            alignment: Alignment.center,
            decoration: BoxDecoration(shape: BoxShape.circle, color: color),
            child: Text(
              '$index',
              style: AppTextStyles.sectionTitle.copyWith(
                color: Colors.white,
                fontWeight: FontWeight.w900,
              ),
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Text(
              title,
              style: AppTextStyles.sectionTitle.copyWith(
                fontSize: 17,
                fontWeight: FontWeight.w900,
              ),
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Row(
              children: [
                Icon(LucideIcons.calendarDays, color: color, size: 17),
                const SizedBox(width: 6),
                Text(
                  days,
                  style: AppTextStyles.sectionTitle.copyWith(
                    color: color,
                    fontSize: 16,
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class AddDashedRow extends StatelessWidget {
  const AddDashedRow({super.key, required this.label, this.onTap});

  final String label;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      child: Container(
        height: 52,
        margin: const EdgeInsets.fromLTRB(62, 2, 62, 16),
        alignment: Alignment.center,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: businessGreen.withValues(alpha: 0.52),
            style: BorderStyle.solid,
          ),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(LucideIcons.circlePlus, color: businessGreen, size: 24),
            const SizedBox(width: 8),
            Text(
              label,
              style: AppTextStyles.sectionTitle.copyWith(
                color: businessGreen,
                fontSize: 17,
                fontWeight: FontWeight.w900,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
