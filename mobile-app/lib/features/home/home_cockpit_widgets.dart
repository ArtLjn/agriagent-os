part of 'home_screen.dart';

class _CockpitCard extends StatelessWidget {
  const _CockpitCard({required this.model});

  final HomeViewModel model;

  @override
  Widget build(BuildContext context) {
    return CardPanel(
      radius: 18,
      padding: const EdgeInsets.fromLTRB(18, 18, 18, 16),
      borderColor: const Color(0xFFDDEBFF),
      gradient: const LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [Color(0xFFF4FAFF), Color(0xFFEAF4FF)],
      ),
      child: Stack(
        clipBehavior: Clip.none,
        children: [
          Positioned(
            left: 76,
            right: -18,
            top: 22,
            height: 188,
            child: Opacity(
              opacity: 0.78,
              child: ShaderMask(
                blendMode: BlendMode.dstIn,
                shaderCallback: (bounds) {
                  return const LinearGradient(
                    begin: Alignment.topCenter,
                    end: Alignment.bottomCenter,
                    stops: [0, 0.72, 1],
                    colors: [Colors.white, Colors.white, Colors.transparent],
                  ).createShader(bounds);
                },
                child: Image.asset(
                  AppAssets.homeHeroFarm,
                  fit: BoxFit.cover,
                  alignment: Alignment.centerRight,
                ),
              ),
            ),
          ),
          Positioned.fill(
            child: DecoratedBox(
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(18),
                gradient: const LinearGradient(
                  begin: Alignment.centerLeft,
                  end: Alignment.centerRight,
                  stops: [0, 0.46, 1],
                  colors: [
                    Color(0xF7F4FAFF),
                    Color(0xC8F4FAFF),
                    Color(0x00F4FAFF),
                  ],
                ),
              ),
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  const Text('今日经营态势', style: AppTextStyles.dateTitle),
                  const SizedBox(width: 14),
                  StatusPill(
                    text: 'AI分析',
                    color: AppColors.blue,
                    background: AppColors.blueSoft.withValues(alpha: 0.72),
                  ),
                  const Spacer(),
                ],
              ),
              const SizedBox(height: 14),
              SizedBox(
                height: 126,
                child: Align(
                  alignment: Alignment.centerLeft,
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 250),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          model.scoreText,
                          style: AppTextStyles.metric.copyWith(
                            color: AppColors.blue,
                            fontSize: 62,
                            height: 0.98,
                          ),
                        ),
                        const SizedBox(height: 10),
                        Text(
                          model.scoreCaption,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: AppTextStyles.listTitle.copyWith(
                            color: AppColors.muted,
                            fontSize: 17,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 14),
              _CockpitMetrics(model: model),
            ],
          ),
        ],
      ),
    );
  }
}

class _CockpitMetrics extends StatelessWidget {
  const _CockpitMetrics({required this.model});

  final HomeViewModel model;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 82,
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.88),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.lineSoft),
      ),
      child: Row(
        children: [
          Expanded(
            child: _CockpitMetric(
              icon: LucideIcons.chartSpline,
              iconColor: AppColors.blue,
              iconBackground: AppColors.blueSoft,
              label: '天气',
              value: model.weatherText,
              valueColor: AppColors.blue,
            ),
          ),
          const _VerticalSoftDivider(),
          Expanded(
            child: _CockpitMetric(
              icon: LucideIcons.shield,
              iconColor: AppColors.greenDark,
              iconBackground: AppColors.greenSoft,
              label: '作业',
              value: model.workOrderCountText,
              valueColor: AppColors.greenDark,
            ),
          ),
          const _VerticalSoftDivider(),
          Expanded(
            child: _CockpitMetric(
              icon: LucideIcons.triangleAlert,
              iconColor: Color(0xFFFF6500),
              iconBackground: AppColors.amberSoft,
              label: '待处理',
              value: model.pendingText,
              valueColor: Color(0xFFFF6500),
            ),
          ),
        ],
      ),
    );
  }
}

class _CockpitMetric extends StatelessWidget {
  const _CockpitMetric({
    required this.icon,
    required this.iconColor,
    required this.iconBackground,
    required this.label,
    required this.value,
    required this.valueColor,
  });

  final IconData icon;
  final Color iconColor;
  final Color iconBackground;
  final String label;
  final String value;
  final Color valueColor;

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            IconBadge(
              icon: icon,
              color: iconColor,
              background: iconBackground,
              size: 28,
              iconSize: 16,
            ),
            const SizedBox(width: 5),
            Flexible(
              child: Text(
                label,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: AppTextStyles.small.copyWith(fontSize: 12),
              ),
            ),
          ],
        ),
        const SizedBox(height: 5),
        SizedBox(
          height: 28,
          child: Center(
            child: FittedBox(
              fit: BoxFit.scaleDown,
              alignment: Alignment.center,
              child: Text(
                value,
                maxLines: 1,
                style: AppTextStyles.dateTitle.copyWith(
                  color: valueColor,
                  fontSize: 23,
                  height: 1.1,
                ),
              ),
            ),
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
    return Container(width: 1, height: 44, color: AppColors.lineSoft);
  }
}
