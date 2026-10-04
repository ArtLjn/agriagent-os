import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../data/api/api_client.dart';
import '../../data/repositories/dashboard_repository.dart';
import '../../shared/app_identity.dart';
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
  late Future<HomeViewModel> _future =
      HomeController(repository: widget.repository).load();

  Future<void> _refresh() async {
    final pending = HomeController(repository: widget.repository).load();
    setState(() {
      _future = pending;
    });
    try {
      await pending;
    } catch (_) {
      // FutureBuilder 展示错误及重试入口，下拉刷新只负责结束等待状态。
    }
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      bottom: false,
      child: RefreshIndicator(
        onRefresh: _refresh,
        color: AppColors.blue,
        child: SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.fromLTRB(24, 20, 24, 32),
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 430),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  _HomeHeader(onRefresh: _refresh),
                  const SizedBox(height: 24),
                  FutureBuilder<HomeViewModel>(
                    future: _future,
                    builder: (context, snapshot) {
                      final model = snapshot.data;
                      return Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          _FarmWelcomeCard(
                              weatherText: model?.weatherText ?? '暂无天气',
                              weatherCondition: model?.weatherCondition ??
                                  WeatherCondition.unknown,
                              weatherDescription:
                                  model?.weatherDescription ?? ''),
                          const SizedBox(height: 24),
                          _QuickActionStrip(
                              onBottomTabChanged: widget.onBottomTabChanged),
                          const SizedBox(height: 32),
                          if (snapshot.hasError && model == null)
                            _HomeStateCard(
                              message:
                                  ApiClient.userMessageFor(snapshot.error!),
                              onRetry: _refresh,
                            )
                          else if (model == null)
                            const _HomeStateCard()
                          else ...[
                            _BusinessOverview(
                                model: model,
                                onBottomTabChanged: widget.onBottomTabChanged),
                            const SizedBox(height: 24),
                            _AiSuggestionsCard(
                              suggestions: model.suggestions,
                              score: model.adviceScoreText,
                              onBottomTabChanged: widget.onBottomTabChanged,
                            ),
                          ],
                          const SizedBox(height: 24),
                          const Text('每一份耕耘，都值得被记住',
                              textAlign: TextAlign.center,
                              style: AppTextStyles.small),
                        ],
                      );
                    },
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _HomeHeader extends StatelessWidget {
  const _HomeHeader({required this.onRefresh});

  final VoidCallback onRefresh;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Image.asset(AppAssets.brandLogo, width: 40, height: 40),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(AppIdentity.displayName,
                  style: AppTextStyles.sectionTitle
                      .copyWith(fontWeight: FontWeight.w600)),
              const SizedBox(height: 4),
              const Text('你的农场经营助手', style: AppTextStyles.small),
            ],
          ),
        ),
        IconButton(
          tooltip: '更新首页',
          onPressed: onRefresh,
          color: AppColors.muted,
          style: IconButton.styleFrom(backgroundColor: AppColors.surface2),
          icon: const Icon(LucideIcons.refreshCw, size: 20),
        ),
      ],
    );
  }
}

class _HomeStateCard extends StatelessWidget {
  const _HomeStateCard({this.message, this.onRetry});

  final String? message;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    return CardPanel(
      shadow: false,
      radius: 24,
      padding: const EdgeInsets.all(24),
      child: Column(
        children: [
          if (message == null)
            const SizedBox.square(
                dimension: 24, child: CircularProgressIndicator(strokeWidth: 2))
          else
            const Icon(LucideIcons.wifiOff, color: AppColors.muted, size: 32),
          const SizedBox(height: 20),
          Text(message == null ? '正在整理农场记录' : '暂时没能更新首页',
              style: AppTextStyles.sectionTitle),
          if (message != null) ...[
            const SizedBox(height: 8),
            Text(message!,
                textAlign: TextAlign.center,
                style: AppTextStyles.body.copyWith(color: AppColors.muted)),
            const SizedBox(height: 20),
            OutlinedButton.icon(
              onPressed: onRetry,
              style: OutlinedButton.styleFrom(minimumSize: const Size(140, 48)),
              icon: const Icon(LucideIcons.refreshCw, size: 18),
              label: const Text('重新加载'),
            ),
          ],
        ],
      ),
    );
  }
}
