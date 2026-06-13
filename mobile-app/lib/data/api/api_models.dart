part 'daily_advice_models.dart';

class AuthSession {
  const AuthSession({
    required this.token,
    required this.tokenType,
    required this.user,
  });

  factory AuthSession.fromJson(Map<String, dynamic> json) {
    return AuthSession(
      token: json['access_token'] as String? ?? '',
      tokenType: json['token_type'] as String? ?? 'bearer',
      user: AppUser.fromJson(json['user'] as Map<String, dynamic>? ?? {}),
    );
  }

  final String token;
  final String tokenType;
  final AppUser user;
}

class AppUser {
  const AppUser({
    required this.id,
    required this.phone,
    required this.nickname,
    required this.role,
    required this.status,
    this.avatarUrl,
    this.createdAt,
    this.farm,
  });

  factory AppUser.fromJson(Map<String, dynamic> json) {
    return AppUser(
      id: '${json['id'] ?? ''}',
      phone: '${json['phone'] ?? ''}',
      nickname: '${json['nickname'] ?? ''}',
      role: '${json['role'] ?? ''}',
      status: '${json['status'] ?? ''}',
      avatarUrl: json['avatar_url'] as String?,
      createdAt: DateTime.tryParse('${json['created_at'] ?? ''}'),
      farm: json['farm'] is Map
          ? FarmProfile.fromJson(Map<String, dynamic>.from(json['farm'] as Map))
          : null,
    );
  }

  final String id;
  final String phone;
  final String nickname;
  final String role;
  final String status;
  final String? avatarUrl;
  final DateTime? createdAt;
  final FarmProfile? farm;
}

class FarmProfile {
  const FarmProfile({
    required this.id,
    required this.name,
    this.location,
  });

  factory FarmProfile.fromJson(Map<String, dynamic> json) {
    return FarmProfile(
      id: (json['id'] as num?)?.toInt() ?? 0,
      name: '${json['name'] ?? ''}',
      location: json['location'] as String?,
    );
  }

  final int id;
  final String name;
  final String? location;
}

class PageResult<T> {
  const PageResult({required this.items, required this.total});

  factory PageResult.fromJson(
    Map<String, dynamic> json,
    T Function(Map<String, dynamic>) fromJson,
  ) {
    final rawItems = json['items'] as List<dynamic>? ?? [];
    return PageResult(
      items: rawItems
          .map((item) => fromJson(Map<String, dynamic>.from(item as Map)))
          .toList(),
      total: (json['total'] as num?)?.toInt() ?? rawItems.length,
    );
  }

  final List<T> items;
  final int total;
}

class UserSettings {
  const UserSettings({
    required this.displayName,
    this.defaultCity,
    this.defaultLat,
    this.defaultLon,
    this.assistantRole = 'warm',
  });

  factory UserSettings.fromJson(Map<String, dynamic> json) {
    return UserSettings(
      displayName: '${json['display_name'] ?? '农友'}',
      defaultCity: json['default_city'] as String?,
      defaultLat: (json['default_lat'] as num?)?.toDouble(),
      defaultLon: (json['default_lon'] as num?)?.toDouble(),
      assistantRole: '${json['assistant_role'] ?? 'warm'}',
    );
  }

  final String displayName;
  final String? defaultCity;
  final double? defaultLat;
  final double? defaultLon;
  final String assistantRole;
}

class VersionInfo {
  const VersionInfo({
    required this.latestVersion,
    required this.latestVersionCode,
    required this.downloadUrl,
    required this.changelog,
  });

  factory VersionInfo.fromJson(Map<String, dynamic> json) {
    return VersionInfo(
      latestVersion: '${json['latest_version'] ?? ''}',
      latestVersionCode: (json['latest_version_code'] as num?)?.toInt() ?? 0,
      downloadUrl: '${json['download_url'] ?? ''}',
      changelog: '${json['changelog'] ?? ''}',
    );
  }

  final String latestVersion;
  final int latestVersionCode;
  final String downloadUrl;
  final String changelog;
}

class ChatReply {
  const ChatReply({required this.reply, this.pendingAction});

  factory ChatReply.fromJson(Map<String, dynamic> json) {
    return ChatReply(
      reply: '${json['reply'] ?? ''}',
      pendingAction: json['pending_action'] as Map<String, dynamic>?,
    );
  }

  final String reply;
  final Map<String, dynamic>? pendingAction;
}

class ConversationSummary {
  const ConversationSummary({
    required this.id,
    required this.sessionId,
    required this.title,
    required this.preview,
    required this.status,
    required this.category,
  });

  factory ConversationSummary.fromJson(Map<String, dynamic> json) {
    return ConversationSummary(
      id: (json['id'] as num?)?.toInt() ?? 0,
      sessionId: '${json['session_id'] ?? ''}',
      title: '${json['title'] ?? ''}',
      preview: '${json['preview'] ?? ''}',
      status: '${json['status'] ?? ''}',
      category: '${json['category'] ?? '对话'}',
    );
  }

  final int id;
  final String sessionId;
  final String title;
  final String preview;
  final String status;
  final String category;
}

class ConversationMessage {
  const ConversationMessage({
    required this.id,
    required this.role,
    required this.content,
    this.skills = const [],
    this.pendingAction,
  });

  factory ConversationMessage.fromJson(Map<String, dynamic> json) {
    return ConversationMessage(
      id: (json['id'] as num?)?.toInt() ?? 0,
      role: '${json['role'] ?? ''}',
      content: '${json['content'] ?? ''}',
      skills:
          (json['skills'] as List<dynamic>? ?? []).map((v) => '$v').toList(),
      pendingAction: json['pending_action'] as Map<String, dynamic>?,
    );
  }

  final int id;
  final String role;
  final String content;
  final List<String> skills;
  final Map<String, dynamic>? pendingAction;
}

class YayaSkill {
  const YayaSkill({
    required this.key,
    required this.title,
    required this.description,
    required this.category,
    required this.icon,
    required this.iconColor,
    required this.recommended,
    required this.enabled,
  });

  factory YayaSkill.fromJson(Map<String, dynamic> json) {
    return YayaSkill(
      key: '${json['key'] ?? ''}',
      title: '${json['title'] ?? ''}',
      description: '${json['description'] ?? ''}',
      category: '${json['category'] ?? ''}',
      icon: '${json['icon'] ?? ''}',
      iconColor: '${json['icon_color'] ?? ''}',
      recommended: json['recommended'] == true,
      enabled: json['enabled'] != false,
    );
  }

  final String key;
  final String title;
  final String description;
  final String category;
  final String icon;
  final String iconColor;
  final bool recommended;
  final bool enabled;
}

class ApiRecord {
  const ApiRecord(this.json);

  factory ApiRecord.fromJson(Map<String, dynamic> json) => ApiRecord(json);

  final Map<String, dynamic> json;

  int? get id => (json['id'] as num?)?.toInt();
  String get name => '${json['name'] ?? json['title'] ?? ''}';
}

class SmartFillResult {
  const SmartFillResult({
    required this.scene,
    required this.draft,
    required this.missingFields,
    required this.warnings,
    this.traceId,
  });

  factory SmartFillResult.fromJson(Map<String, dynamic> json) {
    return SmartFillResult(
      scene: '${json['scene'] ?? ''}',
      draft: Map<String, dynamic>.from(json['draft'] as Map? ?? {}),
      missingFields: (json['missing_fields'] as List<dynamic>? ?? [])
          .map((v) => '$v')
          .toList(),
      warnings:
          (json['warnings'] as List<dynamic>? ?? []).map((v) => '$v').toList(),
      traceId: json['trace_id'] as String?,
    );
  }

  final String scene;
  final Map<String, dynamic> draft;
  final List<String> missingFields;
  final List<String> warnings;
  final String? traceId;
}
