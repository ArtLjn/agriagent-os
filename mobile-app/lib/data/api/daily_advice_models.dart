part of 'api_models.dart';

class DailyAdvice {
  const DailyAdvice({
    this.cycleId,
    required this.preview,
    required this.items,
    required this.advice,
  });

  factory DailyAdvice.fromJson(Map<String, dynamic> json) {
    return DailyAdvice(
      cycleId: (json['cycle_id'] as num?)?.toInt(),
      preview: '${json['preview'] ?? ''}',
      items: (json['items'] as List<dynamic>? ?? [])
          .map((item) =>
              AdviceItem.fromJson(Map<String, dynamic>.from(item as Map)))
          .toList(),
      advice: '${json['advice'] ?? ''}',
    );
  }

  final int? cycleId;
  final String preview;
  final List<AdviceItem> items;
  final String advice;
}

class AdviceItem {
  const AdviceItem({
    required this.title,
    required this.detail,
    required this.priority,
    required this.icon,
    required this.id,
    required this.category,
    required this.level,
    required this.sourceType,
    this.sourceId,
    required this.compact,
    required this.detailView,
  });

  factory AdviceItem.fromJson(Map<String, dynamic> json) {
    final compactJson =
        Map<String, dynamic>.from(json['compact'] as Map? ?? {});
    final detailJson =
        Map<String, dynamic>.from(json['detail_view'] as Map? ?? {});
    final legacyTitle = '${json['title'] ?? ''}';
    final legacyDetail = '${json['detail'] ?? ''}';
    final compact = AdviceCompact.fromJson(
      compactJson,
      fallbackTitle: legacyTitle,
      fallbackSubtitle: legacyDetail,
      fallbackIcon: '${json['icon'] ?? ''}',
    );
    final detailView = AdviceDetailView.fromJson(
      detailJson,
      fallbackTitle: legacyTitle.isEmpty ? compact.title : legacyTitle,
      fallbackDescription:
          legacyDetail.isEmpty ? compact.subtitle : legacyDetail,
    );
    return AdviceItem(
      id: '${json['id'] ?? 'legacy-advice'}',
      category: '${json['category'] ?? 'record'}',
      level: '${json['level'] ?? 'normal'}',
      sourceType: '${json['source_type'] ?? 'legacy'}',
      sourceId: (json['source_id'] as num?)?.toInt(),
      title: '${json['title'] ?? compact.title}',
      detail: '${json['detail'] ?? compact.subtitle}',
      priority: (json['priority'] as num?)?.toInt() ?? 3,
      icon: '${json['icon'] ?? compact.icon}',
      compact: compact,
      detailView: detailView,
    );
  }

  final String id;
  final String category;
  final String level;
  final String sourceType;
  final int? sourceId;
  final String title;
  final String detail;
  final int priority;
  final String icon;
  final AdviceCompact compact;
  final AdviceDetailView detailView;
}

class AdviceCompact {
  const AdviceCompact({
    required this.title,
    required this.subtitle,
    required this.icon,
    required this.iconColor,
  });

  factory AdviceCompact.fromJson(
    Map<String, dynamic> json, {
    required String fallbackTitle,
    required String fallbackSubtitle,
    required String fallbackIcon,
  }) {
    return AdviceCompact(
      title: _text(json['title'], fallbackTitle),
      subtitle: _text(json['subtitle'], fallbackSubtitle),
      icon: _text(json['icon'], fallbackIcon),
      iconColor: _text(json['icon_color'], 'gray'),
    );
  }

  final String title;
  final String subtitle;
  final String icon;
  final String iconColor;
}

class AdviceDetailView {
  const AdviceDetailView({
    required this.title,
    required this.description,
    required this.heroBadges,
    required this.evidence,
    required this.steps,
    required this.related,
    required this.actions,
  });

  factory AdviceDetailView.fromJson(
    Map<String, dynamic> json, {
    required String fallbackTitle,
    required String fallbackDescription,
  }) {
    return AdviceDetailView(
      title: _text(json['title'], fallbackTitle),
      description: _text(json['description'], fallbackDescription),
      heroBadges: _listOfMaps(json['hero_badges'])
          .map(AdviceHeroBadge.fromJson)
          .toList(),
      evidence:
          _listOfMaps(json['evidence']).map(AdviceEvidence.fromJson).toList(),
      steps: _listOfMaps(json['steps']).map(AdviceStep.fromJson).toList(),
      related: _listOfMaps(json['related'])
          .map(AdviceRelatedEntry.fromJson)
          .toList(),
      actions: _listOfMaps(json['actions']).map(AdviceAction.fromJson).toList(),
    );
  }

  final String title;
  final String description;
  final List<AdviceHeroBadge> heroBadges;
  final List<AdviceEvidence> evidence;
  final List<AdviceStep> steps;
  final List<AdviceRelatedEntry> related;
  final List<AdviceAction> actions;
}

class AdviceHeroBadge {
  const AdviceHeroBadge({
    required this.label,
    required this.value,
    required this.level,
    this.icon,
  });

  factory AdviceHeroBadge.fromJson(Map<String, dynamic> json) {
    return AdviceHeroBadge(
      label: _text(json['label'], ''),
      value: _text(json['value'], ''),
      level: _text(json['level'], 'normal'),
      icon: json['icon'] as String?,
    );
  }

  final String label;
  final String value;
  final String level;
  final String? icon;
}

class AdviceEvidence {
  const AdviceEvidence({
    required this.title,
    required this.description,
    required this.sourceType,
    this.sourceId,
  });

  factory AdviceEvidence.fromJson(Map<String, dynamic> json) {
    return AdviceEvidence(
      title: _text(json['title'], ''),
      description: _text(json['description'], ''),
      sourceType: _text(json['source_type'], ''),
      sourceId: (json['source_id'] as num?)?.toInt(),
    );
  }

  final String title;
  final String description;
  final String sourceType;
  final int? sourceId;
}

class AdviceStep {
  const AdviceStep({
    required this.order,
    required this.title,
    required this.description,
  });

  factory AdviceStep.fromJson(Map<String, dynamic> json) {
    return AdviceStep(
      order: (json['order'] as num?)?.toInt() ?? 0,
      title: _text(json['title'], ''),
      description: _text(json['description'], ''),
    );
  }

  final int order;
  final String title;
  final String description;
}

class AdviceRelatedEntry {
  const AdviceRelatedEntry({
    required this.title,
    required this.description,
    required this.sourceType,
    this.sourceId,
  });

  factory AdviceRelatedEntry.fromJson(Map<String, dynamic> json) {
    return AdviceRelatedEntry(
      title: _text(json['title'], ''),
      description: _text(json['description'], ''),
      sourceType: _text(json['source_type'], ''),
      sourceId: (json['source_id'] as num?)?.toInt(),
    );
  }

  final String title;
  final String description;
  final String sourceType;
  final int? sourceId;
}

class AdviceAction {
  const AdviceAction({
    required this.type,
    required this.label,
    required this.payload,
  });

  factory AdviceAction.fromJson(Map<String, dynamic> json) {
    return AdviceAction(
      type: _text(json['type'], ''),
      label: _text(json['label'], ''),
      payload: Map<String, dynamic>.from(json['payload'] as Map? ?? {}),
    );
  }

  final String type;
  final String label;
  final Map<String, dynamic> payload;
}

String _text(Object? value, String fallback) {
  final text = '${value ?? ''}'.trim();
  return text.isEmpty ? fallback : text;
}

List<Map<String, dynamic>> _listOfMaps(Object? value) {
  final raw = value is List ? value : const [];
  return raw
      .whereType<Map>()
      .map((item) => Map<String, dynamic>.from(item))
      .toList();
}
