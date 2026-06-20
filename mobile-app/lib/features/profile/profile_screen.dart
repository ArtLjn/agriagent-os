import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../data/location/location_service.dart';
import '../../data/repositories/profile_repository.dart';
import '../../shared/app_identity.dart';
import '../../shared/widgets/city_picker_sheet.dart';
import '../../shared/widgets/card_panel.dart';
import '../../shared/widgets/reference_page.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';
import 'profile_controller.dart';

part 'profile_header_widgets.dart';
part 'profile_settings_widgets.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({
    super.key,
    required this.repository,
    this.location,
    this.onLogout,
  });

  final ProfileRepository repository;
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
    });
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<ProfileViewModel>(
      future: _profileFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError || !snapshot.hasData) {
          return const Center(child: Text('个人资料加载失败，请稍后重试'));
        }
        final model = snapshot.data!;
        return ReferencePage(
          headerTrailing: const HeaderIconButton(icon: LucideIcons.settings),
          children: [
            const SizedBox(height: 14),
            _ProfileCard(model: model),
            const SizedBox(height: 14),
            _LocationWeatherCard(
              model: model,
              repository: widget.repository,
              location: widget.location,
              onUpdated: _reloadProfile,
            ),
            const SizedBox(height: 14),
            _AiPreferenceCard(
              model: model,
              repository: widget.repository,
              onUpdated: _reloadProfile,
            ),
            const SizedBox(height: 14),
            _SystemSettingsCard(
              model: model,
              repository: widget.repository,
              onLogout: widget.onLogout,
            ),
            const SizedBox(height: 28),
            const _CompleteProfileButton(),
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
    this.location,
    required this.onUpdated,
  });

  final ProfileViewModel model;
  final ProfileRepository repository;
  final LocationService? location;
  final VoidCallback onUpdated;

  @override
  Widget build(BuildContext context) {
    return CardPanel(
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 4),
      child: Column(
        children: [
          _ProfileOptionRow(
            icon: LucideIcons.mapPin,
            color: AppColors.blue,
            background: AppColors.blueSoft,
            title: '经营地区',
            value: model.city,
            onTap: () => _editLocation(context),
          ),
          const Divider(height: 1, color: AppColors.lineSoft),
          const _ProfileOptionRow(
            icon: LucideIcons.refreshCw,
            color: AppColors.greenDark,
            background: AppColors.greenSoft,
            title: '数据同步',
            value: '正常',
            valueColor: AppColors.greenDark,
          ),
        ],
      ),
    );
  }

  Future<void> _editLocation(BuildContext context) async {
    final location = await showCityPickerSheet(
      context: context,
      selectedCity: model.city == '未设置' ? '' : model.city,
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
    return CardPanel(
      padding: const EdgeInsets.fromLTRB(18, 16, 18, 4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(LucideIcons.sparkles, size: 24, color: AppColors.blue),
              SizedBox(width: 10),
              Text('AI 偏好设置', style: AppTextStyles.dateTitle),
            ],
          ),
          const SizedBox(height: 10),
          _ProfileOptionRow(
            icon: LucideIcons.messagesSquare,
            color: AppColors.blue,
            background: AppColors.blueSoft,
            title: '回答风格',
            value: model.assistantRoleLabel,
            onTap: () => _editAssistantRole(context),
          ),
          const Divider(height: 1, color: AppColors.lineSoft),
          const _ProfileOptionRow(
            icon: LucideIcons.chartNoAxesColumnIncreasing,
            color: AppColors.greenDark,
            background: AppColors.greenSoft,
            title: '分析深度',
            value: '待开放',
          ),
          const Divider(height: 1, color: AppColors.lineSoft),
          const _ProfileOptionRow(
            icon: LucideIcons.wandSparkles,
            color: AppColors.purple,
            background: AppColors.purpleSoft,
            title: '自动生成报表',
            value: '待开放',
          ),
        ],
      ),
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
