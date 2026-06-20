import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../data/repositories/dashboard_repository.dart';
import '../../shared/assets/app_assets.dart';
import '../../shared/widgets/card_panel.dart';
import '../../shared/widgets/reference_page.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';
import 'advice_detail_screen.dart';
import 'home_controller.dart';

part 'home_action_widgets.dart';
part 'home_cockpit_widgets.dart';
part 'home_insight_widgets.dart';
part 'home_suggestions_widgets.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({
    super.key,
    required this.repository,
    this.onBottomTabChanged,
  });

  final DashboardRepository repository;
  final ValueChanged<int>? onBottomTabChanged;

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  late final Future<HomeViewModel> _future =
      HomeController(repository: widget.repository).load();

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<HomeViewModel>(
      future: _future,
      builder: (context, snapshot) {
        final model = snapshot.data;
        return ReferencePage(
          headerTrailing:
              const HeaderIconButton(icon: LucideIcons.bell, badge: '3'),
          children: [
            const SizedBox(height: 14),
            if (snapshot.connectionState != ConnectionState.done &&
                model == null)
              const _HomeStateCard(text: '加载中...')
            else if (snapshot.hasError && model == null)
              const _HomeStateCard(text: '数据加载失败，请稍后重试')
            else ...[
              _CockpitCard(model: model!),
              const SizedBox(height: 14),
              _AiSuggestionsCard(
                suggestions: model.suggestions,
                onBottomTabChanged: widget.onBottomTabChanged,
              ),
              const SizedBox(height: 14),
              _InsightGrid(model: model),
              const SizedBox(height: 14),
              const _QuickActionStrip(),
            ],
          ],
        );
      },
    );
  }
}

class _HomeStateCard extends StatelessWidget {
  const _HomeStateCard({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    return CardPanel(
      padding: const EdgeInsets.all(18),
      child: Text(text, style: AppTextStyles.body),
    );
  }
}
