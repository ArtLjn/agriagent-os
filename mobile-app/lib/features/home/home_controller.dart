import '../../data/api/api_models.dart';
import '../../data/repositories/dashboard_repository.dart';

class HomeController {
  HomeController({required this.repository});

  final DashboardRepository repository;

  Future<HomeViewModel> load() async {
    final results = await Future.wait<Object>([
      repository.getDailyAdvice(),
      repository.getForecast(),
      repository.getWorkOrders(size: 10),
      repository.getUnsettledLaborSummary(),
    ]);
    final advice = results[0] as DailyAdvice;
    final forecast = Map<String, dynamic>.from(results[1] as Map);
    final workOrders = results[2] as PageResult<ApiRecord>;
    final labor = Map<String, dynamic>.from(results[3] as Map);
    final unpaid = _number(labor['total_unpaid'] ?? labor['unpaid_amount']);

    return HomeViewModel(
      headline: _nonEmpty(advice.preview, fallback: '暂无建议'),
      scoreText: workOrders.total.toString(),
      scoreCaption: '${_weatherText(forecast)} · ${workOrders.total}项作业',
      weatherText: _weatherText(forecast),
      workOrderCountText: '${workOrders.total}项',
      unsettledLaborText: _money(unpaid),
      riskText: unpaid > 0 ? '1项' : '0项',
      suggestions: _suggestions(advice),
    );
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
    final location = _firstText(data, const ['location', 'city', 'name']);
    final summary = _firstText(data, const ['summary', 'text', 'weather']);
    final forecast = data['forecast'];
    String daily = '';
    if (forecast is List && forecast.isNotEmpty && forecast.first is Map) {
      daily = _firstText(
        Map<String, dynamic>.from(forecast.first as Map),
        const ['summary', 'text', 'weather'],
      );
    }
    final parts = [location, summary, daily].where((part) => part.isNotEmpty);
    return parts.isEmpty ? '暂无天气' : parts.join(' ');
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
