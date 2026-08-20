part of 'profile_screen.dart';

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
            value: '待开放',
          ),
          const Divider(height: 1, color: AppColors.lineSoft),
          const _ProfileOptionRow(
            icon: LucideIcons.bell,
            color: AppColors.amber,
            background: AppColors.amberSoft,
            title: '消息通知',
            value: '待开放',
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
    this.onTap,
  });

  final IconData icon;
  final Color color;
  final Color background;
  final String title;
  final String? value;
  final Color? titleColor;
  final Color valueColor;
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
          if (value != null)
            Flexible(
              child: Text(
                value!,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                textAlign: TextAlign.right,
                style: AppTextStyles.body.copyWith(color: valueColor),
              ),
            ),
          if (onTap != null) ...[
            const SizedBox(width: 8),
            Icon(LucideIcons.chevronRight, size: 20, color: valueColor),
          ],
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

class AssistantRoleOption {
  const AssistantRoleOption({
    required this.value,
    required this.label,
    required this.description,
    required this.icon,
    required this.color,
    required this.background,
  });

  final String value;
  final String label;
  final String description;
  final IconData icon;
  final Color color;
  final Color background;
}

const _assistantRoleOptions = [
  AssistantRoleOption(
    value: 'warm',
    label: '温暖陪伴型',
    description: '语气更亲切，适合日常农事建议和连续沟通。',
    icon: LucideIcons.messagesSquare,
    color: AppColors.greenDark,
    background: AppColors.greenSoft,
  ),
  AssistantRoleOption(
    value: 'professional',
    label: '冷静专业型',
    description: '表达更直接，优先给出依据、风险和操作建议。',
    icon: LucideIcons.clipboardCheck,
    color: AppColors.blue,
    background: AppColors.blueSoft,
  ),
  AssistantRoleOption(
    value: 'creative',
    label: '灵感创意型',
    description: '更适合活动策划、经营思路和内容生成。',
    icon: LucideIcons.sparkles,
    color: AppColors.purple,
    background: AppColors.purpleSoft,
  ),
];

Future<AssistantRoleOption?> showAssistantRoleSheet({
  required BuildContext context,
  required String selectedValue,
}) {
  return showModalBottomSheet<AssistantRoleOption>(
    context: context,
    backgroundColor: Colors.transparent,
    isScrollControlled: true,
    builder: (context) {
      return _AssistantRoleSheet(selectedValue: selectedValue);
    },
  );
}

class _AssistantRoleSheet extends StatelessWidget {
  const _AssistantRoleSheet({required this.selectedValue});

  final String selectedValue;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      top: false,
      child: Container(
        padding: const EdgeInsets.fromLTRB(20, 10, 20, 20),
        decoration: const BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
          boxShadow: [
            BoxShadow(
              color: Color(0x1A111827),
              blurRadius: 24,
              offset: Offset(0, -8),
            ),
          ],
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Align(
              child: Container(
                width: 44,
                height: 5,
                decoration: BoxDecoration(
                  color: const Color(0xFFD0D5DD),
                  borderRadius: BorderRadius.circular(999),
                ),
              ),
            ),
            const SizedBox(height: 18),
            const Text('回答风格', style: AppTextStyles.title),
            const SizedBox(height: 12),
            for (final option in _assistantRoleOptions)
              _AssistantRoleTile(
                option: option,
                selected: option.value == selectedValue,
                onTap: () => Navigator.of(context).pop(option),
              ),
          ],
        ),
      ),
    );
  }
}

class _AssistantRoleTile extends StatelessWidget {
  const _AssistantRoleTile({
    required this.option,
    required this.selected,
    required this.onTap,
  });

  final AssistantRoleOption option;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      borderRadius: BorderRadius.circular(16),
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.only(bottom: 10),
        padding: const EdgeInsets.all(12),
        constraints: const BoxConstraints(minHeight: 76),
        decoration: BoxDecoration(
          color: selected ? AppColors.blueSoft : AppColors.surface2,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: selected ? AppColors.blue : AppColors.lineSoft,
          ),
        ),
        child: Row(
          children: [
            IconBadge(
              icon: option.icon,
              color: option.color,
              background: option.background,
              size: 38,
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(option.label, style: AppTextStyles.listTitle),
                  const SizedBox(height: 3),
                  Text(
                    option.description,
                    style: AppTextStyles.small.copyWith(
                      color: AppColors.muted,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 10),
            Icon(
              selected ? LucideIcons.circleCheck : LucideIcons.circle,
              size: 20,
              color: selected ? AppColors.blue : AppColors.subtle,
            ),
          ],
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
