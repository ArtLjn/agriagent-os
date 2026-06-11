import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../data/api/api_models.dart';
import '../../data/repositories/business_repository.dart';
import '../../shared/assets/app_assets.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';
import 'business_ui.dart';
import 'farm_cycle_pages.dart';

class CropTemplateListPage extends StatelessWidget {
  const CropTemplateListPage({
    super.key,
    required this.repository,
    this.onBottomTabChanged,
  });

  static const routePath = '/crop-template-list';

  final BusinessRepository repository;
  final ValueChanged<int>? onBottomTabChanged;

  @override
  Widget build(BuildContext context) {
    return BusinessPageFrame(
      title: '作物模板',
      trailingIcon: LucideIcons.plus,
      trailingOnTap: () => Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => CropTemplateFormPage(
            repository: repository,
            onBottomTabChanged: onBottomTabChanged,
          ),
        ),
      ),
      showBottomTabs: true,
      onBottomTabChanged: onBottomTabChanged,
      children: [
        const TemplateLibraryBanner(
          asset: AppAssets.businessTemplateOpenBookBanner,
        ),
        const SearchFieldCard(text: '搜索作物或品种'),
        const ChipRail(items: ['全部', '瓜果', '蔬菜', '粮食']),
        FutureBuilder<PageResult<ApiRecord>>(
          future: repository.listCropTemplates(),
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return const LoadingCard();
            }
            final items = snapshot.data?.items ?? const <ApiRecord>[];
            if (items.isEmpty && snapshot.hasError) {
              return const BusinessCard(
                padding: EdgeInsets.all(18),
                child: Text('还没有作物模板。'),
              );
            }
            return Column(
              children: [
                for (var index = 0;
                    index < _templateFallbacks.length;
                    index++) ...[
                  TemplateListCard(
                    record: index < items.length ? items[index] : null,
                    repository: repository,
                    index: index,
                    onBottomTabChanged: onBottomTabChanged,
                  ),
                  const SizedBox(height: 12),
                ],
              ],
            );
          },
        ),
      ],
    );
  }
}

class CropTemplateFormPage extends StatefulWidget {
  const CropTemplateFormPage(
      {super.key,
      required this.repository,
      this.templateId,
      this.onBottomTabChanged});

  static const routePath = '/crop-template-form';

  final BusinessRepository repository;
  final int? templateId;
  final ValueChanged<int>? onBottomTabChanged;

  @override
  State<CropTemplateFormPage> createState() => _CropTemplateFormPageState();
}

class _CropTemplateFormPageState extends State<CropTemplateFormPage> {
  final _name = TextEditingController(text: '西瓜');
  final _variety = TextEditingController(text: '8424');
  final _stageName = TextEditingController(text: '育苗期');
  final _stageDays = TextEditingController(text: '18');
  final _stageTask = TextEditingController(text: '控温、补光');
  bool _saving = false;

  @override
  void dispose() {
    _name.dispose();
    _variety.dispose();
    _stageName.dispose();
    _stageDays.dispose();
    _stageTask.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (_saving) return;
    setState(() => _saving = true);
    try {
      await widget.repository.saveCropTemplate({
        'name': _name.text.trim(),
        'variety': _variety.text.trim(),
        'stages': [
          {
            'name': _stageName.text.trim(),
            'duration_days': int.tryParse(_stageDays.text.trim()) ?? 0,
            'order_index': 1,
            'key_tasks': _stageTask.text.trim(),
          },
        ],
      }, templateId: widget.templateId);
      _showMessage('保存模板成功');
    } catch (_) {
      _showMessage('保存失败，请稍后再试');
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  void _showMessage(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    return BusinessPageFrame(
      title: widget.templateId == null ? '新建模板' : '编辑模板',
      trailingIcon: LucideIcons.sparkles,
      bottomBar: BottomActions(
        secondaryLabel: '预览',
        primaryLabel: _saving ? '保存中' : '保存模板',
        onPrimary: _save,
        showTabs: true,
        onBottomTabChanged: widget.onBottomTabChanged,
      ),
      children: [
        const AiLandscapeBanner(
          title: '输入作物名称，AI生成阶段',
          subtitle: '例如：我要种8424西瓜',
          asset: AppAssets.businessTemplateBanner,
          accent: businessGreen,
        ),
        FormRowsCard(
          title: '作物信息',
          icon: LucideIcons.sprout,
          children: [
            BusinessFormRow(
                label: '作物名称', value: '西瓜', controller: _name, chevron: true),
            BusinessFormRow(
                label: '品种',
                value: '8424',
                controller: _variety,
                chevron: true),
            const BusinessFormRow(label: '适用季节', value: '春季', chevron: true),
          ],
        ),
        const BusinessCard(
          child: Column(
            children: [
              BusinessCardHeader(
                title: '生长阶段',
                icon: LucideIcons.sprout,
              ),
              StageEditRow(
                  index: 1, title: '播种期', days: '7天', color: businessBlue),
              StageEditRow(
                  index: 2, title: '苗期', days: '18天', color: businessGreen),
              StageEditRow(
                  index: 3, title: '伸蔓期', days: '22天', color: AppColors.amber),
              StageEditRow(
                  index: 4, title: '开花坐果期', days: '25天', color: businessGreen),
              StageEditRow(
                  index: 5, title: '采收期', days: '20天', color: businessBlue),
              AddDashedRow(label: '添加阶段'),
            ],
          ),
        ),
        Offstage(
          offstage: true,
          child: FormRowsCard(
            title: '阶段设置',
            icon: LucideIcons.listChecks,
            children: [
              BusinessFormRow(
                  label: '阶段名称', value: '育苗期', controller: _stageName),
              BusinessFormRow(
                label: '持续天数',
                value: '18',
                controller: _stageDays,
                keyboardType: TextInputType.number,
              ),
              BusinessFormRow(
                  label: '关键任务', value: '控温、补光', controller: _stageTask),
            ],
          ),
        ),
      ],
    );
  }
}

class TemplateListCard extends StatelessWidget {
  const TemplateListCard(
      {super.key,
      this.record,
      required this.repository,
      this.index = 0,
      this.onBottomTabChanged});

  final ApiRecord? record;
  final BusinessRepository repository;
  final int index;
  final ValueChanged<int>? onBottomTabChanged;

  @override
  Widget build(BuildContext context) {
    final json = record?.json ?? const <String, Object?>{};
    final fallback = _templateFallbacks[index % _templateFallbacks.length];
    final stageNames = fallback.stages;
    final name = fallback.name;
    final variety = fallback.variety;
    final stageCount = stageNames.length;
    final days = fallback.days;
    final used = json['usage_count'] ?? fallback.used;
    return BusinessCard(
      padding: const EdgeInsets.fromLTRB(14, 14, 14, 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SizedBox(
                width: 104,
                child: Image.asset(
                  fallback.asset,
                  height: 112,
                  fit: BoxFit.contain,
                  errorBuilder: (_, __, ___) => const Icon(
                    LucideIcons.sprout,
                    color: AppColors.green,
                  ),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      name,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: AppTextStyles.sectionTitle.copyWith(
                        fontSize: 20,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                    const SizedBox(height: 7),
                    SoftPill(
                      text: variety,
                      color: AppColors.greenDark,
                      background: AppColors.greenSoft,
                    ),
                    const SizedBox(height: 9),
                    Text(
                      '$stageCount 个阶段 · 周期 $days 天 · 已用于$used个茬口',
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: AppTextStyles.body.copyWith(
                        color: AppColors.muted,
                        fontSize: 13,
                        height: 18 / 13,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          MiniStageTimeline(
            stages: stageNames.take(6).toList(),
            activeIndex: stageNames.length - 1,
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(
                child: FilledActionButton(
                  label: '新建茬口',
                  foreground: businessBlue,
                  background: AppColors.blueSoft,
                  borderColor: AppColors.blueSoft,
                  icon: LucideIcons.layers,
                  height: 42,
                  onTap: () => Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (_) => FarmCycleFormPage(
                        repository: repository,
                        onBottomTabChanged: onBottomTabChanged,
                      ),
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: FilledActionButton(
                  label: '编辑',
                  foreground: AppColors.purple,
                  background: AppColors.purpleSoft,
                  borderColor: AppColors.purpleSoft,
                  icon: LucideIcons.pencil,
                  height: 42,
                  onTap: () => Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (_) => CropTemplateFormPage(
                        repository: repository,
                        onBottomTabChanged: onBottomTabChanged,
                      ),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

const _templateFallbacks = [
  _TemplateFallback(
    name: '8424西瓜',
    variety: '西瓜',
    days: 92,
    used: 3,
    asset: AppAssets.businessCropWatermelon,
    stages: ['播种育苗', '定植缓苗', '伸蔓期', '膨果期', '成熟采收'],
  ),
  _TemplateFallback(
    name: '普罗旺斯番茄',
    variety: '番茄',
    days: 120,
    used: 2,
    asset: AppAssets.businessCropTomato,
    stages: ['播种育苗', '定植缓苗', '开花坐果', '果实膨大', '转色期', '成熟采收'],
  ),
  _TemplateFallback(
    name: '甜玉米',
    variety: '玉米',
    days: 85,
    used: 1,
    asset: AppAssets.businessCropCorn,
    stages: ['播种育苗', '拔节期', '抽雄吐丝', '成熟采收'],
  ),
];

class _TemplateFallback {
  const _TemplateFallback({
    required this.name,
    required this.variety,
    required this.days,
    required this.used,
    required this.asset,
    required this.stages,
  });

  final String name;
  final String variety;
  final int days;
  final int used;
  final String asset;
  final List<String> stages;
}
