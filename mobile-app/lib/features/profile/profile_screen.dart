import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../data/repositories/profile_repository.dart';
import '../../shared/widgets/card_panel.dart';
import '../../shared/widgets/reference_page.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';
import 'profile_controller.dart';

part 'profile_header_widgets.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({
    super.key,
    required this.repository,
    this.onLogout,
  });

  final ProfileRepository repository;
  final Future<void> Function()? onLogout;

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  late final ProfileController _controller = ProfileController(
    repository: widget.repository,
  );
  late final Future<ProfileViewModel> _profileFuture = _controller.load();

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
            _LocationWeatherCard(model: model),
            const SizedBox(height: 14),
            const _AiPreferenceCard(),
            const SizedBox(height: 14),
            _SystemSettingsCard(model: model, onLogout: widget.onLogout),
            const SizedBox(height: 28),
            const _CompleteProfileButton(),
          ],
        );
      },
    );
  }
}

class _LocationWeatherCard extends StatelessWidget {
  const _LocationWeatherCard({required this.model});

  final ProfileViewModel model;

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
            title: '所在城市',
            value: model.city,
          ),
          const Divider(height: 1, color: AppColors.lineSoft),
          _ProfileOptionRow(
            icon: LucideIcons.cloudSun,
            color: AppColors.blue,
            background: AppColors.blueSoft,
            title: '默认天气',
            value: model.weatherCity,
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
}

class _AiPreferenceCard extends StatelessWidget {
  const _AiPreferenceCard();

  @override
  Widget build(BuildContext context) {
    return const CardPanel(
      padding: EdgeInsets.fromLTRB(18, 16, 18, 4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(LucideIcons.sparkles, size: 24, color: AppColors.blue),
              SizedBox(width: 10),
              Text('AI 偏好设置', style: AppTextStyles.dateTitle),
            ],
          ),
          SizedBox(height: 10),
          _ProfileOptionRow(
            icon: LucideIcons.messagesSquare,
            color: AppColors.blue,
            background: AppColors.blueSoft,
            title: '回答风格',
            value: '简洁实用',
          ),
          Divider(height: 1, color: AppColors.lineSoft),
          _ProfileOptionRow(
            icon: LucideIcons.chartNoAxesColumnIncreasing,
            color: AppColors.greenDark,
            background: AppColors.greenSoft,
            title: '分析深度',
            value: '标准',
          ),
          Divider(height: 1, color: AppColors.lineSoft),
          _ProfileOptionRow(
            icon: LucideIcons.wandSparkles,
            color: AppColors.purple,
            background: AppColors.purpleSoft,
            title: '自动生成报表',
            trailing: _SwitchPill(on: true),
          ),
        ],
      ),
    );
  }
}

class _SystemSettingsCard extends StatelessWidget {
  const _SystemSettingsCard({required this.model, this.onLogout});

  final ProfileViewModel model;
  final Future<void> Function()? onLogout;

  @override
  Widget build(BuildContext context) {
    return CardPanel(
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 4),
      child: Column(
        children: [
          const _ProfileOptionRow(
            icon: LucideIcons.cloudUpload,
            color: AppColors.greenDark,
            background: AppColors.greenSoft,
            title: '数据备份与恢复',
          ),
          const Divider(height: 1, color: AppColors.lineSoft),
          const _ProfileOptionRow(
            icon: LucideIcons.bell,
            color: AppColors.amber,
            background: AppColors.amberSoft,
            title: '消息通知',
          ),
          const Divider(height: 1, color: AppColors.lineSoft),
          _ProfileOptionRow(
            icon: LucideIcons.info,
            color: AppColors.blue,
            background: AppColors.blueSoft,
            title: '关于农场管家',
            value: model.versionLabel,
          ),
          if (onLogout != null) ...[
            const Divider(height: 1, color: AppColors.lineSoft),
            _ProfileOptionRow(
              icon: LucideIcons.logOut,
              color: AppColors.red,
              background: AppColors.redSoft,
              title: '退出登录',
              valueColor: AppColors.red,
              onTap: onLogout,
            ),
          ],
        ],
      ),
    );
  }
}

class _ProfileOptionRow extends StatelessWidget {
  const _ProfileOptionRow({
    required this.icon,
    required this.color,
    required this.background,
    required this.title,
    this.value,
    this.valueColor = AppColors.muted,
    this.trailing,
    this.onTap,
  });

  final IconData icon;
  final Color color;
  final Color background;
  final String title;
  final String? value;
  final Color valueColor;
  final Widget? trailing;
  final Future<void> Function()? onTap;

  @override
  Widget build(BuildContext context) {
    final content = SizedBox(
      height: 64,
      child: Row(
        children: [
          IconBadge(icon: icon, color: color, background: background, size: 36),
          const SizedBox(width: 16),
          Expanded(
            child: Text(
              title,
              style: AppTextStyles.listTitle.copyWith(
                color: onTap == null ? null : valueColor,
              ),
            ),
          ),
          if (trailing != null)
            trailing!
          else if (value != null)
            Flexible(
              child: Text(
                value!,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                textAlign: TextAlign.right,
                style: AppTextStyles.body.copyWith(color: valueColor),
              ),
            ),
          const SizedBox(width: 8),
          Icon(
            LucideIcons.chevronRight,
            size: 20,
            color: onTap == null ? AppColors.subtle : valueColor,
          ),
        ],
      ),
    );
    if (onTap == null) return content;
    return InkWell(onTap: onTap, child: content);
  }
}

class _SwitchPill extends StatelessWidget {
  const _SwitchPill({required this.on});

  final bool on;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 50,
      height: 28,
      padding: const EdgeInsets.all(3),
      decoration: BoxDecoration(
        color: on ? AppColors.greenDark : AppColors.line,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Align(
        alignment: on ? Alignment.centerRight : Alignment.centerLeft,
        child: Container(
          width: 22,
          height: 22,
          decoration: const BoxDecoration(
            color: Colors.white,
            shape: BoxShape.circle,
            boxShadow: [
              BoxShadow(
                color: Color(0x16000000),
                blurRadius: 8,
                offset: Offset(0, 2),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _CompleteProfileButton extends StatelessWidget {
  const _CompleteProfileButton();

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 52,
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: AppColors.greenDark, width: 1.2),
      ),
      child: Center(
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(
              LucideIcons.clipboardList,
              color: AppColors.greenDark,
              size: 22,
            ),
            const SizedBox(width: 10),
            Text(
              '完善农场资料',
              style: AppTextStyles.sectionTitle.copyWith(
                color: AppColors.greenDark,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
