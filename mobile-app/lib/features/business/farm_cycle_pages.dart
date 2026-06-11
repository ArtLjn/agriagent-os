import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../data/api/api_models.dart';
import '../../data/repositories/business_repository.dart';
import '../../shared/assets/app_assets.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';
import 'business_ui.dart';
import 'farm_log_create_page.dart';

class FarmCycleListPage extends StatelessWidget {
  const FarmCycleListPage({
    super.key,
    required this.repository,
    this.onBottomTabChanged,
  });

  static const routePath = '/farm-cycle-list';

  final BusinessRepository repository;
  final ValueChanged<int>? onBottomTabChanged;

  @override
  Widget build(BuildContext context) {
    return BusinessPageFrame(
      title: '茬口管理',
      trailingIcon: LucideIcons.slidersHorizontal,
      showBottomTabs: true,
      onBottomTabChanged: onBottomTabChanged,
      bottomOverlay: CycleCreateFab(
        label: '新建茬口',
        onTap: () => Navigator.of(context).push(
          MaterialPageRoute(
            builder: (_) => FarmCycleFormPage(
              repository: repository,
              onBottomTabChanged: onBottomTabChanged,
            ),
          ),
        ),
      ),
      children: [
        FutureBuilder<PageResult<ApiRecord>>(
          future: repository.listCycles(),
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
                if (items.isEmpty && snapshot.hasError)
                  const BusinessCard(
                    padding: EdgeInsets.all(18),
                    child: Text('茬口数据加载失败，请稍后重试。'),
                  )
                else if (items.isEmpty)
                  const BusinessCard(
                    padding: EdgeInsets.all(18),
                    child: Text('还没有茬口，先新建一个生产批次。'),
                  )
                else
                  Column(
                    children: [
                      for (final item in items) ...[
                        CycleListCard(
                          record: item,
                          repository: repository,
                          onBottomTabChanged: onBottomTabChanged,
                        ),
                        const SizedBox(height: 12),
                      ],
                    ],
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
    this.onBottomTabChanged,
  });

  static const routePath = '/farm-cycle-form';

  final BusinessRepository repository;
  final int? cycleId;
  final ValueChanged<int>? onBottomTabChanged;

  @override
  State<FarmCycleFormPage> createState() => _FarmCycleFormPageState();
}

class _FarmCycleFormPageState extends State<FarmCycleFormPage> {
  final _name = TextEditingController();
  final _templateId = TextEditingController();
  final _startDate = TextEditingController(text: _todayText());
  final _field = TextEditingController();
  final _area = TextEditingController();
  final _season = TextEditingController();
  final _note = TextEditingController();
  bool _saving = false;

  @override
  void dispose() {
    _name.dispose();
    _templateId.dispose();
    _startDate.dispose();
    _field.dispose();
    _area.dispose();
    _season.dispose();
    _note.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (_saving) return;
    setState(() => _saving = true);
    try {
      await widget.repository.saveCycle(
        {
          'name': _name.text.trim(),
          'crop_template_id': int.tryParse(_templateId.text.trim()),
          'start_date': _startDate.text.trim(),
          'field_name': _field.text.trim(),
          'total_area_mu': num.tryParse(_area.text.trim()) ?? _area.text.trim(),
          'season': _season.text.trim(),
          'batch_note': _note.text.trim(),
        }..removeWhere((_, value) => value == null || value == ''),
        cycleId: widget.cycleId,
      );
      _showMessage('创建茬口成功');
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
      title: widget.cycleId == null ? '新建茬口' : '编辑茬口',
      trailingIcon: LucideIcons.sparkles,
      bottomBar: BottomActions(
        secondaryLabel: '保存草稿',
        primaryLabel: _saving ? '保存中' : '创建茬口',
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
              value: '',
              controller: _templateId,
              hintText: '输入模板 ID',
              chevron: true,
            ),
            BusinessFormRow(
              label: '开始日期',
              value: '',
              controller: _startDate,
              hintText: '选择日期',
              chevron: true,
            ),
            BusinessFormRow(
              label: '地块',
              value: '',
              controller: _field,
              hintText: '输入地块',
            ),
          ],
        ),
        FormRowsCard(
          title: '面积与季节',
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
              label: '季节',
              value: '',
              controller: _season,
              hintText: '输入季节',
            ),
            BusinessFormRow(
              label: '备注',
              value: '',
              controller: _note,
              hintText: '补充说明',
            ),
          ],
        ),
        const StagePreviewCard(stages: []),
      ],
    );
  }
}

class CycleListCard extends StatelessWidget {
  const CycleListCard({
    super.key,
    required this.record,
    required this.repository,
    this.onBottomTabChanged,
  });

  final ApiRecord record;
  final BusinessRepository repository;
  final ValueChanged<int>? onBottomTabChanged;

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
                  label: '记农事',
                  foreground: AppColors.greenDark,
                  background: AppColors.greenSoft,
                  borderColor: AppColors.greenSoft,
                  icon: LucideIcons.squarePen,
                  height: 38,
                  onTap: () => Navigator.of(context).push(
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
                  onTap: () => onBottomTabChanged?.call(3),
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
  final now = DateTime.now();
  final month = now.month.toString().padLeft(2, '0');
  final day = now.day.toString().padLeft(2, '0');
  return '${now.year}-$month-$day';
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
