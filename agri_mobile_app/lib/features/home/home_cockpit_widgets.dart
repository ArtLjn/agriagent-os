part of 'home_screen.dart';

class _FarmWelcomeCard extends StatelessWidget {
  const _FarmWelcomeCard({
    required this.weatherText,
    required this.weatherCondition,
    required this.weatherDescription,
  });

  final String weatherText;
  final WeatherCondition weatherCondition;
  final String weatherDescription;

  IconData get _weatherIcon => switch (weatherCondition) {
        WeatherCondition.sunny => LucideIcons.sun,
        WeatherCondition.partlyCloudy => LucideIcons.cloudSun,
        WeatherCondition.cloudy => LucideIcons.cloud,
        WeatherCondition.rain => LucideIcons.cloudRain,
        WeatherCondition.snow => LucideIcons.cloudSnow,
        WeatherCondition.thunder => LucideIcons.cloudLightning,
        WeatherCondition.fog => LucideIcons.cloudFog,
        WeatherCondition.unknown => LucideIcons.thermometer,
      };

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(24),
      child: ColoredBox(
        color: AppColors.blueSoft,
        child: LayoutBuilder(builder: (context, constraints) {
          return Stack(
            children: [
              Positioned(
                right: -20,
                bottom: -8,
                child: ExcludeSemantics(
                  child: Image.asset(AppAssets.homeHeroFarm,
                      width: constraints.maxWidth * 0.62,
                      height: 140,
                      fit: BoxFit.contain),
                ),
              ),
              Padding(
                padding: const EdgeInsets.all(24),
                child: SizedBox(
                  width: constraints.maxWidth * 0.58,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('打理好你的\n每一天',
                          style: AppTextStyles.title.copyWith(
                              fontSize: 24,
                              height: 1.4,
                              fontWeight: FontWeight.w600,
                              color: AppColors.navy)),
                      const SizedBox(height: 8),
                      Text('记录耕耘，经营有数',
                          style: AppTextStyles.small
                              .copyWith(color: AppColors.muted)),
                      const SizedBox(height: 24),
                      Semantics(
                        label: weatherText == '暂无天气'
                            ? '天气暂未更新'
                            : weatherDescription.isEmpty
                                ? '气温 $weatherText'
                                : '$weatherDescription，气温 $weatherText',
                        excludeSemantics: true,
                        child: Row(
                          children: [
                            Icon(_weatherIcon,
                                key: const ValueKey('home-weather-icon'),
                                color: AppColors.blue,
                                size: 16),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                  weatherText == '暂无天气'
                                      ? '天气暂未更新'
                                      : weatherText,
                                  style: AppTextStyles.small
                                      .copyWith(color: AppColors.navy)),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          );
        }),
      ),
    );
  }
}
