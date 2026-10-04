import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';
import 'package:package_info_plus/package_info_plus.dart';

import '../../data/location/location_service.dart';
import '../../data/repositories/location_repository.dart';
import '../../data/repositories/profile_repository.dart';
import '../../shared/app_identity.dart';
import '../../shared/widgets/city_picker_sheet.dart';
import '../../shared/widgets/card_panel.dart';
import '../../shared/widgets/reference_page.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_theme.dart';
import '../../theme/app_text_styles.dart';
import 'profile_controller.dart';

part 'profile_header_widgets.dart';
part 'profile_settings_widgets.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({
    super.key,
    required this.repository,
    this.locations,
    this.location,
    this.onLogout,
  });

  final ProfileRepository repository;
  final LocationRepository? locations;
  final LocationService? location;
  final Future<void> Function()? onLogout;

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  late final ProfileController _controller = ProfileController(
    repository: widget.repository,
  );
  late Future<ProfileViewModel> _profileFuture = _controller.load();

  void _reloadProfile() {
    setState(() {
      _profileFuture = _controller.load();
      // 重试先监听异常，随后仍由 FutureBuilder 展示错误和恢复入口。
      _profileFuture.ignore();
    });
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<ProfileViewModel>(
      future: _profileFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const ReferencePage(title: '我的', subtitle: '账号与偏好', children: [
            SizedBox(height: 24),
            CardPanel(
                child: Padding(
                    padding: EdgeInsets.all(24),
                    child: Center(child: CircularProgressIndicator())))
          ]);
        }
        if (snapshot.hasError || !snapshot.hasData) {
          return ReferencePage(title: '我的', subtitle: '账号与偏好', children: [
            const SizedBox(height: 24),
            CardPanel(
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                  const Text('个人资料暂时无法加载', style: AppTextStyles.sectionTitle),
                  const SizedBox(height: 8),
                  const Text('请检查连接后重试。', style: AppTextStyles.body),
                  const SizedBox(height: 16),
                  FilledButton(
                      onPressed: _reloadProfile, child: const Text('重新加载'))
                ]))
          ]);
        }
        final model = snapshot.data!;
        return ReferencePage(
          title: '我的',
          subtitle: '账号与偏好',
          headerTrailing: IconButton(
              tooltip: '刷新资料',
              onPressed: _reloadProfile,
              icon: const Icon(LucideIcons.refreshCw)),
          children: [
            const SizedBox(height: 32),
            _ProfileCard(model: model),
            const SizedBox(height: 32),
            const Text('农场与助手', style: AppTextStyles.small),
            const SizedBox(height: 12),
            CardPanel(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Column(children: [
                  _LocationWeatherCard(
                      model: model,
                      repository: widget.repository,
                      locations: widget.locations,
                      location: widget.location,
                      onUpdated: _reloadProfile),
                  const Divider(height: 1),
                  _AiPreferenceCard(
                      model: model,
                      repository: widget.repository,
                      onUpdated: _reloadProfile),
                ])),
            const SizedBox(height: 24),
            const Text('应用', style: AppTextStyles.small),
            const SizedBox(height: 12),
            const _SystemSettingsCard(),
            if (widget.onLogout != null) ...[
              const SizedBox(height: 32),
              Align(
                  alignment: Alignment.centerLeft,
                  child: TextButton.icon(
                      onPressed: widget.onLogout,
                      icon: const Icon(LucideIcons.logOut, size: 18),
                      label: const Text('退出登录'),
                      style: TextButton.styleFrom(
                          foregroundColor: AppColors.muted))),
            ],
          ],
        );
      },
    );
  }
}

class _LocationWeatherCard extends StatelessWidget {
  const _LocationWeatherCard({
    required this.model,
    required this.repository,
    this.locations,
    this.location,
    required this.onUpdated,
  });

  final ProfileViewModel model;
  final ProfileRepository repository;
  final LocationRepository? locations;
  final LocationService? location;
  final VoidCallback onUpdated;

  @override
  Widget build(BuildContext context) {
    return _ProfileOptionRow(
      icon: LucideIcons.mapPin,
      title: '经营地区',
      value: model.city,
      onTap: () => _editLocation(context),
    );
  }

  Future<void> _editLocation(BuildContext context) async {
    final location = await showCityPickerSheet(
      context: context,
      selectedCity: model.city == '未设置' ? '' : model.city,
      onSearchLocations: locations == null
          ? null
          : (query) async {
              final results = await locations!.searchLocations(query);
              return results
                  .map((item) => CityPickerResult(
                        name: item.name,
                        latitude: item.latitude,
                        longitude: item.longitude,
                      ))
                  .toList();
            },
      onUseCurrentLocation: this.location == null
          ? null
          : () async {
              final suggestion =
                  await this.location!.requestCurrentFarmLocation();
              if (suggestion == null ||
                  suggestion.latitude == null ||
                  suggestion.longitude == null) {
                return null;
              }
              return CityPickerResult(
                name: suggestion.city,
                latitude: suggestion.latitude!,
                longitude: suggestion.longitude!,
              );
            },
    );
    if (location == null) return;
    await repository.updateFarmLocation(
      location: location.name,
      latitude: location.latitude,
      longitude: location.longitude,
    );
    onUpdated();
  }
}

class _AiPreferenceCard extends StatelessWidget {
  const _AiPreferenceCard({
    required this.model,
    required this.repository,
    required this.onUpdated,
  });

  final ProfileViewModel model;
  final ProfileRepository repository;
  final VoidCallback onUpdated;

  @override
  Widget build(BuildContext context) {
    return _ProfileOptionRow(
      icon: LucideIcons.messagesSquare,
      title: '回答风格',
      value: model.assistantRoleLabel,
      onTap: () => _editAssistantRole(context),
    );
  }

  Future<void> _editAssistantRole(BuildContext context) async {
    final role = await showAssistantRoleSheet(
      context: context,
      selectedValue: model.assistantRole,
    );
    if (role == null || role.value == model.assistantRole) return;
    await repository.updateSettings({'assistant_role': role.value});
    onUpdated();
  }
}
