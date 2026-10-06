import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../data/location/location_service.dart';
import '../../data/repositories/location_repository.dart';
import '../../data/repositories/profile_repository.dart';
import '../../shared/widgets/city_picker_sheet.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';
import 'auth_widgets.dart';
import 'auth_entry_page.dart';

class OnboardingSetupScreen extends StatefulWidget {
  const OnboardingSetupScreen({
    super.key,
    required this.onStart,
    required this.onSkip,
    required this.profile,
    required this.location,
    required this.locations,
  });

  final VoidCallback onStart;
  final VoidCallback onSkip;
  final ProfileRepository profile;
  final LocationService location;
  final LocationRepository locations;

  @override
  State<OnboardingSetupScreen> createState() => _OnboardingSetupScreenState();
}

class _OnboardingSetupScreenState extends State<OnboardingSetupScreen> {
  final TextEditingController _locationController = TextEditingController();
  FarmLocationSuggestion? _locationSuggestion;
  CityPickerResult? _selectedLocation;
  bool _locating = false;
  bool _saving = false;
  String? _message;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _useCurrentLocation());
  }

  @override
  void dispose() {
    _locationController.dispose();
    super.dispose();
  }

  Future<void> _useCurrentLocation() async {
    if (_locating || _saving) return;
    setState(() {
      _locating = true;
      _message = null;
    });
    final suggestion = await widget.location.requestCurrentFarmLocation();
    if (!mounted) return;
    if (suggestion == null) {
      setState(() {
        _locating = false;
        _message = '无法获取当前位置，请手动填写经营地区';
      });
      return;
    }
    _locationController.text = suggestion.city;
    _locationSuggestion = suggestion;
    _selectedLocation = null;
    setState(() => _locating = false);
  }

  Future<void> _start() async {
    if (_saving) return;
    final location = _locationController.text.trim();
    if (location.isEmpty) {
      widget.onStart();
      return;
    }
    setState(() {
      _saving = true;
      _message = null;
    });
    try {
      await widget.profile.updateFarmLocation(
        location: location,
        latitude: _selectedLocation?.latitude ?? _locationSuggestion?.latitude,
        longitude:
            _selectedLocation?.longitude ?? _locationSuggestion?.longitude,
      );
      if (mounted) widget.onStart();
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _saving = false;
        _message = '经营地区保存失败，请稍后重试';
      });
    }
  }

  Future<void> _selectLocation() async {
    final location = await showCityPickerSheet(
      context: context,
      selectedCity: _locationController.text.trim(),
      onSearchLocations: _searchLocations,
    );
    if (location == null || !mounted) return;
    _locationController.text = location.name;
    _selectedLocation = location;
    _locationSuggestion = null;
    setState(() => _message = null);
  }

  Future<List<CityPickerResult>> _searchLocations(String query) async {
    final results = await widget.locations.searchLocations(query);
    return results
        .map((item) => CityPickerResult(
              name: item.name,
              latitude: item.latitude,
              longitude: item.longitude,
            ))
        .toList();
  }

  @override
  Widget build(BuildContext context) {
    return AuthEntryPage(
      title: '从你的农场开始',
      subtitle: '设置经营地区，让天气与农事建议更贴近你。',
      children: [
        AuthInputField(
          label: '经营地区',
          placeholder: '请选择经营地区',
          icon: LucideIcons.mapPin,
          controller: _locationController,
          readOnly: true,
          onTap: _saving ? null : _selectLocation,
          trailing: IconButton(
              tooltip: '选择经营地区',
              onPressed: _saving ? null : _selectLocation,
              icon: const Icon(LucideIcons.chevronDown, size: 20)),
        ),
        Align(
            alignment: Alignment.centerRight,
            child: TextButton.icon(
              onPressed: _locating || _saving ? null : _useCurrentLocation,
              icon: const Icon(LucideIcons.locateFixed, size: 16),
              label: Text(_locating ? '定位中…' : '使用当前位置'),
            )),
        const SizedBox(height: 8),
        Text('可稍后在“我的”中修改经营地区。',
            style: AppTextStyles.small.copyWith(color: AppColors.muted)),
        if (_message != null) ...[
          const SizedBox(height: 16),
          AuthErrorBanner(message: _message!)
        ],
        const SizedBox(height: 24),
        AuthEntrySubmitButton(
            label: '开始使用',
            loadingLabel: '保存中',
            isLoading: _saving,
            onTap: _start),
        const SizedBox(height: 8),
        TextButton(
            onPressed: _saving ? null : widget.onSkip,
            child: const Text('稍后再说')),
      ],
    );
  }
}
