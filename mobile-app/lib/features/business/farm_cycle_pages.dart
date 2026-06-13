import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../data/api/api_models.dart';
import '../../data/repositories/business_repository.dart';
import '../../shared/assets/app_assets.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';
import 'bulk_delete_ui.dart';
import 'business_ui.dart';
import 'farm_log_create_page.dart';

class FarmCycleListPage extends StatefulWidget {
  const FarmCycleListPage({
    super.key,
    required this.repository,
    this.onBottomTabChanged,
  });

  static const routePath = '/farm-cycle-list';

  final BusinessRepository repository;
  final ValueChanged<int>? onBottomTabChanged;

  @override
  State<FarmCycleListPage> createState() => _FarmCycleListPageState();
}

class _FarmCycleListPageState extends State<FarmCycleListPage> {
  late Future<PageResult<ApiRecord>> _cyclesFuture;

  @override
  void initState() {
    super.initState();
    _cyclesFuture = widget.repository.listCycles();
  }

  void _reloadCycles() {
    setState(() {
      _cyclesFuture = widget.repository.listCycles();
    });
  }

  @override
  Widget build(BuildContext context) {
    return BusinessPageFrame(
      title: '茬口管理',
      trailingIcon: LucideIcons.slidersHorizontal,
      showBottomTabs: true,
      onBottomTabChanged: widget.onBottomTabChanged,
      bottomOverlay: CycleCreateFab(
        label: '新建茬口',
        onTap: () => Navigator.of(context).push(
          MaterialPageRoute(
            builder: (_) => FarmCycleFormPage(
              repository: widget.repository,
              onBottomTabChanged: widget.onBottomTabChanged,
            ),
          ),
        ),
      ),
      children: [
        FutureBuilder<PageResult<ApiRecord>>(
          future: _cyclesFuture,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  _cycleSummaryBanner(const <ApiRecord>[]),
                  const SizedBox(height: 13),
                  const LoadingCard(),
                ],
              );
            }
            final items = snapshot.data?.items ?? const <ApiRecord>[];
            return Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                _cycleSummaryBanner(items),
                const SizedBox(height: 13),
                const SearchFieldCard(text: '搜索作物、地块、茬口'),
                const SizedBox(height: 13),
                const ChipRail(
                  items: ['全部', '在种', '计划', '已结束'],
                  activeColor: businessGreen,
                ),
                const SizedBox(height: 13),
                BulkDeleteListSection(
                  items: items,
                  hasError: snapshot.hasError,
                  emptyMessage: '还没有茬口，先新建一个生产批次。',
                  errorMessage: '茬口数据加载失败，请稍后重试。',
                  deleteTitle: '茬口',
                  deleteSuccessName: '茬口',
                  onDeleteRecord: widget.repository.deleteCycle,
                  onDeleted: _reloadCycles,
                  cardBuilder: (record, selectionMode, selected) =>
                      CycleListCard(
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

class FarmCycleFormPage extends StatefulWidget {
  const FarmCycleFormPage({
    super.key,
    required this.repository,
    this.cycleId,
    this.initialRecord,
    this.initialTemplateId,
    this.initialTemplateName,
    this.onBottomTabChanged,
  });

  static const routePath = '/farm-cycle-form';

  final BusinessRepository repository;
  final int? cycleId;
  final ApiRecord? initialRecord;
  final int? initialTemplateId;
  final String? initialTemplateName;
  final ValueChanged<int>? onBottomTabChanged;

  @override
  State<FarmCycleFormPage> createState() => _FarmCycleFormPageState();
}

class _FarmCycleFormPageState extends State<FarmCycleFormPage> {
  final _name = TextEditingController();
  final _startDate = TextEditingController(text: _todayText());
  final _unitName = TextEditingController();
  final _area = TextEditingController();
  final _season = TextEditingController();
  final _note = TextEditingController();
  final _unitNote = TextEditingController();
  final _plantedDate = TextEditingController(text: _todayText());
  late Future<PageResult<ApiRecord>> _templatesFuture;
  ApiRecord? _selectedTemplate;
  bool _showMore = false;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _templatesFuture = widget.repository.listCropTemplates(size: 100);
    _hydrateInitialRecord();
    final templateId = widget.initialTemplateId;
    if (templateId != null && _selectedTemplate == null) {
      final templateName = widget.initialTemplateName?.trim();
      _selectedTemplate = ApiRecord({
        'id': templateId,
        'name':
            templateName?.isNotEmpty == true ? templateName : '模板 $templateId',
        'stages': const <Object>[],
      });
      if (templateName != null && templateName.isNotEmpty) {
        _name.text = '$templateName茬口';
      }
    }
  }

  void _hydrateInitialRecord() {
    final json = widget.initialRecord?.json;
    if (json == null) return;
    _name.text = _firstNonEmpty([json['name']]);
    _startDate.text =
        _firstNonEmpty([json['start_date']], fallback: _startDate.text);
    _unitName.text = _firstNonEmpty([json['field_name']]);
    _area.text = _firstNonEmpty([json['total_area_mu'], json['unit_area_mu']]);
    _season.text = _firstNonEmpty([json['season']]);
    _note.text = _firstNonEmpty([json['batch_note']]);
    final templateId = json['crop_template_id'];
    if (templateId is int) {
      _selectedTemplate = ApiRecord({
        'id': templateId,
        'name': _firstNonEmpty([
          json['crop_template_name'],
          json['crop_name'],
          json['template_name'],
        ], fallback: '模板 $templateId'),
        'stages': json['stages'] ?? const <Object>[],
      });
    }
  }

  @override
  void dispose() {
    _name.dispose();
    _startDate.dispose();
    _unitName.dispose();
    _area.dispose();
    _season.dispose();
    _note.dispose();
    _unitNote.dispose();
    _plantedDate.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (_saving) return;
    if (!_validateBeforeSave()) return;
    setState(() => _saving = true);
    try {
      final cycle = await widget.repository.saveCycle(
        {
          'name': _name.text.trim(),
          'crop_template_id': _selectedTemplate?.id,
          'start_date': _startDate.text.trim(),
          'field_name': _unitName.text.trim(),
          'total_area_mu': num.tryParse(_area.text.trim()) ?? _area.text.trim(),
          'season': _season.text.trim(),
          'batch_note': _note.text.trim(),
        }..removeWhere((_, value) => value == null || value == ''),
        cycleId: widget.cycleId,
      );
      final unitName = _unitName.text.trim();
      if (widget.cycleId == null && unitName.isNotEmpty) {
        await widget.repository.createPlantingUnit(
          {
            'cycle_id': cycle.id,
            'name': unitName,
            'area_mu': num.tryParse(_area.text.trim()) ?? _area.text.trim(),
            'planted_date': _plantedDate.text.trim(),
            'status': 'active',
            'note': _unitNote.text.trim(),
          }..removeWhere((_, value) => value == null || value == ''),
        );
      }
      _showMessage(widget.cycleId == null ? '创建茬口成功' : '保存茬口成功');
    } catch (_) {
      _showMessage('保存失败，请稍后再试');
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  bool _validateBeforeSave() {
    if (_selectedTemplate == null) {
      _showMessage('请选择作物模板');
      return false;
    }
    if (_name.text.trim().isEmpty) {
      _showMessage('请填写茬口名称');
      return false;
    }
    if (widget.cycleId == null && _unitName.text.trim().isEmpty) {
      _showMessage('请填写棚室或种植区域');
      return false;
    }
    return true;
  }

  Future<void> _pickDate(TextEditingController controller) async {
    final initialDate = DateTime.tryParse(controller.text) ?? DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: initialDate,
      firstDate: DateTime(2020),
      lastDate: DateTime(2035),
      helpText: '选择日期',
      cancelText: '取消',
      confirmText: '确定',
    );
    if (picked == null) return;
    final formatted = _dateText(picked);
    setState(() {
      controller.text = formatted;
      if (controller == _startDate) {
        _plantedDate.text = formatted;
      }
    });
  }

  void _selectTemplate(ApiRecord template) {
    setState(() {
      _selectedTemplate = template;
      if (_name.text.trim().isEmpty) {
        _name.text = _defaultCycleName(template);
      }
    });
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
      title: widget.cycleId == null ? '新建茬口' : '编辑茬口',
      trailingIcon: LucideIcons.sparkles,
      bottomBar: BottomActions(
        secondaryLabel: '保存草稿',
        primaryLabel: _saving
            ? '保存中'
            : widget.cycleId == null
                ? '创建茬口'
                : '保存茬口',
        onPrimary: _save,
        onSecondary: () => _showMessage('草稿已保留在当前页面'),
        showTabs: true,
        onBottomTabChanged: widget.onBottomTabChanged,
      ),
      children: [
        const AiLandscapeBanner(
          title: '新建茬口',
          subtitle: '选择模板后自动带出阶段',
          asset: AppAssets.businessCycleBanner,
          accent: AppColors.green,
        ),
        const AssistEntryCard(
          text: '说一句生成茬口草稿',
          icon: LucideIcons.bot,
        ),
        FormRowsCard(
          title: '基础信息',
          icon: LucideIcons.layers,
          children: [
            BusinessFormRow(
              label: '茬口名称',
              value: '',
              controller: _name,
              hintText: '输入茬口名称',
            ),
            BusinessFormRow(
              label: '作物模板',
              value: _templateDisplayName(_selectedTemplate),
              hintText: '选择自己的作物模板',
              chevron: true,
              onTap: () async {
                final selected = await _showTemplatePicker(
                  context,
                  _templatesFuture,
                  _selectedTemplate?.id,
                );
                if (selected != null) _selectTemplate(selected);
              },
            ),
            BusinessFormRow(
              label: '开始日期',
              value: _startDate.text,
              chevron: true,
              onTap: () => _pickDate(_startDate),
            ),
            BusinessFormRow(
              label: '种植区域',
              value: '',
              controller: _unitName,
              hintText: '例：东大棚 1 号、A 区',
            ),
          ],
        ),
        FormRowsCard(
          title: '区域面积',
          icon: LucideIcons.ruler,
          children: [
            BusinessFormRow(
              label: '面积',
              value: '',
              controller: _area,
              hintText: '输入亩数',
              keyboardType: TextInputType.number,
            ),
            BusinessFormRow(
              label: '定植日期',
              value: _plantedDate.text,
              chevron: true,
              onTap: () => _pickDate(_plantedDate),
            ),
            BusinessFormRow(
              label: '区域备注',
              value: '',
              controller: _unitNote,
              hintText: '可选，例如垄数、棚号说明',
            ),
          ],
        ),
        FormRowsCard(
          title: '更多信息',
          icon: LucideIcons.slidersHorizontal,
          children: [
            BusinessFormRow(
              label: '可选信息',
              value: _showMore ? '收起' : '填写季节和备注',
              chevron: true,
              onTap: () => setState(() => _showMore = !_showMore),
            ),
            if (_showMore) ...[
              BusinessFormRow(
                label: '季节',
                value: '',
                controller: _season,
                hintText: '可选，如春季、秋季',
              ),
              BusinessFormRow(
                label: '茬口备注',
                value: '',
                controller: _note,
                hintText: '补充说明',
              ),
            ],
          ],
        ),
        StagePreviewCard(stages: _templateStages(_selectedTemplate)),
      ],
    );
  }
}

Future<ApiRecord?> _showTemplatePicker(
  BuildContext context,
  Future<PageResult<ApiRecord>> templatesFuture,
  int? selectedTemplateId,
) {
  return showBusinessPickerSheet<ApiRecord>(
    context: context,
    title: '选择作物模板',
    subtitle: '选择后自动带出生长阶段，创建茬口更快',
    future: templatesFuture,
    selectedId: selectedTemplateId,
    loadingText: '正在加载模板',
    errorText: '模板加载失败，请稍后再试',
    emptyText: '还没有作物模板，先新建一个模板',
    titleFor: _templateDisplayName,
    subtitleFor: _templateSubtitle,
    leadingIconFor: (_) => LucideIcons.sprout,
    accentFor: (_) => businessGreen,
  );
}

class CycleListCard extends StatelessWidget {
  const CycleListCard({
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
    final name = _firstNonEmpty([json['name']], fallback: '未命名茬口');
    final variety = _firstNonEmpty([
      json['crop_name'],
      json['crop_template_name'],
      json['template_name'],
      json['variety'],
      json['crop_template_id'] == null
          ? null
          : '模板ID ${json['crop_template_id']}',
    ], fallback: '未关联模板');
    final field = _firstNonEmpty([json['field_name']], fallback: '未填写地块');
    final area = _firstNonEmpty([json['total_area_mu'], json['unit_area_mu']],
        fallback: '未填写面积');
    final stage = _firstNonEmpty(
      [json['current_stage_name'], json['status']],
      fallback: '未设置阶段',
    );
    final startDate = _firstNonEmpty([json['start_date']], fallback: '未填写');
    final progressValue = ((json['progress_percent'] as num?)?.toDouble() ?? 0);
    final progress = progressValue / 100;
    final isPlan = '${json['status'] ?? ''}'.toLowerCase() == 'planned';
    return CycleVisualCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SelectionCheckbox(visible: selectionMode, selected: selected),
              const CropIllustrationAvatar(
                asset: AppAssets.businessCycleBanner,
                size: 96,
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      name,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: AppTextStyles.sectionTitle.copyWith(
                        fontSize: 19,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                    const SizedBox(height: 5),
                    Text(
                      variety,
                      style: AppTextStyles.body.copyWith(
                        color: AppColors.muted,
                        fontSize: 15,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        const Icon(
                          LucideIcons.mapPin,
                          size: 15,
                          color: AppColors.subtle,
                        ),
                        const SizedBox(width: 4),
                        Expanded(
                          child: Text(
                            '$field  |  $area',
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: AppTextStyles.body.copyWith(
                              color: AppColors.muted,
                              fontSize: 15,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              SoftPill(
                text: stage,
                color: isPlan ? businessBlue : AppColors.greenDark,
                background: isPlan ? AppColors.blueSoft : AppColors.greenSoft,
              ),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Text(
                '进度',
                style: AppTextStyles.body.copyWith(
                  color: AppColors.muted,
                  fontSize: 14,
                ),
              ),
              const SizedBox(width: 8),
              Text(
                '${progressValue.round()}%',
                style: AppTextStyles.body.copyWith(
                  color: businessGreen,
                  fontWeight: FontWeight.w900,
                  fontSize: 15,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(999),
                  child: LinearProgressIndicator(
                    value: progress.clamp(0, 1),
                    minHeight: 6,
                    backgroundColor: AppColors.line,
                    valueColor: const AlwaysStoppedAnimation(businessGreen),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              const Icon(
                LucideIcons.calendarDays,
                size: 16,
                color: AppColors.subtle,
              ),
              const SizedBox(width: 6),
              Flexible(
                flex: 5,
                child: Text(
                  '开始时间  $startDate',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppTextStyles.body.copyWith(
                    color: AppColors.muted,
                    fontSize: 14,
                  ),
                ),
              ),
              const SizedBox(width: 8),
              Flexible(
                flex: 3,
                child: FilledActionButton(
                  label: '编辑',
                  foreground: AppColors.greenDark,
                  background: AppColors.greenSoft,
                  borderColor: AppColors.greenSoft,
                  icon: LucideIcons.pencil,
                  height: 38,
                  onTap: selectionMode
                      ? null
                      : () => Navigator.of(context).push(
                            MaterialPageRoute(
                              builder: (_) => FarmCycleFormPage(
                                repository: repository,
                                cycleId: record.id,
                                initialRecord: record,
                                onBottomTabChanged: onBottomTabChanged,
                              ),
                            ),
                          ),
                ),
              ),
              const SizedBox(width: 8),
              Flexible(
                flex: 3,
                child: FilledActionButton(
                  label: '记农事',
                  foreground: AppColors.greenDark,
                  background: AppColors.greenSoft,
                  borderColor: AppColors.greenSoft,
                  icon: LucideIcons.squarePen,
                  height: 38,
                  onTap: selectionMode
                      ? null
                      : () => Navigator.of(context).push(
                            MaterialPageRoute(
                              builder: (_) => FarmLogCreatePage(
                                repository: repository,
                                onBottomTabChanged: onBottomTabChanged,
                              ),
                            ),
                          ),
                ),
              ),
              const SizedBox(width: 8),
              Flexible(
                flex: 3,
                child: FilledActionButton(
                  label: '查看账本',
                  foreground: businessBlue,
                  background: AppColors.blueSoft,
                  borderColor: AppColors.blueSoft,
                  icon: LucideIcons.bookOpenText,
                  height: 38,
                  onTap:
                      selectionMode ? null : () => onBottomTabChanged?.call(3),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class CycleVisualCard extends StatelessWidget {
  const CycleVisualCard({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(12, 12, 12, 12),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(businessCardRadius),
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Colors.white, Color(0xFFFBFEFC), Color(0xFFF2FBF5)],
        ),
        border: Border.all(color: const Color(0xFFE7EEF4)),
        boxShadow: const [
          BoxShadow(
            color: Color(0x0B163C2E),
            blurRadius: 18,
            offset: Offset(0, 8),
          ),
        ],
      ),
      child: child,
    );
  }
}

class StagePreviewCard extends StatelessWidget {
  const StagePreviewCard({super.key, required this.stages});

  final List<({String name, String days})> stages;

  @override
  Widget build(BuildContext context) {
    return BusinessCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const BusinessCardHeader(title: '阶段预览', icon: LucideIcons.gitBranch),
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 2, 20, 16),
            child: stages.isEmpty
                ? Text(
                    '选择作物模板后显示阶段预览。',
                    style: AppTextStyles.body.copyWith(
                      color: AppColors.muted,
                      fontWeight: FontWeight.w600,
                    ),
                  )
                : Column(
                    children: [
                      for (var i = 0; i < stages.length; i++)
                        Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Column(
                              children: [
                                Container(
                                  width: 12,
                                  height: 12,
                                  decoration: const BoxDecoration(
                                    color: businessGreen,
                                    shape: BoxShape.circle,
                                  ),
                                ),
                                if (i != stages.length - 1)
                                  Container(
                                    width: 2,
                                    height: 40,
                                    color:
                                        businessGreen.withValues(alpha: 0.48),
                                  ),
                              ],
                            ),
                            const SizedBox(width: 14),
                            Expanded(
                              child: Container(
                                height: 38,
                                margin: const EdgeInsets.only(bottom: 10),
                                padding:
                                    const EdgeInsets.symmetric(horizontal: 14),
                                decoration: BoxDecoration(
                                  color: AppColors.greenSoft
                                      .withValues(alpha: 0.38),
                                  borderRadius: BorderRadius.circular(10),
                                  border: Border.all(color: AppColors.lineSoft),
                                ),
                                child: Row(
                                  children: [
                                    Expanded(
                                      child: Text(
                                        stages[i].name,
                                        style: AppTextStyles.body.copyWith(
                                          color: AppColors.ink,
                                          fontWeight: FontWeight.w700,
                                        ),
                                      ),
                                    ),
                                    Text(
                                      stages[i].days,
                                      style: AppTextStyles.body.copyWith(
                                        color: AppColors.ink,
                                        fontWeight: FontWeight.w700,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ),
                          ],
                        ),
                    ],
                  ),
          ),
        ],
      ),
    );
  }
}

CycleSummaryBanner _cycleSummaryBanner(List<ApiRecord> items) {
  final summary = _CycleSummary.from(items);
  return CycleSummaryBanner(
    asset: AppAssets.businessCycleWideBanner,
    cycleCount: items.length,
    totalAreaText: summary.totalAreaText,
    currentStageText: summary.currentStageText,
    activeCount: summary.activeCount,
    plannedCount: summary.plannedCount,
    endedCount: summary.endedCount,
  );
}

class _CycleSummary {
  const _CycleSummary({
    required this.totalAreaText,
    required this.currentStageText,
    required this.activeCount,
    required this.plannedCount,
    required this.endedCount,
  });

  factory _CycleSummary.from(List<ApiRecord> items) {
    var totalArea = 0.0;
    var hasArea = false;
    var activeCount = 0;
    var plannedCount = 0;
    var endedCount = 0;
    var currentStageText = '暂无';
    for (final item in items) {
      final json = item.json;
      final area = _parseDouble(json['total_area_mu'] ?? json['unit_area_mu']);
      if (area != null) {
        totalArea += area;
        hasArea = true;
      }
      final status = '${json['status'] ?? ''}'.toLowerCase();
      if (status == 'planned' || status == 'plan') {
        plannedCount++;
      } else if (status == 'ended' ||
          status == 'finished' ||
          status == 'completed') {
        endedCount++;
      } else if (status.isNotEmpty) {
        activeCount++;
      }
      if (currentStageText == '暂无') {
        currentStageText = _firstNonEmpty(
          [json['current_stage_name']],
          fallback: '暂无',
        );
      }
    }
    return _CycleSummary(
      totalAreaText: hasArea ? '${_trimNumber(totalArea)}亩' : '暂无',
      currentStageText: currentStageText,
      activeCount: activeCount,
      plannedCount: plannedCount,
      endedCount: endedCount,
    );
  }

  final String totalAreaText;
  final String currentStageText;
  final int activeCount;
  final int plannedCount;
  final int endedCount;
}

String _todayText() {
  return _dateText(DateTime.now());
}

String _dateText(DateTime date) {
  final month = date.month.toString().padLeft(2, '0');
  final day = date.day.toString().padLeft(2, '0');
  return '${date.year}-$month-$day';
}

String _templateDisplayName(ApiRecord? template) {
  if (template == null) return '选择作物模板';
  final json = template.json;
  final name = _firstNonEmpty([json['name']], fallback: '未命名模板');
  final variety = _firstNonEmpty([json['variety']]);
  return variety.isEmpty ? name : '$name / $variety';
}

String _templateSubtitle(ApiRecord template) {
  final stages = _templateStages(template);
  final days = _firstNonEmpty([template.json['total_cycle_days']]);
  final parts = <String>[
    '${stages.length} 个阶段',
    if (days.isNotEmpty) '周期 $days 天',
  ];
  return parts.join(' · ');
}

String _defaultCycleName(ApiRecord template) {
  final start = DateTime.tryParse(_todayText()) ?? DateTime.now();
  final season = _seasonFromMonth(start.month);
  final name = _firstNonEmpty([template.json['name']], fallback: '新茬口');
  return '$season$name';
}

String _seasonFromMonth(int month) {
  if (month >= 3 && month <= 5) return '春季';
  if (month >= 6 && month <= 8) return '夏季';
  if (month >= 9 && month <= 11) return '秋季';
  return '冬季';
}

List<({String name, String days})> _templateStages(ApiRecord? template) {
  final rawStages = template?.json['stages'];
  if (rawStages is! List) return const [];
  return rawStages.whereType<Map>().map((stage) {
    final name = _firstNonEmpty([stage['name']], fallback: '未命名阶段');
    final days = _firstNonEmpty([stage['duration_days']], fallback: '-');
    return (name: name, days: '$days天');
  }).toList();
}

String _firstNonEmpty(List<Object?> values, {String fallback = ''}) {
  for (final value in values) {
    final text = '$value'.trim();
    if (value != null && text.isNotEmpty && text != 'null') return text;
  }
  return fallback;
}

double? _parseDouble(Object? value) {
  if (value == null) return null;
  if (value is num) return value.toDouble();
  return double.tryParse('$value');
}

String _trimNumber(double value) {
  if (value == value.roundToDouble()) return value.round().toString();
  return value.toStringAsFixed(1);
}
