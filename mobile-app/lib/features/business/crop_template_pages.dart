import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../data/api/api_models.dart';
import '../../data/repositories/business_repository.dart';
import '../../shared/assets/app_assets.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';
import 'bulk_delete_ui.dart';
import 'business_ui.dart';
import 'farm_cycle_pages.dart';

class CropTemplateListPage extends StatefulWidget {
  const CropTemplateListPage({
    super.key,
    required this.repository,
    this.onBottomTabChanged,
  });

  static const routePath = '/crop-template-list';

  final BusinessRepository repository;
  final ValueChanged<int>? onBottomTabChanged;

  @override
  State<CropTemplateListPage> createState() => _CropTemplateListPageState();
}

class _CropTemplateListPageState extends State<CropTemplateListPage> {
  late Future<PageResult<ApiRecord>> _templatesFuture;

  @override
  void initState() {
    super.initState();
    _templatesFuture = widget.repository.listCropTemplates();
  }

  void _reloadTemplates() {
    setState(() {
      _templatesFuture = widget.repository.listCropTemplates();
    });
  }

  @override
  Widget build(BuildContext context) {
    return BusinessPageFrame(
      title: '作物模板',
      trailingIcon: LucideIcons.plus,
      trailingOnTap: () => Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => CropTemplateFormPage(
            repository: widget.repository,
            onBottomTabChanged: widget.onBottomTabChanged,
          ),
        ),
      ),
      showBottomTabs: true,
      onBottomTabChanged: widget.onBottomTabChanged,
      children: [
        FutureBuilder<PageResult<ApiRecord>>(
          future: _templatesFuture,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return const Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  TemplateLibraryBanner(
                    asset: AppAssets.businessTemplateOpenBookBanner,
                    templateCount: 0,
                  ),
                  SizedBox(height: 13),
                  LoadingCard(),
                ],
              );
            }
            final items = snapshot.data?.items ?? const <ApiRecord>[];
            return Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                TemplateLibraryBanner(
                  asset: AppAssets.businessTemplateOpenBookBanner,
                  templateCount: items.length,
                ),
                const SizedBox(height: 13),
                const SearchFieldCard(text: '搜索作物或品种'),
                const SizedBox(height: 13),
                const ChipRail(items: ['全部', '瓜果', '蔬菜', '粮食']),
                const SizedBox(height: 13),
                BulkDeleteListSection(
                  items: items,
                  hasError: snapshot.hasError,
                  emptyMessage: '还没有作物模板。',
                  errorMessage: '作物模板加载失败，请稍后重试。',
                  deleteTitle: '作物模板',
                  deleteSuccessName: '作物模板',
                  onDeleteRecord: widget.repository.deleteCropTemplate,
                  onDeleted: _reloadTemplates,
                  cardBuilder: (record, selectionMode, selected) =>
                      TemplateListCard(
                    record: record,
                    repository: widget.repository,
                    onBottomTabChanged: widget.onBottomTabChanged,
                    selectionMode: selectionMode,
                    selected: selected,
                  ),
                ),
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
  final _name = TextEditingController();
  final _variety = TextEditingController();
  final _stageName = TextEditingController();
  final _stageDays = TextEditingController();
  final _stageTask = TextEditingController();
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
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(message)));
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
        onSecondary: () => _showMessage('已生成阶段预览'),
        showTabs: true,
        onBottomTabChanged: widget.onBottomTabChanged,
      ),
      children: [
        const AiLandscapeBanner(
          title: '输入作物名称，AI生成阶段',
          subtitle: '填写模板信息后保存到后端',
          asset: AppAssets.businessTemplateBanner,
          accent: businessGreen,
        ),
        FormRowsCard(
          title: '作物信息',
          icon: LucideIcons.sprout,
          children: [
            BusinessFormRow(
              label: '作物名称',
              value: '',
              controller: _name,
              hintText: '输入作物名称',
              chevron: true,
            ),
            BusinessFormRow(
              label: '品种',
              value: '',
              controller: _variety,
              hintText: '输入品种',
              chevron: true,
            ),
          ],
        ),
        BusinessCard(
          child: Column(
            children: [
              const BusinessCardHeader(
                title: '生长阶段',
                icon: LucideIcons.sprout,
              ),
              BusinessFormRow(
                label: '阶段名称',
                value: '',
                controller: _stageName,
                hintText: '输入阶段名称',
              ),
              BusinessFormRow(
                label: '持续天数',
                value: '',
                controller: _stageDays,
                hintText: '输入天数',
                keyboardType: TextInputType.number,
              ),
              BusinessFormRow(
                label: '关键任务',
                value: '',
                controller: _stageTask,
                hintText: '输入关键任务',
              ),
              AddDashedRow(label: '添加阶段', onTap: () => _showMessage('已添加新阶段')),
            ],
          ),
        ),
      ],
    );
  }
}

class TemplateListCard extends StatelessWidget {
  const TemplateListCard({
    super.key,
    required this.record,
    required this.repository,
    this.onBottomTabChanged,
    this.selectionMode = false,
    this.selected = false,
  });

  final ApiRecord record;
  final BusinessRepository repository;
  final ValueChanged<int>? onBottomTabChanged;
  final bool selectionMode;
  final bool selected;

  @override
  Widget build(BuildContext context) {
    final json = record.json;
    final stageNames = _stageNames(json['stages']);
    final name = _firstNonEmpty([json['name']], fallback: '未命名模板');
    final variety = _firstNonEmpty([json['variety']], fallback: '未填写品种');
    final stageCount = stageNames.length;
    final days = _firstNonEmpty([json['total_cycle_days']], fallback: '未设置');
    final used = json['usage_count'] ?? 0;
    return BusinessCard(
      padding: const EdgeInsets.fromLTRB(14, 14, 14, 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SelectionCheckbox(visible: selectionMode, selected: selected),
              SizedBox(
                width: 104,
                child: Image.asset(
                  AppAssets.businessTemplateBanner,
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
            activeIndex: stageNames.isEmpty ? 0 : stageNames.length - 1,
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
                  onTap: selectionMode
                      ? null
                      : () => Navigator.of(context).push(
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
                  onTap: selectionMode
                      ? null
                      : () => Navigator.of(context).push(
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

List<String> _stageNames(Object? value) {
  if (value is! List) return const [];
  return value.whereType<Map>().map((stage) {
    return _firstNonEmpty([stage['name']], fallback: '未命名阶段');
  }).toList();
}

String _firstNonEmpty(List<Object?> values, {String fallback = ''}) {
  for (final value in values) {
    final text = '$value'.trim();
    if (value != null && text.isNotEmpty && text != 'null') return text;
  }
  return fallback;
}
