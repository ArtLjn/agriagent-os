import '../../data/api/api_models.dart';
import '../../data/repositories/profile_repository.dart';

class ProfileController {
  ProfileController({required this.repository});

  final ProfileRepository repository;

  Future<ProfileViewModel> load() async {
    final AppUser user = await repository.getProfile();
    final UserSettings settings = await repository.getSettings();
    final VersionInfo version = await repository.checkVersion();
    final city = _fallback(settings.defaultCity, '未设置');

    return ProfileViewModel(
      nickname: _fallback(user.nickname, '农友'),
      phone: _fallback(user.phone, '未绑定手机号'),
      role: _fallback(user.role, '用户'),
      status: _fallback(user.status, '未知'),
      city: city,
      weatherCity: city,
      versionLabel: version.latestVersion.isEmpty
          ? '版本未知'
          : '版本 ${version.latestVersion}',
    );
  }

  String _fallback(String? value, String fallback) {
    final text = value?.trim() ?? '';
    return text.isEmpty ? fallback : text;
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
    required this.versionLabel,
  });

  final String nickname;
  final String phone;
  final String role;
  final String status;
  final String city;
  final String weatherCity;
  final String versionLabel;
}
