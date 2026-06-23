import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../data/api/api_models.dart';
import '../../data/repositories/business_repository.dart';
import '../../shared/assets/app_assets.dart';
import '../../shared/widgets/animated_press.dart';
import '../../shared/widgets/textured_card.dart';
import '../../theme/app_colors.dart';
import 'bulk_delete_ui.dart';
import 'business_ui.dart';

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
  final _searchController = TextEditingController();
  int _filterIndex = 0;

  static const _filters = ['全部', '瓜果', '蔬菜', '粮食'];

  @override
  void initState() {
    super.initState();
    _templatesFuture = widget.repository.listCropTemplates();
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
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
              return Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  _TemplateLibraryHero(templateCount: 0),
                  const SizedBox(height: 16),
                  const LoadingCard(),
                ],
              );
            }
            final items = snapshot.data?.items ?? const <ApiRecord>[];
            final visibleItems = _filterTemplates(
              items,
              query: _searchController.text,
              filterIndex: _filterIndex,
            );
            return Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                _TemplateLibraryHero(templateCount: items.length),
                const SizedBox(height: 16),
                SearchFieldCard(
                  text: '搜索作物或品种',
                  controller: _searchController,
                  onChanged: (_) => setState(() {}),
                ),
                const SizedBox(height: 12),
                ChipRail(
                  items: _filters,
                  activeIndex: _filterIndex,
                  activeColor: AppColors.ink,
                  onSelected: (index) => setState(() => _filterIndex = index),
                ),
                const SizedBox(height: 16),
                BulkDeleteListSection(
                  items: visibleItems,
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

class _TemplateLibraryHero extends StatelessWidget {
  const _TemplateLibraryHero({required this.templateCount});

  final int templateCount;

  @override
  Widget build(BuildContext context) {
    return TexturedCard(
      accent: AppColors.blue,
      padding: const EdgeInsets.fromLTRB(20, 18, 20, 18),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          GradientIconTile(
            icon: LucideIcons.bookOpenText,
            accent: AppColors.blue,
            size: 44,
            iconSize: 20,
            borderRadius: 14,
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  '模板库',
                  style: TextStyle(
                    color: AppColors.ink,
                    fontSize: 16,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 0,
                  ),
                ),
                const SizedBox(height: 3),
                Text(
                  templateCount == 0
                      ? '还没有模板，新建后生成茬口更快'
                      : '已创建 $templateCount 个作物模板',
                  style: const TextStyle(
                    color: AppColors.muted,
                    fontSize: 12.5,
                    fontWeight: FontWeight.w500,
                    letterSpacing: 0,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 12),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
            decoration: BoxDecoration(
              color: AppColors.blueSoft,
              borderRadius: BorderRadius.circular(999),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(
                  LucideIcons.layers,
                  size: 12,
                  color: AppColors.blue,
                ),
                const SizedBox(width: 4),
                Text(
                  '$templateCount',
                  style: const TextStyle(
                    color: AppColors.blue,
                    fontSize: 13,
                    fontWeight: FontWeight.w900,
                    letterSpacing: -0.2,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

List<ApiRecord> _filterTemplates(
  List<ApiRecord> items, {
  required String query,
  required int filterIndex,
}) {
  final keyword = query.trim().toLowerCase();
  final category =
      filterIndex == 0 ? '' : _CropTemplateListPageState._filters[filterIndex];
  return items.where((item) {
    final json = item.json;
    if (category.isNotEmpty && !_templateMatchesCategory(json, category)) {
      return false;
    }
    if (keyword.isEmpty) return true;
    final searchable = [
      json['name'],
      json['variety'],
      json['category'],
      json['crop_category'],
    ].map((value) => _firstNonEmpty([value]).toLowerCase()).join(' ');
    return searchable.contains(keyword);
  }).toList(growable: false);
}

bool _templateMatchesCategory(Map<String, dynamic> json, String category) {
  final explicitCategory =
      _firstNonEmpty([json['category'], json['crop_category']]);
  if (explicitCategory == category) return true;
  final text = [
    json['name'],
    json['variety'],
  ].map((value) => _firstNonEmpty([value])).join(' ');
  return switch (category) {
    '瓜果' => text.contains('瓜') || text.contains('果'),
    '蔬菜' => text.contains('菜') ||
        text.contains('番茄') ||
        text.contains('黄瓜') ||
        text.contains('辣椒') ||
        text.contains('茄'),
    '粮食' => text.contains('玉米') ||
        text.contains('小麦') ||
        text.contains('水稻') ||
        text.contains('粮'),
    _ => true,
  };
}

class CropTemplateFormPage extends StatefulWidget {
  const CropTemplateFormPage({
    super.key,
    required this.repository,
    this.templateId,
    this.initialRecord,
    this.onBottomTabChanged,
  });

  static const routePath = '/crop-template-form';

  final BusinessRepository repository;
  final int? templateId;
  final ApiRecord? initialRecord;
  final ValueChanged<int>? onBottomTabChanged;

  @override
  State<CropTemplateFormPage> createState() => _CropTemplateFormPageState();
}

class _CropTemplateFormPageState extends State<CropTemplateFormPage> {
  final _name = TextEditingController();
  final _variety = TextEditingController();
  final List<_EditableStage> _stages = [_EditableStage()];
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _hydrateInitialRecord();
  }

  void _hydrateInitialRecord() {
    final json = widget.initialRecord?.json;
    if (json == null) return;
    _name.text = _firstNonEmpty([json['name']]);
    _variety.text = _firstNonEmpty([json['variety']]);
    final stages = json['stages'];
    if (stages is List && stages.isNotEmpty && stages.first is Map) {
      _stages
        ..clear()
        ..addAll(stages.whereType<Map>().map((stage) {
          return _EditableStage.fromJson(Map<String, dynamic>.from(stage));
        }));
    }
  }

  @override
  void dispose() {
    _name.dispose();
    _variety.dispose();
    for (final stage in _stages) {
      stage.dispose();
    }
    super.dispose();
  }

  Future<void> _save() async {
    if (_saving) return;
    setState(() => _saving = true);
    try {
      await widget.repository.saveCropTemplate(
        {
          'name': _name.text.trim(),
          'variety': _variety.text.trim(),
          'stages': _stagePayloads(),
        },
        templateId: widget.templateId ?? widget.initialRecord?.id,
      );
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

  List<Map<String, Object?>> _stagePayloads() {
    return [
      for (var index = 0; index < _stages.length; index++)
        {
          'name': _stages[index].name.text.trim(),
          'duration_days': int.tryParse(_stages[index].days.text.trim()) ?? 0,
          'order_index': index + 1,
          'key_tasks': _stages[index].task.text.trim(),
        },
    ];
  }

  void _addStage() {
    setState(() => _stages.add(_EditableStage()));
    _showMessage('已添加新阶段');
  }

  void _removeStage(int index) {
    if (_stages.length == 1) {
      _showMessage('至少保留一个阶段');
      return;
    }
    setState(() {
      final removed = _stages.removeAt(index);
      removed.dispose();
    });
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
          title: '模板信息',
          subtitle: '保存后可复用',
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
            ),
            BusinessFormRow(
              label: '品种',
              value: '',
              controller: _variety,
              hintText: '输入品种',
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
              for (var index = 0; index < _stages.length; index++)
                _StageEditorCard(
                  stage: _stages[index],
                  index: index,
                  canRemove: _stages.length > 1,
                  onRemove: () => _removeStage(index),
                ),
              AddDashedRow(label: '添加阶段', onTap: _addStage),
            ],
          ),
        ),
      ],
    );
  }
}

class _EditableStage {
  _EditableStage();

  _EditableStage.fromJson(Map<String, dynamic> json) {
    name.text = _firstNonEmpty([json['name']]);
    days.text = _firstNonEmpty([json['duration_days']]);
    task.text = _firstNonEmpty([json['key_tasks']]);
  }

  final TextEditingController name = TextEditingController();
  final TextEditingController days = TextEditingController();
  final TextEditingController task = TextEditingController();

  void dispose() {
    name.dispose();
    days.dispose();
    task.dispose();
  }
}

class _StageEditorCard extends StatelessWidget {
  const _StageEditorCard({
    required this.stage,
    required this.index,
    required this.canRemove,
    required this.onRemove,
  });

  final _EditableStage stage;
  final int index;
  final bool canRemove;
  final VoidCallback onRemove;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.fromLTRB(12, 0, 12, 12),
      decoration: BoxDecoration(
        color: AppColors.surface2,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppColors.lineSoft),
      ),
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(14, 10, 10, 2),
            child: Row(
              children: [
                SoftPill(
                  text: '阶段 ${index + 1}',
                  color: businessGreen,
                  background: AppColors.greenSoft,
                ),
                const Spacer(),
                IconButton(
                  tooltip: canRemove ? '删除阶段' : '至少保留一个阶段',
                  onPressed: canRemove ? onRemove : null,
                  icon: const Icon(LucideIcons.trash2, size: 18),
                  color: canRemove ? AppColors.red : AppColors.subtle,
                ),
              ],
            ),
          ),
          BusinessFormRow(
            label: '阶段名称',
            value: '',
            controller: stage.name,
            hintText: '输入阶段名称',
          ),
          BusinessFormRow(
            label: '持续天数',
            value: '',
            controller: stage.days,
            hintText: '输入天数',
            keyboardType: TextInputType.number,
          ),
          BusinessFormRow(
            label: '关键任务',
            value: '',
            controller: stage.task,
            hintText: '输入关键任务',
          ),
        ],
      ),
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
    final days = _firstNonEmpty([json['total_cycle_days']], fallback: '');
    final used = json['usage_count'] ?? 0;
    return AnimatedPress(
      scale: 0.99,
      onTap: selectionMode
          ? null
          : () => Navigator.of(context).push(
                MaterialPageRoute(
                  builder: (_) => CropTemplateFormPage(
                    repository: repository,
                    templateId: record.id,
                    initialRecord: record,
                    onBottomTabChanged: onBottomTabChanged,
                  ),
                ),
              ),
      child: Container(
        padding: const EdgeInsets.fromLTRB(16, 14, 12, 14),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(18),
          border: Border.all(
            color: selected ? AppColors.ink : AppColors.lineSoft,
          ),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            SelectionCheckbox(visible: selectionMode, selected: selected),
            Container(
              width: 40,
              height: 40,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: AppColors.surface2,
                borderRadius: BorderRadius.circular(11),
              ),
              child: const Icon(
                LucideIcons.sprout,
                size: 18,
                color: AppColors.ink2,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Flexible(
                        child: Text(
                          name,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            color: AppColors.ink,
                            fontSize: 16,
                            fontWeight: FontWeight.w800,
                            letterSpacing: -0.2,
                            height: 1.2,
                          ),
                        ),
                      ),
                      if (variety.isNotEmpty && variety != '未填写品种') ...[
                        const SizedBox(width: 8),
                        Text(
                          variety,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            color: AppColors.subtle,
                            fontSize: 12,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ],
                    ],
                  ),
                  const SizedBox(height: 5),
                  Row(
                    children: [
                      _MetaItem(
                        icon: LucideIcons.gitBranch,
                        text: '$stageCount 阶段',
                      ),
                      const SizedBox(width: 12),
                      if (days.isNotEmpty) ...[
                        _MetaItem(
                          icon: LucideIcons.calendarDays,
                          text: '$days 天',
                        ),
                        const SizedBox(width: 12),
                      ],
                      _MetaItem(
                        icon: LucideIcons.layers,
                        text: '用于 $used',
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(width: 4),
            const Icon(
              LucideIcons.chevronRight,
              color: AppColors.subtle,
              size: 18,
            ),
          ],
        ),
      ),
    );
  }
}

class _MetaItem extends StatelessWidget {
  const _MetaItem({required this.icon, required this.text});

  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 11, color: AppColors.subtle),
        const SizedBox(width: 3),
        Text(
          text,
          style: const TextStyle(
            color: AppColors.muted,
            fontSize: 11.5,
            fontWeight: FontWeight.w600,
            letterSpacing: 0,
          ),
        ),
      ],
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
