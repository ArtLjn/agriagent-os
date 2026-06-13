import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../data/api/api_models.dart';
import '../../shared/assets/app_assets.dart';
import '../../shared/widgets/card_panel.dart';
import '../../shared/widgets/reference_page.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';
import '../shell/bottom_tab_bar.dart';
import 'home_controller.dart';

part 'advice_detail_sections.dart';

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
                          _EvidenceCard(item: suggestion.item),
                          const SizedBox(height: 14),
                          _StepsCard(item: suggestion.item),
                          const SizedBox(height: 14),
                          _RelatedCard(item: suggestion.item),
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
        suggestion: suggestion,
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
    final item = suggestion.item;
    final detail = item?.detailView;
    final badges = detail?.heroBadges
            .where((badge) => badge.value.trim().isNotEmpty)
            .take(3)
            .toList() ??
        const <AdviceHeroBadge>[];
    final metaChips = _heroMeta(badges);
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
                                detail?.title.isNotEmpty == true
                                    ? detail!.title
                                    : suggestion.title,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: AppTextStyles.title,
                              ),
                              const SizedBox(height: 8),
                              StatusPill(
                                text: _levelText(item?.level, item?.priority),
                                color: _levelColor(item?.level, item?.priority),
                                background: _levelBackground(
                                    item?.level, item?.priority),
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
                        detail?.description.isNotEmpty == true
                            ? detail!.description
                            : suggestion.subtitle,
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
                    Row(
                      children: [
                        for (var index = 0;
                            index < metaChips.length;
                            index++) ...[
                          Expanded(child: metaChips[index]),
                          if (index != metaChips.length - 1)
                            const SizedBox(width: 10),
                        ],
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

class _AdviceBottomArea extends StatelessWidget {
  const _AdviceBottomArea({
    required this.suggestion,
    required this.onHomeTap,
  });

  final HomeSuggestionViewModel suggestion;
  final VoidCallback onHomeTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: AppColors.surface,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          _AdviceActionBar(suggestion: suggestion),
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
