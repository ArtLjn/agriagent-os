import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../data/location/location_service.dart';
import '../../data/repositories/profile_repository.dart';
import '../../shared/app_identity.dart';
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
            _AiPreferenceCard(model: model),
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
    final location = await showDialog<String>(
      context: context,
      builder: (_) => _LocationEditDialog(
        initialValue: model.city == '未设置' ? '' : model.city,
        location: this.location,
      ),
    );
    if (location == null || location.isEmpty) return;
    await repository.updateFarmLocation(location: location);
    onUpdated();
  }
}

class _LocationEditDialog extends StatefulWidget {
  const _LocationEditDialog({
    required this.initialValue,
    this.location,
  });

  final String initialValue;
  final LocationService? location;

  @override
  State<_LocationEditDialog> createState() => _LocationEditDialogState();
}

class _LocationEditDialogState extends State<_LocationEditDialog> {
  late final TextEditingController _controller = TextEditingController(
    text: widget.initialValue,
  );
  bool _locating = false;
  String? _message;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _submit() {
    Navigator.of(context).pop(_controller.text.trim());
  }

  Future<void> _relocate() async {
    final service = widget.location;
    if (service == null || _locating) return;
    setState(() {
      _locating = true;
      _message = null;
    });
    final suggestion = await service.requestCurrentFarmLocation();
    if (!mounted) return;
    if (suggestion == null) {
      setState(() {
        _locating = false;
        _message = '无法获取当前位置';
      });
      return;
    }
    _controller.text = suggestion.city;
    Navigator.of(context).pop(suggestion.city);
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('经营地区'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          TextField(
            controller: _controller,
            autofocus: true,
            decoration: const InputDecoration(hintText: '请输入经营地区'),
            textInputAction: TextInputAction.done,
            onSubmitted: (_) => _submit(),
          ),
          if (widget.location != null) ...[
            const SizedBox(height: 12),
            OutlinedButton.icon(
              onPressed: _locating ? null : _relocate,
              icon: Icon(
                _locating ? LucideIcons.loaderCircle : LucideIcons.locateFixed,
                size: 17,
              ),
              label: Text(_locating ? '定位中...' : '重新定位'),
            ),
          ],
          if (_message != null) ...[
            const SizedBox(height: 8),
            Text(
              _message!,
              style: AppTextStyles.small.copyWith(color: AppColors.red),
            ),
          ],
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('取消'),
        ),
        FilledButton(
          onPressed: _submit,
          child: const Text('保存'),
        ),
      ],
    );
  }
}

class _AiPreferenceCard extends StatelessWidget {
  const _AiPreferenceCard({required this.model});

  final ProfileViewModel model;

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
          ),
          const Divider(height: 1, color: AppColors.lineSoft),
          const _ProfileOptionRow(
            icon: LucideIcons.chartNoAxesColumnIncreasing,
            color: AppColors.greenDark,
            background: AppColors.greenSoft,
            title: '分析深度',
            value: '标准',
          ),
          const Divider(height: 1, color: AppColors.lineSoft),
          const _ProfileOptionRow(
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
  const _SystemSettingsCard({
    required this.model,
    required this.repository,
    this.onLogout,
  });

  final ProfileViewModel model;
  final ProfileRepository repository;
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
            title: '关于${AppIdentity.displayName}',
            value: model.safeVersionLabel,
            onTap: () async {
              await Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) => AboutAppPage(
                    repository: repository,
                    initialModel: model,
                  ),
                ),
              );
            },
          ),
          if (onLogout != null) ...[
            const Divider(height: 1, color: AppColors.lineSoft),
            _ProfileOptionRow(
              icon: LucideIcons.logOut,
              color: AppColors.red,
              background: AppColors.redSoft,
              title: '退出登录',
              titleColor: AppColors.red,
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
    this.titleColor,
    this.valueColor = AppColors.muted,
    this.trailing,
    this.onTap,
  });

  final IconData icon;
  final Color color;
  final Color background;
  final String title;
  final String? value;
  final Color? titleColor;
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
              style: AppTextStyles.listTitle.copyWith(color: titleColor),
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

class AboutAppPage extends StatefulWidget {
  const AboutAppPage({
    super.key,
    required this.repository,
    this.initialModel,
  });

  final ProfileRepository repository;
  final ProfileViewModel? initialModel;

  @override
  State<AboutAppPage> createState() => _AboutAppPageState();
}

class _AboutAppPageState extends State<AboutAppPage> {
  late final ProfileController _controller = ProfileController(
    repository: widget.repository,
  );
  late Future<ProfileViewModel> _future = widget.initialModel == null
      ? _controller.load()
      : Future.value(widget.initialModel);
  bool _dialogShown = false;

  @override
  void initState() {
    super.initState();
    if (widget.initialModel != null) {
      _future = _refreshVersion();
    }
  }

  Future<ProfileViewModel> _refreshVersion() {
    return _controller.load();
  }

  Future<void> _checkAgain() async {
    setState(() {
      _dialogShown = false;
      _future = _refreshVersion();
    });
  }

  void _showUpdateDialog(ProfileViewModel model) {
    if (_dialogShown || !model.hasVersionUpdate) return;
    _dialogShown = true;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      showDialog<void>(
        context: context,
        barrierDismissible: true,
        builder: (context) => _VersionUpdateDialog(model: model),
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: FutureBuilder<ProfileViewModel>(
          future: _future,
          builder: (context, snapshot) {
            final model = snapshot.data ?? widget.initialModel;
            if (snapshot.connectionState != ConnectionState.done &&
                model == null) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snapshot.hasError || model == null) {
              return _AboutErrorState(onRetry: _checkAgain);
            }
            _showUpdateDialog(model);
            return SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(20, 8, 20, 40),
              child: Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 430),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      _AboutHeader(
                          onBack: () => Navigator.of(context).maybePop()),
                      const SizedBox(height: 18),
                      _AboutHeroCard(model: model),
                      const SizedBox(height: 14),
                      _AboutVersionCard(
                          model: model, onCheckAgain: _checkAgain),
                    ],
                  ),
                ),
              ),
            );
          },
        ),
      ),
    );
  }
}

class _AboutHeader extends StatelessWidget {
  const _AboutHeader({required this.onBack});

  final VoidCallback onBack;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 52,
      child: Row(
        children: [
          IconButton(
            onPressed: onBack,
            icon: const Icon(LucideIcons.arrowLeft),
            color: AppColors.ink,
          ),
          Expanded(
            child: Text(
              '关于${AppIdentity.displayName}',
              textAlign: TextAlign.center,
              style: AppTextStyles.title.copyWith(fontSize: 20),
            ),
          ),
          const SizedBox(width: 48),
        ],
      ),
    );
  }
}

class _AboutHeroCard extends StatelessWidget {
  const _AboutHeroCard({required this.model});

  final ProfileViewModel model;

  @override
  Widget build(BuildContext context) {
    return CardPanel(
      radius: 20,
      padding: const EdgeInsets.all(20),
      gradient: const LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [Colors.white, Color(0xFFEFF6FF)],
      ),
      borderColor: const Color(0xFFDDEBFF),
      child: Row(
        children: [
          const FarmBrandMark(size: 58),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(AppIdentity.displayName,
                    style: AppTextStyles.metric.copyWith(fontSize: 24)),
                const SizedBox(height: 4),
                Text(
                  AppIdentity.tagline,
                  style: AppTextStyles.body.copyWith(color: AppColors.muted),
                ),
                const SizedBox(height: 8),
                StatusPill(
                  text: model.safeVersionLabel,
                  color: AppColors.blue,
                  background: AppColors.blueSoft,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _AboutVersionCard extends StatelessWidget {
  const _AboutVersionCard({required this.model, required this.onCheckAgain});

  final ProfileViewModel model;
  final Future<void> Function() onCheckAgain;

  @override
  Widget build(BuildContext context) {
    return CardPanel(
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 4),
      child: Column(
        children: [
          _ProfileOptionRow(
            icon: LucideIcons.cloudDownload,
            color: AppColors.greenDark,
            background: AppColors.greenSoft,
            title: '版本更新检测',
            value: model.safeVersionStatus,
            valueColor: AppColors.greenDark,
            onTap: onCheckAgain,
          ),
          const Divider(height: 1, color: AppColors.lineSoft),
          _ProfileOptionRow(
            icon: LucideIcons.fileText,
            color: AppColors.amber,
            background: AppColors.amberSoft,
            title: '更新说明',
            value: model.updateSummary,
          ),
          const Divider(height: 1, color: AppColors.lineSoft),
          const _ProfileOptionRow(
            icon: LucideIcons.shieldCheck,
            color: AppColors.blue,
            background: AppColors.blueSoft,
            title: '隐私与协议',
            value: '查看',
          ),
          const Divider(height: 1, color: AppColors.lineSoft),
          const _ProfileOptionRow(
            icon: LucideIcons.headphones,
            color: AppColors.purple,
            background: AppColors.purpleSoft,
            title: '服务支持',
            value: '在线帮助',
          ),
        ],
      ),
    );
  }
}

class _VersionUpdateDialog extends StatelessWidget {
  const _VersionUpdateDialog({required this.model});

  final ProfileViewModel model;

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(22)),
      title: Row(
        children: [
          Icon(
            LucideIcons.sparkles,
            color: AppColors.blue,
          ),
          const SizedBox(width: 10),
          const Expanded(child: Text('发现新版本')),
        ],
      ),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            model.updateSummary,
            style:
                AppTextStyles.listTitle.copyWith(fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 10),
          Text(
            model.safeVersionChangelog,
            style: AppTextStyles.body.copyWith(color: AppColors.muted),
          ),
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('稍后'),
        ),
        FilledButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('立即更新'),
        ),
      ],
    );
  }
}

class _AboutErrorState extends StatelessWidget {
  const _AboutErrorState({required this.onRetry});

  final Future<void> Function() onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text('版本信息加载失败', style: AppTextStyles.listTitle),
          const SizedBox(height: 12),
          FilledButton(onPressed: onRetry, child: const Text('重试')),
        ],
      ),
    );
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
