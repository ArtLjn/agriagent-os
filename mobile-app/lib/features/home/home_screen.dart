import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../shared/assets/app_assets.dart';
import '../../shared/widgets/card_panel.dart';
import '../../shared/widgets/reference_page.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';

part 'home_action_widgets.dart';
part 'home_cockpit_widgets.dart';
part 'home_insight_widgets.dart';
part 'home_suggestions_widgets.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const ReferencePage(
      headerTrailing: HeaderIconButton(icon: LucideIcons.bell, badge: '3'),
      children: [
        SizedBox(height: 14),
        _CockpitCard(),
        SizedBox(height: 14),
        _AiSuggestionsCard(),
        SizedBox(height: 14),
        _InsightGrid(),
        SizedBox(height: 14),
        _QuickActionStrip(),
      ],
    );
  }
}
