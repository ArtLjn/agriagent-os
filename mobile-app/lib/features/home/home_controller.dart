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
    final weatherText = _weatherText(forecast);

    return HomeViewModel(
      headline: _nonEmpty(advice.preview, fallback: '暂无建议'),
      scoreText: workOrders.total.toString(),
      scoreCaption: '$weatherText · ${workOrders.total}项作业',
      weatherText: weatherText,
      workOrderCountText: '${workOrders.total}项',
      unsettledLaborText: _money(unpaid),
      riskText: unpaid > 0 ? '1项' : '0项',
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
            title: _nonEmpty(item.title, fallback: '暂无建议'),
            subtitle: _nonEmpty(item.detail, fallback: advice.advice),
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

  String _weatherText(Map<String, dynamic> data) {
    final summary = _firstText(data, const ['summary', 'text', 'weather']);
    final forecast = data['forecast'];
    String daily = '';
    if (forecast is List && forecast.isNotEmpty && forecast.first is Map) {
      daily = _firstText(
        Map<String, dynamic>.from(forecast.first as Map),
        const ['summary', 'text', 'weather'],
      );
    }
    final backendDaily = _legacyDailyWeatherText(data['daily']);
    final parts =
        [summary, daily, backendDaily].where((part) => part.isNotEmpty);
    return parts.isEmpty ? '暂无天气' : parts.join(' ');
  }

  String _legacyDailyWeatherText(Object? dailyData) {
    if (dailyData is! Map) return '';
    final daily = Map<String, dynamic>.from(dailyData);
    final maxTemps = _listValue(daily['temperature_2m_max']);
    final precipitations = _listValue(daily['precipitation_sum']);
    final maxTemp = maxTemps.isNotEmpty ? _number(maxTemps.first) : 0;
    final precipitation =
        precipitations.isNotEmpty ? _number(precipitations.first) : 0;
    if (maxTemp == 0 && precipitation == 0) return '';

    final weather =
        _weatherLabel(maxTemp: maxTemp, precipitation: precipitation);
    return '$weather ${maxTemp.round()}℃';
  }

  List<dynamic> _listValue(Object? value) {
    if (value is List<dynamic>) return value;
    if (value is List) return List<dynamic>.from(value);
    return const [];
  }

  String _weatherLabel({required num maxTemp, required num precipitation}) {
    if (maxTemp >= 32) return '高温';
    if (precipitation >= 10) return '大雨';
    if (precipitation >= 1) return '小雨';
    return '晴';
  }

  String _firstText(Map<String, dynamic> data, List<String> keys) {
    for (final key in keys) {
      final value = data[key];
      if (value != null && '$value'.trim().isNotEmpty) return '$value';
    }
    return '';
  }
}

class HomeViewModel {
  const HomeViewModel({
    required this.headline,
    required this.scoreText,
    required this.scoreCaption,
    required this.weatherText,
    required this.workOrderCountText,
    required this.unsettledLaborText,
    required this.riskText,
    required this.suggestions,
  });

  final String headline;
  final String scoreText;
  final String scoreCaption;
  final String weatherText;
  final String workOrderCountText;
  final String unsettledLaborText;
  final String riskText;
  final List<HomeSuggestionViewModel> suggestions;
}

class HomeSuggestionViewModel {
  const HomeSuggestionViewModel({required this.title, required this.subtitle});

  final String title;
  final String subtitle;
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
