import 'package:package_info_plus/package_info_plus.dart';

import '../../data/api/api_models.dart';
import '../../data/repositories/profile_repository.dart';

typedef CurrentVersionCodeResolver = Future<int> Function();

class ProfileController {
  ProfileController({
    required this.repository,
    int? currentVersionCode,
    CurrentVersionCodeResolver? currentVersionCodeResolver,
  }) : currentVersionCodeResolver = currentVersionCodeResolver ??
            (currentVersionCode == null
                ? _resolveInstalledVersionCode
                : (() async => currentVersionCode));

  final ProfileRepository repository;
  final CurrentVersionCodeResolver currentVersionCodeResolver;

  Future<ProfileViewModel> load() async {
    final AppUser user = await repository.getProfile();
    final UserSettings settings = await repository.getSettings();
    final currentVersionCode = await currentVersionCodeResolver();
    final VersionInfo version = await repository.checkVersion(
      currentVersionCode: currentVersionCode,
    );
    final city = _fallback(settings.defaultCity, '未设置');
    final hasUpdate = version.latestVersionCode > currentVersionCode;
    final latestVersion = _fallback(version.latestVersion, '');

    return ProfileViewModel(
      nickname: _fallback(user.nickname, '农友'),
      phone: _fallback(user.phone, '未绑定手机号'),
      role: _roleLabel(user.role),
      status: _statusLabel(user.status),
      city: city,
      weatherCity: city,
      latestVersion: latestVersion,
      hasVersionUpdate: hasUpdate,
      versionLabel: _versionLabel(version, hasUpdate),
      versionStatus: _versionStatus(version, hasUpdate),
      versionChangelog: _fallback(version.changelog, '暂无更新说明'),
      versionDownloadUrl: _fallback(version.downloadUrl, '暂无下载地址'),
    );
  }

  static Future<int> _resolveInstalledVersionCode() async {
    final info = await PackageInfo.fromPlatform();
    return int.tryParse(info.buildNumber.trim()) ?? 0;
  }

  String _versionLabel(VersionInfo version, bool hasUpdate) {
    if (version.latestVersion.isEmpty) return '版本未知';
    if (hasUpdate) return '发现新版本 ${version.latestVersion}';
    return '已是最新 ${version.latestVersion}';
  }

  String _versionStatus(VersionInfo version, bool hasUpdate) {
    if (hasUpdate) return '可更新';
    return '已是最新';
  }

  String _fallback(String? value, String fallback) {
    final text = value?.trim() ?? '';
    return text.isEmpty ? fallback : text;
  }

  String _roleLabel(String? value) {
    return switch ((value ?? '').trim().toLowerCase()) {
      'admin' => '管理员',
      'owner' => '负责人',
      'manager' => '管理员',
      'user' => '用户',
      '' => '用户',
      _ => value!.trim(),
    };
  }

  String _statusLabel(String? value) {
    return switch ((value ?? '').trim().toLowerCase()) {
      'active' => '正常',
      'inactive' => '未启用',
      'disabled' => '已停用',
      'pending' => '待确认',
      '' => '未知',
      _ => value!.trim(),
    };
  }
}

class ProfileViewModel {
  const ProfileViewModel({
    required this.nickname,
    required this.phone,
    required this.role,
    required this.status,
    required this.city,
    required this.weatherCity,
    this.latestVersion,
    this.hasVersionUpdate = false,
    this.versionLabel,
    this.versionStatus,
    this.versionChangelog,
    this.versionDownloadUrl,
  });

  final String nickname;
  final String phone;
  final String role;
  final String status;
  final String city;
  final String weatherCity;
  final String? latestVersion;
  final bool hasVersionUpdate;
  final String? versionLabel;
  final String? versionStatus;
  final String? versionChangelog;
  final String? versionDownloadUrl;

  String get safeLatestVersion => _safeText(latestVersion, '未知版本');

  String get safeVersionLabel => _safeText(versionLabel, '版本未知');

  String get safeVersionStatus => _safeText(versionStatus, '已是最新');

  String get safeVersionChangelog => _safeText(versionChangelog, '暂无更新说明');

  String get safeVersionDownloadUrl => _safeText(versionDownloadUrl, '暂无下载地址');

  String get latestVersionWithPrefix {
    final text = safeLatestVersion;
    if (text == '未知版本' || text.startsWith('v') || text.startsWith('V')) {
      return text;
    }
    return 'v$text';
  }

  String get updateSummary {
    if (!hasVersionUpdate) return '当前已是最新版本';
    return '更新至 $latestVersionWithPrefix';
  }

  static String _safeText(String? value, String fallback) {
    final text = value?.trim() ?? '';
    return text.isEmpty ? fallback : text;
  }
}
