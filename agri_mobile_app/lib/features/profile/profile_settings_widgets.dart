part of 'profile_screen.dart';

class _SystemSettingsCard extends StatelessWidget {
  const _SystemSettingsCard();

  @override
  Widget build(BuildContext context) {
    return CardPanel(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: _ProfileOptionRow(
        icon: LucideIcons.info,
        title: '关于${AppIdentity.displayName}',
        value: '应用信息与开源许可',
        onTap: () => Navigator.of(context).push<void>(
            MaterialPageRoute(builder: (_) => const AboutAppPage())),
      ),
    );
  }
}

class _ProfileOptionRow extends StatefulWidget {
  const _ProfileOptionRow(
      {required this.icon, required this.title, this.value, this.onTap});

  final IconData icon;
  final String title;
  final String? value;
  final Future<void> Function()? onTap;

  @override
  State<_ProfileOptionRow> createState() => _ProfileOptionRowState();
}

class _ProfileOptionRowState extends State<_ProfileOptionRow> {
  bool _pending = false;

  Future<void> _runAction() async {
    if (_pending || widget.onTap == null) return;
    setState(() => _pending = true);
    try {
      await widget.onTap!();
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('操作未完成，请稍后重试')));
      }
    } finally {
      if (mounted) setState(() => _pending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: _pending ? null : _runAction,
      child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 16),
          child: Row(children: [
            Icon(widget.icon, size: 22, color: AppColors.ink2),
            const SizedBox(width: 16),
            Expanded(
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                  Text(widget.title, style: AppTextStyles.listTitle),
                  if (widget.value != null) ...[
                    const SizedBox(height: 4),
                    Text(_pending ? '正在处理…' : widget.value!,
                        style: AppTextStyles.small),
                  ],
                ])),
            const SizedBox(width: 12),
            Icon(_pending ? LucideIcons.ellipsis : LucideIcons.chevronRight,
                size: 18, color: AppColors.subtle),
          ])),
    );
  }
}

class AboutAppPage extends StatefulWidget {
  const AboutAppPage({super.key});

  @override
  State<AboutAppPage> createState() => _AboutAppPageState();
}

class _AboutAppPageState extends State<AboutAppPage> {
  late final Future<PackageInfo> _info = PackageInfo.fromPlatform();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(title: const Text('关于田掌柜')),
      body: SafeArea(
          child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(24, 32, 24, 40),
        child: Center(
            child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 430),
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      const Center(child: FarmBrandMark(size: 80)),
                      const SizedBox(height: 24),
                      Text(AppIdentity.displayName,
                          textAlign: TextAlign.center,
                          style: AppTextStyles.title.copyWith(fontSize: 28)),
                      const SizedBox(height: 8),
                      Text(AppIdentity.tagline,
                          textAlign: TextAlign.center,
                          style: AppTextStyles.body
                              .copyWith(color: AppColors.muted)),
                      const SizedBox(height: 32),
                      const Text('让每一份耕耘，有据可循。',
                          style: AppTextStyles.sectionTitle),
                      const SizedBox(height: 12),
                      const Text(
                          '记录农事与收支，整理茬口和用工。'
                          '把零散的日常，留成下一次经营的依据。',
                          style: AppTextStyles.body),
                      const SizedBox(height: 32),
                      CardPanel(
                          child: Column(children: [
                        FutureBuilder<PackageInfo>(
                            future: _info,
                            builder: (context, snapshot) => Row(children: [
                                  const Expanded(
                                      child: Text('当前版本',
                                          style: AppTextStyles.body)),
                                  Text(
                                      snapshot.hasData
                                          ? 'v${snapshot.data!.version} (${snapshot.data!.buildNumber})'
                                          : snapshot.hasError
                                              ? '暂不可用'
                                              : '读取中…',
                                      style: AppTextStyles.small),
                                ])),
                        const SizedBox(height: 16),
                        const Divider(height: 1),
                        _ProfileOptionRow(
                            icon: LucideIcons.fileText,
                            title: '开源许可',
                            onTap: () async => showLicensePage(
                                context: context,
                                applicationName: AppIdentity.displayName)),
                      ])),
                    ]))),
      )),
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
    sheetAnimationStyle: AppMotion.sheetStyle(context),
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
            const SizedBox(height: 8),
            const Text('选择芽芽与你沟通的方式，之后随时可以调整。', style: AppTextStyles.small),
            const SizedBox(height: 24),
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
          color: selected ? AppColors.blueSoft : Colors.transparent,
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
