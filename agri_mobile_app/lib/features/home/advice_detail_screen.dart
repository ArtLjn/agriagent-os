import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../data/api/api_models.dart';
import '../../shared/widgets/card_panel.dart';
import '../../shared/widgets/reference_page.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';
import '../shell/bottom_tab_bar.dart';
import 'home_controller.dart';

part 'advice_detail_sections.dart';

class AdviceDetailScreen extends StatelessWidget {
  const AdviceDetailScreen({
    super.key,
    required this.suggestion,
    this.onBottomTabChanged,
  });

  final HomeSuggestionViewModel suggestion;
  final ValueChanged<int>? onBottomTabChanged;

  void _handleBottomTabChanged(BuildContext context, int index) {
    Navigator.of(context).popUntil((route) => route.isFirst);
    onBottomTabChanged?.call(index);
  }

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
                  padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
                  child: Center(
                    child: ConstrainedBox(
                      constraints: const BoxConstraints(maxWidth: 430),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          _AdviceHeroCard(suggestion: suggestion),
                          const SizedBox(height: 12),
                          if (_EvidenceCard.hasContent(suggestion.item)) ...[
                            _EvidenceCard(item: suggestion.item),
                            const SizedBox(height: 12),
                          ],
                          if (_StepsCard.hasContent(suggestion.item)) ...[
                            _StepsCard(item: suggestion.item),
                            const SizedBox(height: 12),
                          ],
                          if (_RelatedCard.hasContent(suggestion.item))
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
        onBottomTabChanged: (index) => _handleBottomTabChanged(context, index),
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
              const SizedBox(width: 48),
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
      radius: 24,
      padding: const EdgeInsets.all(20),
      background: AppColors.blueSoft,
      borderColor: AppColors.blueSoft,
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          IconBadge(
              icon: _adviceIcon(item?.compact.icon),
              color: AppColors.blue,
              background: Colors.white,
              size: 40),
          const SizedBox(width: 12),
          StatusPill(
              text: _levelText(item?.level, item?.priority),
              color: _levelColor(item?.level, item?.priority),
              background: _levelBackground(item?.level, item?.priority)),
        ]),
        const SizedBox(height: 20),
        Text(
            detail?.title.isNotEmpty == true ? detail!.title : suggestion.title,
            style: AppTextStyles.title),
        const SizedBox(height: 12),
        Text(
            detail?.description.isNotEmpty == true
                ? detail!.description
                : suggestion.subtitle,
            style: AppTextStyles.body
                .copyWith(color: AppColors.ink2, height: 1.6)),
        if (metaChips.isNotEmpty) ...[
          const SizedBox(height: 20),
          Wrap(spacing: 8, runSpacing: 8, children: metaChips),
        ],
      ]),
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
      constraints: const BoxConstraints(minHeight: 44),
      padding: const EdgeInsets.symmetric(horizontal: 11),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.92),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.lineSoft),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 17, color: iconColor),
          const SizedBox(width: 5),
          Text(
            text,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: AppTextStyles.small.copyWith(
              color: AppColors.ink,
              fontSize: 13.5,
              fontWeight: FontWeight.w700,
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
    required this.onBottomTabChanged,
  });

  final HomeSuggestionViewModel suggestion;
  final ValueChanged<int> onBottomTabChanged;

  @override
  Widget build(BuildContext context) {
    final actions = suggestion.item?.detailView.actions
            .where(
                (action) => action.type.isNotEmpty && action.label.isNotEmpty)
            .toList() ??
        const <AdviceAction>[];
    return Material(
      color: AppColors.surface,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (actions.isNotEmpty) _AdviceActionBar(actions: actions),
          AppBottomTabBar(
            selectedIndex: 0,
            onChanged: onBottomTabChanged,
          ),
        ],
      ),
    );
  }
}
