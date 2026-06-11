import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../data/api/api_models.dart';
import '../../data/repositories/business_repository.dart';
import '../../shared/assets/app_assets.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';
import 'business_ui.dart';

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
        const CycleSummaryBanner(asset: AppAssets.businessCycleWideBanner),
        const SearchFieldCard(text: '搜索作物、地块、茬口'),
        const ChipRail(
          items: ['全部', '在种', '计划', '已结束'],
          activeColor: businessGreen,
        ),
        FutureBuilder<PageResult<ApiRecord>>(
          future: repository.listCycles(),
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return const LoadingCard();
            }
            final items = snapshot.data?.items ?? const <ApiRecord>[];
            if (items.isEmpty && snapshot.hasError) {
              return const BusinessCard(
                padding: EdgeInsets.all(18),
                child: Text('还没有茬口，先新建一个生产批次。'),
              );
            }
            return Column(
              children: [
                for (var index = 0;
                    index < _cycleFallbacks.length;
                    index++) ...[
                  CycleListCard(
                    record: index < items.length ? items[index] : null,
                    index: index,
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
  final _name = TextEditingController(text: '西瓜春茬');
  final _templateId = TextEditingController(text: '8424西瓜');
  final _startDate = TextEditingController(text: '2026-04-01');
  final _field = TextEditingController(text: '东大棚');
  final _area = TextEditingController(text: '8.6');
  final _season = TextEditingController(text: '春季');
  final _note = TextEditingController(text: '第一批试种');
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
        .showSnackBar(SnackBar(content: Text(message)));
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
            BusinessFormRow(label: '茬口名称', value: '西瓜春茬', controller: _name),
            BusinessFormRow(
              label: '作物模板',
              value: '8424西瓜',
              controller: _templateId,
              chevron: true,
            ),
            BusinessFormRow(
              label: '开始日期',
              value: '2026-04-01',
              controller: _startDate,
              chevron: true,
            ),
            BusinessFormRow(label: '地块', value: '东大棚', controller: _field),
          ],
        ),
        FormRowsCard(
          title: '面积与季节',
          icon: LucideIcons.ruler,
          children: [
            BusinessFormRow(
              label: '面积',
              value: '8.6亩',
              controller: _area,
              keyboardType: TextInputType.number,
            ),
            BusinessFormRow(label: '季节', value: '春季', controller: _season),
            BusinessFormRow(label: '备注', value: '第一批试种', controller: _note),
          ],
        ),
        const StagePreviewCard(),
      ],
    );
  }
}

class CycleListCard extends StatelessWidget {
  const CycleListCard({super.key, this.record, this.index = 0});

  final ApiRecord? record;
  final int index;

  @override
  Widget build(BuildContext context) {
    final json = record?.json ?? const <String, Object?>{};
    final fallback = _cycleFallbacks[index % _cycleFallbacks.length];
    final name = fallback.name;
    final variety = fallback.variety;
    final field = fallback.field;
    final area = fallback.area;
    final stage = fallback.stage;
    final startDate = fallback.startDate;
    final progressValue =
        ((json['progress_percent'] as num?)?.toDouble() ?? fallback.progress);
    final progress = progressValue / 100;
    return CycleVisualCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              CropIllustrationAvatar(asset: fallback.asset, size: 96),
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
                            '$field  |  $area亩',
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
                color: fallback.isPlan ? businessBlue : AppColors.greenDark,
                background:
                    fallback.isPlan ? AppColors.blueSoft : AppColors.greenSoft,
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

const _cycleFallbacks = [
  _CycleFallback(
    name: '西瓜春茬',
    variety: '8424西瓜',
    field: '东大棚',
    area: '8.6',
    stage: '苗期',
    progress: 42,
    startDate: '2026-04-01',
    isPlan: false,
    asset: AppAssets.businessCropWatermelon,
  ),
  _CycleFallback(
    name: '番茄夏茬',
    variety: '普罗旺斯',
    field: '2号棚',
    area: '6',
    stage: '开花坐果期',
    progress: 68,
    startDate: '2026-03-12',
    isPlan: false,
    asset: AppAssets.businessCropTomato,
  ),
  _CycleFallback(
    name: '玉米秋茬',
    variety: '甜玉米',
    field: '北地',
    area: '4',
    stage: '计划中',
    progress: 0,
    startDate: '2026-06-20',
    isPlan: true,
    asset: AppAssets.businessCropCorn,
  ),
];

class _CycleFallback {
  const _CycleFallback({
    required this.name,
    required this.variety,
    required this.field,
    required this.area,
    required this.stage,
    required this.progress,
    required this.startDate,
    required this.isPlan,
    required this.asset,
  });

  final String name;
  final String variety;
  final String field;
  final String area;
  final String stage;
  final double progress;
  final String startDate;
  final bool isPlan;
  final String asset;
}

class StagePreviewCard extends StatelessWidget {
  const StagePreviewCard({super.key});

  static const stages = [
    ('播种期', '7天'),
    ('苗期', '18天'),
    ('伸蔓期', '22天'),
    ('开花坐果期', '25天'),
    ('采收期', '20天'),
  ];

  @override
  Widget build(BuildContext context) {
    return BusinessCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const BusinessCardHeader(title: '阶段预览', icon: LucideIcons.gitBranch),
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 2, 20, 16),
            child: Column(
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
                              color: businessGreen.withValues(alpha: 0.48),
                            ),
                        ],
                      ),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Container(
                          height: 38,
                          margin: const EdgeInsets.only(bottom: 10),
                          padding: const EdgeInsets.symmetric(horizontal: 14),
                          decoration: BoxDecoration(
                            color: AppColors.greenSoft.withValues(alpha: 0.38),
                            borderRadius: BorderRadius.circular(10),
                            border: Border.all(color: AppColors.lineSoft),
                          ),
                          child: Row(
                            children: [
                              Expanded(
                                child: Text(
                                  stages[i].$1,
                                  style: AppTextStyles.body.copyWith(
                                    color: AppColors.ink,
                                    fontWeight: FontWeight.w700,
                                  ),
                                ),
                              ),
                              Text(
                                stages[i].$2,
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
