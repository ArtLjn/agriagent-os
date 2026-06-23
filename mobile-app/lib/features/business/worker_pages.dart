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

class WorkerListPage extends StatefulWidget {
  const WorkerListPage({
    super.key,
    required this.repository,
    this.onBottomTabChanged,
  });

  static const routePath = '/worker-list';

  final BusinessRepository repository;
  final ValueChanged<int>? onBottomTabChanged;

  @override
  State<WorkerListPage> createState() => _WorkerListPageState();
}

class _WorkerListPageState extends State<WorkerListPage> {
  late Future<PageResult<ApiRecord>> _workersFuture;
  final _searchController = TextEditingController();
  int _filterIndex = 0;

  static const _filters = ['全部', '有欠款', '已结清', '离职'];

  @override
  void initState() {
    super.initState();
    _workersFuture = widget.repository.listWorkerSummaries();
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  void _reloadWorkers() {
    setState(() {
      _workersFuture = widget.repository.listWorkerSummaries();
    });
  }

  @override
  Widget build(BuildContext context) {
    return BusinessPageFrame(
      title: '工人管理',
      trailingIcon: LucideIcons.slidersHorizontal,
      showBottomTabs: true,
      onBottomTabChanged: widget.onBottomTabChanged,
      bottomOverlay: _WorkerCreatePill(
        label: '新增工人',
        onTap: () => Navigator.of(context).push(
          MaterialPageRoute(
            builder: (_) => WorkerFormPage(
              repository: widget.repository,
              onBottomTabChanged: widget.onBottomTabChanged,
            ),
          ),
        ),
      ),
      children: [
        FutureBuilder<PageResult<ApiRecord>>(
          future: _workersFuture,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  _workerSummaryHero(const _WorkerSummary(
                    unpaidText: '0',
                    workerCount: 0,
                    monthlyWorkCount: 0,
                    relatedCycleCount: 0,
                  )),
                  const SizedBox(height: 16),
                  const LoadingCard(),
                ],
              );
            }
            final items = snapshot.data?.items ?? const <ApiRecord>[];
            final visibleItems = _filterWorkers(
              items,
              query: _searchController.text,
              filterIndex: _filterIndex,
            );
            final summary = _workerSummary(visibleItems);
            return Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                _workerSummaryHero(summary),
                const SizedBox(height: 16),
                SearchFieldCard(
                  text: '搜索工人姓名',
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
                  emptyMessage: '还没有工人档案。',
                  errorMessage: '工人档案加载失败，请稍后重试。',
                  deleteTitle: '工人档案',
                  deleteSuccessName: '工人档案',
                  onDeleteRecord: widget.repository.deleteWorker,
                  onDeleted: _reloadWorkers,
                  cardBuilder: (record, selectionMode, selected) =>
                      WorkerListCard(
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

_WorkerSummaryHero _workerSummaryHero(_WorkerSummary summary) {
  return _WorkerSummaryHero(
    unpaidText: summary.unpaidText,
    workerCount: summary.workerCount,
    monthlyWorkCount: summary.monthlyWorkCount,
    relatedCycleCount: summary.relatedCycleCount,
  );
}

class _WorkerSummaryHero extends StatelessWidget {
  const _WorkerSummaryHero({
    required this.unpaidText,
    required this.workerCount,
    required this.monthlyWorkCount,
    required this.relatedCycleCount,
  });

  final String unpaidText;
  final int workerCount;
  final int monthlyWorkCount;
  final int relatedCycleCount;

  @override
  Widget build(BuildContext context) {
    final unpaidValue = num.tryParse(unpaidText) ?? 0;
    final hasUnpaid = unpaidValue > 0;
    return TexturedCard(
      accent: hasUnpaid ? AppColors.red : AppColors.blue,
      padding: const EdgeInsets.fromLTRB(20, 18, 20, 18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              GradientIconTile(
                icon: LucideIcons.users,
                accent: hasUnpaid ? AppColors.red : AppColors.blue,
                size: 32,
                iconSize: 17,
                borderRadius: 10,
              ),
              const SizedBox(width: 10),
              const Expanded(
                child: Text(
                  '工人概览',
                  style: TextStyle(
                    color: AppColors.ink,
                    fontSize: 16,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 0,
                  ),
                ),
              ),
              if (hasUnpaid)
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                  decoration: BoxDecoration(
                    color: AppColors.redSoft,
                    borderRadius: BorderRadius.circular(999),
                  ),
                  child: const Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(
                        LucideIcons.circleAlert,
                        size: 12,
                        color: AppColors.red,
                      ),
                      SizedBox(width: 4),
                      Text(
                        '有欠款',
                        style: TextStyle(
                          color: AppColors.red,
                          fontSize: 12,
                          fontWeight: FontWeight.w800,
                          letterSpacing: 0.1,
                        ),
                      ),
                    ],
                  ),
                ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: _MetricValue(
                  value: '¥$unpaidText',
                  label: '未结金额',
                  accent: hasUnpaid ? AppColors.red : AppColors.ink,
                ),
              ),
              Container(
                width: 1,
                height: 44,
                margin: const EdgeInsets.symmetric(horizontal: 12),
                color: AppColors.line,
              ),
              Expanded(
                child: _MetricValue(
                  value: '$workerCount',
                  unit: '人',
                  label: '工人总数',
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            decoration: BoxDecoration(
              color: AppColors.surface2,
              borderRadius: BorderRadius.circular(12),
            ),
            child: Row(
              children: [
                const Icon(
                  LucideIcons.calendarClock,
                  size: 13,
                  color: AppColors.subtle,
                ),
                const SizedBox(width: 5),
                const Text(
                  '本月用工',
                  style: TextStyle(
                    color: AppColors.muted,
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const Spacer(),
                Text(
                  '$monthlyWorkCount 次',
                  style: const TextStyle(
                    color: AppColors.ink,
                    fontSize: 13,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(width: 12),
                Container(
                  width: 1,
                  height: 12,
                  color: AppColors.line,
                ),
                const SizedBox(width: 12),
                const Text(
                  '相关茬口',
                  style: TextStyle(
                    color: AppColors.muted,
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(width: 5),
                Text(
                  '$relatedCycleCount',
                  style: const TextStyle(
                    color: AppColors.ink,
                    fontSize: 13,
                    fontWeight: FontWeight.w800,
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

class _MetricValue extends StatelessWidget {
  const _MetricValue({
    required this.value,
    required this.label,
    this.unit = '',
    this.accent = AppColors.ink,
  });

  final String value;
  final String label;
  final String unit;
  final Color accent;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.baseline,
          textBaseline: TextBaseline.alphabetic,
          children: [
            Flexible(
              child: FittedBox(
                fit: BoxFit.scaleDown,
                alignment: Alignment.centerLeft,
                child: Text(
                  value,
                  maxLines: 1,
                  style: TextStyle(
                    color: accent,
                    fontSize: 24,
                    fontWeight: FontWeight.w900,
                    letterSpacing: -0.5,
                    height: 1.1,
                  ),
                ),
              ),
            ),
            if (unit.isNotEmpty) ...[
              const SizedBox(width: 2),
              Text(
                unit,
                style: const TextStyle(
                  color: AppColors.muted,
                  fontSize: 13,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ],
        ),
        const SizedBox(height: 4),
        Text(
          label,
          style: const TextStyle(
            color: AppColors.muted,
            fontSize: 12,
            fontWeight: FontWeight.w500,
            letterSpacing: 0,
          ),
        ),
      ],
    );
  }
}

class _WorkerCreatePill extends StatelessWidget {
  const _WorkerCreatePill({required this.label, required this.onTap});

  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.centerRight,
      child: AnimatedPress(
        scale: 0.92,
        onTap: onTap,
        child: Container(
          width: 56,
          height: 56,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: AppColors.ink,
            shape: BoxShape.circle,
            boxShadow: [
              BoxShadow(
                color: AppColors.ink.withValues(alpha: 0.22),
                blurRadius: 18,
                offset: const Offset(0, 8),
              ),
            ],
          ),
          child: const Icon(
            LucideIcons.plus,
            color: Colors.white,
            size: 24,
          ),
        ),
      ),
    );
  }
}

List<ApiRecord> _filterWorkers(
  List<ApiRecord> items, {
  required String query,
  required int filterIndex,
}) {
  final keyword = query.trim().toLowerCase();
  return items.where((item) {
    final json = item.json;
    final isInactive = _isInactiveWorker(json['status']);
    if (filterIndex == 0 && isInactive) return false;
    if (filterIndex == 1 &&
        (!_hasUnpaidAmount(json['unpaid_amount']) || isInactive)) {
      return false;
    }
    if (filterIndex == 2 &&
        (_hasUnpaidAmount(json['unpaid_amount']) || isInactive)) {
      return false;
    }
    if (filterIndex == 3 && !isInactive) return false;
    if (keyword.isEmpty) return true;
    final searchable = [
      json['name'],
      json['phone'],
    ].map((value) => _firstNonEmpty([value]).toLowerCase()).join(' ');
    return searchable.contains(keyword);
  }).toList(growable: false);
}

bool _hasUnpaidAmount(Object? value) => (_parseDouble(value) ?? 0) > 0;

bool _isInactiveWorker(Object? value) {
  final status = '$value'.trim().toLowerCase();
  return status == 'inactive' || status == 'disabled' || status == '离职';
}

_WorkerSummary _workerSummary(List<ApiRecord> items) {
  var unpaid = 0.0;
  final cycleIds = <String>{};
  for (final item in items) {
    final json = item.json;
    unpaid += _parseDouble(json['unpaid_amount']) ?? 0;
    final cycleId = _firstNonEmpty([json['cycle_id']]);
    if (cycleId.isNotEmpty) cycleIds.add(cycleId);
  }
  return _WorkerSummary(
    unpaidText: _trimNumber(unpaid),
    workerCount: items.length,
    monthlyWorkCount: items.fold<int>(0, (total, item) {
      final value = item.json['monthly_work_count'] ??
          item.json['work_count'] ??
          item.json['entry_count'];
      if (value is num) return total + value.toInt();
      return total + (int.tryParse('$value') ?? 0);
    }),
    relatedCycleCount: cycleIds.length,
  );
}

class _WorkerSummary {
  const _WorkerSummary({
    required this.unpaidText,
    required this.workerCount,
    required this.monthlyWorkCount,
    required this.relatedCycleCount,
  });

  final String unpaidText;
  final int workerCount;
  final int monthlyWorkCount;
  final int relatedCycleCount;
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

class WorkerFormPage extends StatefulWidget {
  const WorkerFormPage({
    super.key,
    required this.repository,
    this.workerId,
    this.initialRecord,
    this.onBottomTabChanged,
  });

  static const routePath = '/worker-form';

  final BusinessRepository repository;
  final int? workerId;
  final ApiRecord? initialRecord;
  final ValueChanged<int>? onBottomTabChanged;

  @override
  State<WorkerFormPage> createState() => _WorkerFormPageState();
}

class _WorkerFormPageState extends State<WorkerFormPage> {
  final _name = TextEditingController();
  final _phone = TextEditingController();
  final _unitPrice = TextEditingController();
  final _note = TextEditingController();
  String _payType = 'daily';
  String _status = 'active';
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
    _phone.text = _firstNonEmpty([json['phone']]);
    _unitPrice.text = _firstNonEmpty([json['default_unit_price']]);
    _note.text = _firstNonEmpty([json['note']]);
    _payType = _firstNonEmpty([json['default_pay_type']], fallback: 'daily');
    final rawStatus = _firstNonEmpty([json['status']], fallback: 'active');
    _status = _normalizeWorkerStatus(rawStatus);
  }

  @override
  void dispose() {
    _name.dispose();
    _phone.dispose();
    _unitPrice.dispose();
    _note.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (_saving) return;
    setState(() => _saving = true);
    try {
      await widget.repository.saveWorker(
          {
            'name': _name.text.trim(),
            'phone': _phone.text.trim(),
            'default_pay_type': _payType,
            'default_unit_price':
                num.tryParse(_unitPrice.text.trim()) ?? _unitPrice.text.trim(),
            'note': _note.text.trim(),
            'status': _status,
          }..removeWhere((_, value) => value == null || value == ''),
          workerId: widget.workerId ?? widget.initialRecord?.id);
      _showMessage('保存工人成功');
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
      title: widget.workerId == null ? '新增工人' : '编辑工人',
      bottomBar: BottomActions(
        secondaryLabel: '取消',
        primaryLabel: _saving ? '保存中' : '保存工人',
        onPrimary: _save,
        onSecondary: () => Navigator.of(context).maybePop(),
        showTabs: true,
        onBottomTabChanged: widget.onBottomTabChanged,
      ),
      children: [
        const AiLandscapeBanner(
          title: '工人档案',
          subtitle: '用于记工资、查欠款和茬口用工统计',
          asset: AppAssets.businessWorkerBanner,
          avatarAsset: AppAssets.businessWorkerAvatar1,
          accent: businessBlue,
        ),
        FormRowsCard(
          title: '基础信息',
          icon: LucideIcons.userRound,
          children: [
            BusinessFormRow(
              label: '姓名',
              value: '',
              controller: _name,
              hintText: '输入姓名',
            ),
            BusinessFormRow(
              label: '手机号',
              value: '',
              controller: _phone,
              hintText: '输入手机号',
            ),
            SegmentedFormRow(
              label: '状态',
              options: const {'active': '在用', 'inactive': '离职'},
              value: _status,
              onChanged: (value) => setState(() => _status = value),
            ),
          ],
        ),
        FormRowsCard(
          title: '默认工资',
          icon: LucideIcons.handCoins,
          children: [
            SegmentedFormRow(
              label: '默认计薪方式',
              options: const {'daily': '按天', 'piece': '计件'},
              value: _payType,
              onChanged: (value) => setState(() => _payType = value),
            ),
            BusinessFormRow(
              label: '默认单价',
              value: '',
              controller: _unitPrice,
              hintText: '输入默认单价',
            ),
          ],
        ),
        FormRowsCard(
          title: '备注与标签',
          icon: LucideIcons.tags,
          children: [
            BusinessFormRow(
              label: '备注',
              value: '',
              controller: _note,
              hintText: '补充说明',
            ),
          ],
        ),
        const AssistEntryCard(
          text: '保存后可在记工资时直接选择',
          icon: LucideIcons.badgeCheck,
        ),
      ],
    );
  }
}

String _normalizeWorkerStatus(String value) {
  return switch (value.trim().toLowerCase()) {
    'inactive' || 'disabled' || '离职' => 'inactive',
    _ => 'active',
  };
}

class WorkerListCard extends StatelessWidget {
  const WorkerListCard({
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
    final name = _firstNonEmpty([json['name']], fallback: '未命名工人');
    final unitPrice =
        _firstNonEmpty([json['default_unit_price']], fallback: '');
    final unpaid = json['unpaid_amount'] ?? 0;
    final isSettled = unpaid == 0 || '$unpaid' == '0';
    final phone = _firstNonEmpty([json['phone']], fallback: '未填写手机号');
    final statusLabel = _statusLabel(json['status']);
    final isActive = statusLabel == '在用';
    return AnimatedPress(
      scale: 0.99,
      onTap: selectionMode
          ? null
          : () => Navigator.of(context).push(
                MaterialPageRoute(
                  builder: (_) => WorkerFormPage(
                    repository: repository,
                    workerId: record.id,
                    initialRecord: record,
                    onBottomTabChanged: onBottomTabChanged,
                  ),
                ),
              ),
      child: Container(
        padding: const EdgeInsets.fromLTRB(16, 14, 14, 14),
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
              child: Text(
                name.isNotEmpty ? name.characters.first : '?',
                style: const TextStyle(
                  color: AppColors.ink2,
                  fontSize: 16,
                  fontWeight: FontWeight.w800,
                ),
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
                      if (statusLabel.isNotEmpty) ...[
                        const SizedBox(width: 8),
                        Text(
                          '· $statusLabel',
                          style: TextStyle(
                            color: isActive
                                ? AppColors.greenDark
                                : AppColors.subtle,
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ],
                  ),
                  const SizedBox(height: 5),
                  Row(
                    children: [
                      if (unitPrice.isNotEmpty) ...[
                        Text(
                          '¥$unitPrice/天',
                          style: const TextStyle(
                            color: AppColors.ink2,
                            fontSize: 12.5,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          '·',
                          style: TextStyle(
                            color: AppColors.line,
                            fontSize: 12,
                          ),
                        ),
                        const SizedBox(width: 8),
                      ],
                      Expanded(
                        child: Text(
                          phone,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            color: AppColors.subtle,
                            fontSize: 12.5,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(width: 8),
            if (!isSettled)
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text(
                    '未结',
                    style: TextStyle(
                      color: AppColors.red,
                      fontSize: 10,
                      fontWeight: FontWeight.w700,
                      letterSpacing: 0.1,
                    ),
                  ),
                  Text(
                    '¥$unpaid',
                    style: const TextStyle(
                      color: AppColors.red,
                      fontSize: 15,
                      fontWeight: FontWeight.w900,
                      letterSpacing: -0.3,
                      height: 1.1,
                    ),
                  ),
                ],
              )
            else
              const Icon(
                LucideIcons.check,
                color: AppColors.subtle,
                size: 18,
              ),
          ],
        ),
      ),
    );
  }
}

String _statusLabel(Object? value) {
  return switch ('$value'.trim().toLowerCase()) {
    'active' => '在用',
    'inactive' || 'disabled' => '离职',
    '' => '',
    _ => '$value',
  };
}

String _firstNonEmpty(List<Object?> values, {String fallback = ''}) {
  for (final value in values) {
    final text = '$value'.trim();
    if (value != null && text.isNotEmpty && text != 'null') return text;
  }
  return fallback;
}
