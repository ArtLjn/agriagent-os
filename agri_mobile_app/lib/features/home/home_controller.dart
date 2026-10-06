import '../../data/api/api_models.dart';
import '../../data/repositories/dashboard_repository.dart';

class HomeController {
  HomeController({required this.repository});

  final DashboardRepository repository;

  Future<HomeViewModel> load() async {
    final results = await Future.wait<Object>([
      repository.getDailyAdvice(),
      _loadForecast(),
      repository.getWorkOrders(size: 10),
      repository.getUnsettledLaborSummary(),
    ]);
    final advice = results[0] as DailyAdvice;
    final forecast = Map<String, dynamic>.from(results[1] as Map);
    final workOrders = results[2] as PageResult<ApiRecord>;
    final labor = Map<String, dynamic>.from(results[3] as Map);
    final unpaid = _number(labor['total_unpaid'] ?? labor['unpaid_amount']);
    final weather = _weather(forecast);
    final weatherText = weather.text;
    final workOrderText = _metricValue(
      advice.overview,
      'work_order',
      fallback: '${workOrders.total}项',
    );
    final pendingText = _metricValue(
      advice.overview,
      'pending',
      fallback: unpaid > 0 ? '1项' : '0项',
    );
    final score = advice.overview.score.clamp(0, 100).toInt();
    final scoreText = advice.isAiGenerated ? score.toString() : '--';
    final scoreCaption = advice.isAiGenerated
        ? _nonEmpty(
            advice.overview.subtitle,
            fallback: '$weatherText · $workOrderText作业',
          )
        : '经营概览已同步，暂无每日 AI 评分';

    return HomeViewModel(
      headline: _nonEmpty(advice.preview, fallback: '暂无建议'),
      scoreText: scoreText,
      scoreCaption: scoreCaption,
      weatherText: weatherText,
      weatherCondition: weather.condition,
      weatherDescription: weather.description,
      workOrderCountText: workOrderText,
      pendingText: pendingText,
      adviceScoreText: advice.isAiGenerated ? '$score分' : '暂无评分',
      adviceScoreProgress: advice.isAiGenerated ? score / 100 : 0,
      unsettledLaborText: _money(unpaid),
      riskText: pendingText,
      riskSummaryText:
          _riskSummaryText(pendingText: pendingText, unpaid: unpaid),
      suggestions: _suggestions(advice),
    );
  }

  Future<Map<String, dynamic>> _loadForecast() async {
    try {
      return await repository.getForecast();
    } catch (_) {
      return const {};
    }
  }

  List<HomeSuggestionViewModel> _suggestions(DailyAdvice advice) {
    final items = advice.items
        .map(
          (item) => HomeSuggestionViewModel(
            title: _nonEmpty(item.compact.title, fallback: '暂无建议'),
            subtitle: _nonEmpty(item.compact.subtitle, fallback: advice.advice),
            item: item,
          ),
        )
        .toList();
    if (items.isNotEmpty) return items.take(3).toList();
    final text = _nonEmpty(advice.advice, fallback: advice.preview);
    if (text.isEmpty) {
      return const [
        HomeSuggestionViewModel(title: '暂无建议', subtitle: '稍后再来看看'),
      ];
    }
    return [HomeSuggestionViewModel(title: text, subtitle: '来自 AI 今日建议')];
  }

  ({String text, WeatherCondition condition, String description}) _weather(
      Map<String, dynamic> data) {
    Map<String, dynamic> today = const {};
    for (final key in const ['daily', 'days', 'forecast']) {
      final days = data[key];
      if (days is List && days.isNotEmpty && days.first is Map) {
        today = Map<String, dynamic>.from(days.first as Map);
        break;
      }
    }
    final description = _firstText(
        today, const ['desc', 'weather_text', 'weather', 'summary', 'text']);
    final condition =
        _weatherCondition(description, today['code'] ?? today['weather_code']);
    final current = data['current_weather'];
    final temperature = _temperature(data['current_temp']) ??
        (current is Map ? _temperature(current['temperature']) : null);
    final min = _temperature(today['min_c'] ?? today['min_temp']);
    final max = _temperature(today['max_c'] ?? today['max_temp']);
    // 首页优先展示当天最低/最高温；范围缺失时才使用实时气温。
    String text = min != null && max != null
        ? '${min.round()}～${max.round()}℃'
        : temperature == null
            ? ''
            : '${temperature.round()}℃';
    if (text.isEmpty) {
      text = description.isNotEmpty
          ? description
          : _firstText(data, const ['summary', 'text', 'weather']);
    }
    return (
      text: text.isEmpty ? '暂无天气' : text,
      condition: condition,
      description: description,
    );
  }

  num? _temperature(Object? value) {
    final parsed = value is num ? value : num.tryParse('$value');
    return parsed != null && parsed.isFinite ? parsed : null;
  }

  WeatherCondition _weatherCondition(String description, Object? code) {
    // 和风天气提供中文描述；Open-Meteo 提供 WMO 代码。不能通过气温猜天气。
    if (description.contains('雷')) return WeatherCondition.thunder;
    if (description.contains('雪') || description.contains('霰')) {
      return WeatherCondition.snow;
    }
    if (description.contains('雨')) return WeatherCondition.rain;
    if (description.contains('雾') || description.contains('霾')) {
      return WeatherCondition.fog;
    }
    if (description.contains('阴')) return WeatherCondition.cloudy;
    if (description.contains('云')) return WeatherCondition.partlyCloudy;
    if (description.contains('晴')) return WeatherCondition.sunny;
    return switch (int.tryParse('$code')) {
      0 => WeatherCondition.sunny,
      1 || 2 => WeatherCondition.partlyCloudy,
      3 => WeatherCondition.cloudy,
      45 || 48 => WeatherCondition.fog,
      51 ||
      53 ||
      55 ||
      61 ||
      63 ||
      65 ||
      66 ||
      67 ||
      80 ||
      81 ||
      82 =>
        WeatherCondition.rain,
      71 || 73 || 75 || 77 || 85 || 86 => WeatherCondition.snow,
      95 || 96 || 99 => WeatherCondition.thunder,
      _ => WeatherCondition.unknown,
    };
  }

  String _firstText(Map<String, dynamic> data, List<String> keys) {
    for (final key in keys) {
      final value = data[key];
      if (value != null && '$value'.trim().isNotEmpty) return '$value';
    }
    return '';
  }

  String _metricValue(
    DailyAdviceOverview overview,
    String key, {
    required String fallback,
  }) {
    for (final metric in overview.metrics) {
      if (metric.key == key && metric.value.trim().isNotEmpty) {
        return metric.value;
      }
    }
    return fallback;
  }

  String _riskSummaryText({required String pendingText, required num unpaid}) {
    final pendingCount = _number(pendingText.replaceAll('项', ''));
    if (pendingCount > 0) return '$pendingText待处理';
    if (unpaid > 0) return '1项资金待关注';
    return '暂无待关注';
  }
}

enum WeatherCondition {
  sunny,
  partlyCloudy,
  cloudy,
  rain,
  snow,
  thunder,
  fog,
  unknown
}

class HomeViewModel {
  const HomeViewModel({
    required this.headline,
    required this.scoreText,
    required this.scoreCaption,
    required this.weatherText,
    required this.weatherCondition,
    required this.weatherDescription,
    required this.workOrderCountText,
    required this.pendingText,
    required this.adviceScoreText,
    required this.adviceScoreProgress,
    required this.unsettledLaborText,
    required this.riskText,
    required this.riskSummaryText,
    required this.suggestions,
  });

  final String headline;
  final String scoreText;
  final String scoreCaption;
  final String weatherText;
  final WeatherCondition weatherCondition;
  final String weatherDescription;
  final String workOrderCountText;
  final String pendingText;
  final String adviceScoreText;
  final double adviceScoreProgress;
  final String unsettledLaborText;
  final String riskText;
  final String riskSummaryText;
  final List<HomeSuggestionViewModel> suggestions;
}

class HomeSuggestionViewModel {
  const HomeSuggestionViewModel({
    required this.title,
    required this.subtitle,
    this.item,
  });

  final String title;
  final String subtitle;
  final AdviceItem? item;
}

String _nonEmpty(String value, {required String fallback}) {
  final text = value.trim();
  return text.isEmpty ? fallback : text;
}

num _number(Object? value) {
  if (value is num) return value;
  return num.tryParse('$value') ?? 0;
}

String _money(num value) {
  final prefix = value < 0 ? '-¥' : '¥';
  final abs = value.abs();
  if (abs == abs.roundToDouble()) return '$prefix${abs.toInt()}';
  return '$prefix${abs.toStringAsFixed(2)}';
}
