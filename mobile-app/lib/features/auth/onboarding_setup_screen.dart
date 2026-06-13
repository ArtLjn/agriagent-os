import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../data/location/location_service.dart';
import '../../data/repositories/profile_repository.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';
import 'auth_widgets.dart';

class OnboardingSetupScreen extends StatefulWidget {
  const OnboardingSetupScreen({
    super.key,
    required this.onStart,
    required this.onSkip,
    required this.profile,
    required this.location,
  });

  final VoidCallback onStart;
  final VoidCallback onSkip;
  final ProfileRepository profile;
  final LocationService location;

  @override
  State<OnboardingSetupScreen> createState() => _OnboardingSetupScreenState();
}

class _OnboardingSetupScreenState extends State<OnboardingSetupScreen> {
  final TextEditingController _farmController = TextEditingController();
  final TextEditingController _locationController = TextEditingController();
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
    _farmController.dispose();
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
    setState(() => _locating = false);
  }

  Future<void> _start() async {
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
      await widget.profile.updateFarmLocation(location: location);
      if (mounted) widget.onStart();
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _saving = false;
        _message = '经营地区保存失败，请稍后重试';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return AuthPage(
      bottomPadding: 22,
      children: [
        const SetupHero(),
        AuthSurfaceCard(
          padding: const EdgeInsets.all(18),
          children: [
            AuthInputField(
              label: '农场名称',
              placeholder: '请输入农场名称',
              icon: LucideIcons.building2,
              controller: _farmController,
              height: 48,
              labelGap: 8,
              labelFontSize: 14,
            ),
            const SizedBox(height: 14),
            AuthInputField(
              label: '经营地区',
              placeholder: '请选择经营地区',
              icon: LucideIcons.mapPin,
              controller: _locationController,
              height: 48,
              labelGap: 8,
              labelFontSize: 14,
              trailing: IconButton(
                tooltip: '使用当前位置',
                onPressed: _locating ? null : _useCurrentLocation,
                icon: Icon(
                  _locating ? LucideIcons.loaderCircle : LucideIcons.locateFixed,
                  size: 21,
                  color: _locating ? AppColors.subtle : AppColors.blue,
                ),
              ),
            ),
            Align(
              alignment: Alignment.centerRight,
              child: TextButton.icon(
                onPressed: _locating ? null : _useCurrentLocation,
                icon: const Icon(LucideIcons.locateFixed, size: 16),
                label: Text(_locating ? '定位中...' : '使用当前位置'),
              ),
            ),
            const SizedBox(height: 14),
            const AuthInputField(
              label: '身份',
              placeholder: '农场负责人',
              icon: LucideIcons.circleUserRound,
              height: 48,
              labelGap: 8,
              labelFontSize: 14,
              trailing: Icon(
                LucideIcons.chevronDown,
                size: 22,
                color: AppColors.subtle,
              ),
            ),
            if (_message != null) ...[
              const SizedBox(height: 8),
              Text(
                _message!,
                style: AppTextStyles.small.copyWith(color: AppColors.red),
              ),
            ],
            const SizedBox(height: 18),
            AuthPrimaryButton(label: _saving ? '保存中...' : '开始使用', onTap: _start),
            const SizedBox(height: 10),
            GestureDetector(
              behavior: HitTestBehavior.opaque,
              onTap: widget.onSkip,
              child: Center(
                child: Padding(
                  padding: const EdgeInsets.symmetric(vertical: 6),
                  child: Text(
                    '稍后再说',
                    style: AppTextStyles.body.copyWith(
                      color: AppColors.subtle,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
        const DataNotice(text: '可稍后在我的中修改', topPadding: 14),
      ],
    );
  }
}
