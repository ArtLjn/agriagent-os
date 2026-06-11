import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../shared/assets/app_assets.dart';
import '../../shared/widgets/card_panel.dart';
import '../../shared/widgets/reference_page.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';
import '../shell/bottom_tab_bar.dart';
import 'home_controller.dart';

class AdviceDetailScreen extends StatelessWidget {
  const AdviceDetailScreen({super.key, required this.suggestion});

  final HomeSuggestionViewModel suggestion;

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
          child: Column(
            children: [
              _AdviceAppBar(onBack: () => Navigator.of(context).pop()),
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.fromLTRB(20, 10, 20, 24),
                  child: Center(
                    child: ConstrainedBox(
                      constraints: const BoxConstraints(maxWidth: 430),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          _AdviceHeroCard(suggestion: suggestion),
                          const SizedBox(height: 14),
                          const _EvidenceCard(),
                          const SizedBox(height: 14),
                          const _StepsCard(),
                          const SizedBox(height: 14),
                          const _RelatedCard(),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
      bottomNavigationBar: _AdviceBottomArea(
        onHomeTap: () => Navigator.of(context).pop(),
      ),
    );
  }
}

class _AdviceAppBar extends StatelessWidget {
  const _AdviceAppBar({required this.onBack});

  final VoidCallback onBack;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 430),
        child: SizedBox(
          height: 58,
          child: Row(
            children: [
              IconButton(
                onPressed: onBack,
                icon: const Icon(LucideIcons.chevronLeft),
                color: AppColors.ink,
              ),
              const Expanded(
                child: Text(
                  '建议详情',
                  textAlign: TextAlign.center,
                  style: AppTextStyles.title,
                ),
              ),
              IconButton(
                onPressed: () {},
                icon: const Icon(LucideIcons.ellipsis),
                color: AppColors.ink,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _AdviceHeroCard extends StatelessWidget {
  const _AdviceHeroCard({required this.suggestion});

  final HomeSuggestionViewModel suggestion;

  @override
  Widget build(BuildContext context) {
    return CardPanel(
      radius: 18,
      padding: EdgeInsets.zero,
      borderColor: const Color(0xFFDDEBFF),
      gradient: const LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [Color(0xFFF4FAFF), Color(0xFFEAF4FF)],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(18),
        child: SizedBox(
          height: 248,
          child: Stack(
            children: [
              Positioned.fill(
                child: DecoratedBox(
                  decoration: const BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                      colors: [Color(0xFFF4FAFF), Color(0xFFEAF4FF)],
                    ),
                  ),
                ),
              ),
              Positioned(
                right: -34,
                top: 18,
                bottom: 10,
                width: 292,
                child: Opacity(
                  opacity: 0.76,
                  child: ShaderMask(
                    blendMode: BlendMode.dstIn,
                    shaderCallback: (bounds) {
                      return const LinearGradient(
                        begin: Alignment.centerLeft,
                        end: Alignment.centerRight,
                        stops: [0, 0.18, 0.78, 1],
                        colors: [
                          Colors.transparent,
                          Colors.white,
                          Colors.white,
                          Colors.transparent,
                        ],
                      ).createShader(bounds);
                    },
                    child: ShaderMask(
                      blendMode: BlendMode.dstIn,
                      shaderCallback: (bounds) {
                        return const LinearGradient(
                          begin: Alignment.topCenter,
                          end: Alignment.bottomCenter,
                          stops: [0, 0.12, 0.84, 1],
                          colors: [
                            Colors.transparent,
                            Colors.white,
                            Colors.white,
                            Colors.transparent,
                          ],
                        ).createShader(bounds);
                      },
                      child: Image.asset(
                        AppAssets.aiAdviceHarvesterHero,
                        fit: BoxFit.cover,
                        alignment: Alignment.centerRight,
                      ),
                    ),
                  ),
                ),
              ),
              Positioned.fill(
                child: DecoratedBox(
                  decoration: const BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.centerLeft,
                      end: Alignment.centerRight,
                      stops: [0, 0.5, 1],
                      colors: [
                        Color(0xFAF4FAFF),
                        Color(0xDDF4FAFF),
                        Color(0x3DF4FAFF),
                      ],
                    ),
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(18, 18, 18, 16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        IconBadge(
                          icon: LucideIcons.wheat,
                          color: AppColors.blue,
                          background: AppColors.blueSoft,
                          size: 52,
                          iconSize: 27,
                        ),
                        const SizedBox(width: 14),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                suggestion.title,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: AppTextStyles.title,
                              ),
                              const SizedBox(height: 8),
                              StatusPill(
                                text: '高优先级',
                                color: AppColors.red,
                                background: AppColors.redSoft,
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                    const Spacer(),
                    ConstrainedBox(
                      constraints: const BoxConstraints(maxWidth: 248),
                      child: Text(
                        suggestion.subtitle,
                        maxLines: 3,
                        overflow: TextOverflow.ellipsis,
                        style: AppTextStyles.body.copyWith(
                          color: AppColors.muted,
                          fontSize: 15,
                          height: 1.5,
                        ),
                      ),
                    ),
                    const Spacer(),
                    const Row(
                      children: [
                        Expanded(
                          child: _MetaChip(
                            icon: LucideIcons.mapPin,
                            iconColor: AppColors.blue,
                            text: '睢宁县',
                          ),
                        ),
                        SizedBox(width: 10),
                        Expanded(
                          child: _MetaChip(
                            icon: LucideIcons.thermometer,
                            iconColor: AppColors.red,
                            text: '高温 32℃',
                          ),
                        ),
                        SizedBox(width: 10),
                        Expanded(
                          child: _MetaChip(
                            icon: LucideIcons.clock3,
                            iconColor: AppColors.blue,
                            text: '预计 2 小时',
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _MetaChip extends StatelessWidget {
  const _MetaChip({
    required this.icon,
    required this.iconColor,
    required this.text,
  });

  final IconData icon;
  final Color iconColor;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 42,
      padding: const EdgeInsets.symmetric(horizontal: 10),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.92),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.lineSoft),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, size: 17, color: iconColor),
          const SizedBox(width: 5),
          Flexible(
            child: Text(
              text,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: AppTextStyles.small.copyWith(
                color: AppColors.ink,
                fontSize: 13,
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _EvidenceCard extends StatelessWidget {
  const _EvidenceCard();

  @override
  Widget build(BuildContext context) {
    return const _DetailSectionCard(
      icon: LucideIcons.sparkles,
      title: 'AI 判断依据',
      children: [
        _InfoRow(
          icon: LucideIcons.sprout,
          iconColor: AppColors.greenDark,
          iconBackground: AppColors.greenSoft,
          text: '成熟期：水稻已进入收割窗口',
        ),
        _InfoRow(
          icon: LucideIcons.sun,
          iconColor: AppColors.amber,
          iconBackground: AppColors.amberSoft,
          text: '天气：晴热少雨，适合晾晒',
        ),
        _InfoRow(
          icon: LucideIcons.clipboardList,
          iconColor: AppColors.blue,
          iconBackground: AppColors.blueSoft,
          text: '作业：今日已有 5 项待跟进',
          showDivider: false,
        ),
      ],
    );
  }
}

class _StepsCard extends StatelessWidget {
  const _StepsCard();

  @override
  Widget build(BuildContext context) {
    return const _DetailSectionCard(
      icon: LucideIcons.listChecks,
      title: '执行步骤',
      children: [
        _StepRow(index: 1, text: '检查收割机与镰刀'),
        _StepRow(index: 2, text: '确认装袋和运输工具'),
        _StepRow(index: 3, text: '避开午后高温安排人员'),
        _StepRow(index: 4, text: '收割后记录产量与人工', showDivider: false),
      ],
    );
  }
}

class _RelatedCard extends StatelessWidget {
  const _RelatedCard();

  @override
  Widget build(BuildContext context) {
    return const _DetailSectionCard(
      icon: LucideIcons.link,
      title: '关联事项',
      children: [
        _RelatedRow(
          icon: LucideIcons.userRound,
          iconColor: AppColors.greenDark,
          iconBackground: AppColors.greenSoft,
          title: '未结人工',
          value: '¥400',
          valueColor: AppColors.greenDark,
        ),
        _RelatedRow(
          icon: LucideIcons.triangleAlert,
          iconColor: Color(0xFFFF6500),
          iconBackground: AppColors.amberSoft,
          title: '风险预警',
          value: '1项待关注',
          valueColor: Color(0xFFFF6500),
          showDivider: false,
        ),
      ],
    );
  }
}

class _DetailSectionCard extends StatelessWidget {
  const _DetailSectionCard({
    required this.icon,
    required this.title,
    required this.children,
  });

  final IconData icon;
  final String title;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return CardPanel(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, size: 23, color: AppColors.blue),
              const SizedBox(width: 10),
              Text(title, style: AppTextStyles.dateTitle),
            ],
          ),
          const SizedBox(height: 12),
          ...children,
        ],
      ),
    );
  }
}

class _InfoRow extends StatelessWidget {
  const _InfoRow({
    required this.icon,
    required this.iconColor,
    required this.iconBackground,
    required this.text,
    this.showDivider = true,
  });

  final IconData icon;
  final Color iconColor;
  final Color iconBackground;
  final String text;
  final bool showDivider;

  @override
  Widget build(BuildContext context) {
    return _DividedRow(
      showDivider: showDivider,
      child: Row(
        children: [
          IconBadge(
            icon: icon,
            color: iconColor,
            background: iconBackground,
            size: 44,
            iconSize: 22,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              text,
              style: AppTextStyles.body,
            ),
          ),
        ],
      ),
    );
  }
}

class _StepRow extends StatelessWidget {
  const _StepRow({
    required this.index,
    required this.text,
    this.showDivider = true,
  });

  final int index;
  final String text;
  final bool showDivider;

  @override
  Widget build(BuildContext context) {
    return _DividedRow(
      showDivider: showDivider,
      child: Row(
        children: [
          Container(
            width: 28,
            height: 28,
            decoration: BoxDecoration(
              color: AppColors.blueSoft,
              borderRadius: BorderRadius.circular(999),
              border: Border.all(color: const Color(0xFFCFE0FF)),
            ),
            child: Center(
              child: Text(
                '$index',
                style: AppTextStyles.small.copyWith(
                  color: AppColors.blue,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ),
          ),
          const SizedBox(width: 12),
          Container(
            width: 22,
            height: 22,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(999),
              border: Border.all(color: AppColors.subtle, width: 1.4),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(child: Text(text, style: AppTextStyles.body)),
        ],
      ),
    );
  }
}

class _RelatedRow extends StatelessWidget {
  const _RelatedRow({
    required this.icon,
    required this.iconColor,
    required this.iconBackground,
    required this.title,
    required this.value,
    required this.valueColor,
    this.showDivider = true,
  });

  final IconData icon;
  final Color iconColor;
  final Color iconBackground;
  final String title;
  final String value;
  final Color valueColor;
  final bool showDivider;

  @override
  Widget build(BuildContext context) {
    return _DividedRow(
      showDivider: showDivider,
      child: Row(
        children: [
          IconBadge(
            icon: icon,
            color: iconColor,
            background: iconBackground,
            size: 46,
            iconSize: 23,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: AppTextStyles.listTitle),
                const SizedBox(height: 2),
                Text(
                  value,
                  style: AppTextStyles.listTitle.copyWith(color: valueColor),
                ),
              ],
            ),
          ),
          const Icon(
            LucideIcons.chevronRight,
            size: 22,
            color: AppColors.subtle,
          ),
        ],
      ),
    );
  }
}

class _DividedRow extends StatelessWidget {
  const _DividedRow({required this.child, required this.showDivider});

  final Widget child;
  final bool showDivider;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 10),
          child: child,
        ),
        if (showDivider) const Divider(height: 1, color: AppColors.lineSoft),
      ],
    );
  }
}

class _AdviceActionBar extends StatelessWidget {
  const _AdviceActionBar();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 12, 20, 14),
      decoration: const BoxDecoration(
        color: AppColors.surface,
        border: Border(top: BorderSide(color: AppColors.lineSoft)),
      ),
      child: SafeArea(
        top: false,
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 430),
            child: Row(
              children: [
                Expanded(
                  child: FilledButton.icon(
                    onPressed: () {},
                    icon: const Icon(LucideIcons.filePlus2, size: 20),
                    label: const Text('生成作业单'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: () {},
                    icon: const Icon(LucideIcons.bot, size: 20),
                    label: const Text('问问芽芽'),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _AdviceBottomArea extends StatelessWidget {
  const _AdviceBottomArea({required this.onHomeTap});

  final VoidCallback onHomeTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: AppColors.surface,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const _AdviceActionBar(),
          AppBottomTabBar(
            selectedIndex: 0,
            onChanged: (index) {
              if (index == 0) onHomeTap();
            },
          ),
        ],
      ),
    );
  }
}
