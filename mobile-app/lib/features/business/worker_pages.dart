import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../data/api/api_models.dart';
import '../../data/repositories/business_repository.dart';
import '../../shared/assets/app_assets.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';
import 'bulk_delete_ui.dart';
import 'business_ui.dart';
import 'wage_create_page.dart';

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

  @override
  void initState() {
    super.initState();
    _workersFuture = widget.repository.listWorkerSummaries();
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
      children: [
        FutureBuilder<PageResult<ApiRecord>>(
          future: _workersFuture,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return const Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  WorkerSummaryBanner(
                    asset: AppAssets.businessWorkerHatBanner,
                    unpaidText: '0',
                    workerCount: 0,
                    monthlyWorkCount: 0,
                    relatedCycleCount: 0,
                  ),
                  SizedBox(height: 13),
                  LoadingCard(),
                ],
              );
            }
            final items = snapshot.data?.items ?? const <ApiRecord>[];
            final summary = _workerSummary(items);
            return Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                WorkerSummaryBanner(
                  asset: AppAssets.businessWorkerHatBanner,
                  unpaidText: summary.unpaidText,
                  workerCount: summary.workerCount,
                  monthlyWorkCount: summary.monthlyWorkCount,
                  relatedCycleCount: summary.relatedCycleCount,
                ),
                const SizedBox(height: 13),
                Row(
                  children: [
                    Expanded(
                      child: FilledActionButton(
                        label: '记一笔工资',
                        foreground: Colors.white,
                        background: businessBlue,
                        borderColor: businessBlue,
                        icon: LucideIcons.squarePen,
                        onTap: () => Navigator.of(context).push(
                          MaterialPageRoute(
                            builder: (_) => WageCreatePage(
                              repository: widget.repository,
                              onBottomTabChanged: widget.onBottomTabChanged,
                            ),
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: FilledActionButton(
                        label: '新增工人',
                        foreground: businessBlue,
                        background: Colors.white,
                        borderColor: businessBlue,
                        icon: LucideIcons.userRoundPlus,
                        onTap: () => Navigator.of(context).push(
                          MaterialPageRoute(
                            builder: (_) => WorkerFormPage(
                              repository: widget.repository,
                              onBottomTabChanged: widget.onBottomTabChanged,
                            ),
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 13),
                const SearchFieldCard(text: '搜索工人姓名'),
                const SizedBox(height: 13),
                const ChipRail(items: ['全部', '有欠款', '已结清', '停用']),
                const SizedBox(height: 13),
                BulkDeleteListSection(
                  items: items,
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
    this.onBottomTabChanged,
  });

  static const routePath = '/worker-form';

  final BusinessRepository repository;
  final int? workerId;
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
  bool _saving = false;

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
            'status': 'active',
          }..removeWhere((_, value) => value == null || value == ''),
          workerId: widget.workerId);
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
            const BusinessFormRow(label: '状态', value: '在用', chevron: true),
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
            const BusinessFormRow(
              label: '标签',
              value: '未设置',
              chevron: true,
            ),
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

class WorkerListCard extends StatelessWidget {
  const WorkerListCard({
    super.key,
    required this.record,
    this.selectionMode = false,
    this.selected = false,
  });

  final ApiRecord record;
  final bool selectionMode;
  final bool selected;

  @override
  Widget build(BuildContext context) {
    final json = record.json;
    final name = _firstNonEmpty([json['name']], fallback: '未命名工人');
    final unitPrice =
        _firstNonEmpty([json['default_unit_price']], fallback: '未设置');
    final unpaid = json['unpaid_amount'] ?? 0;
    final isSettled = unpaid == 0 || '$unpaid' == '0';
    return BusinessCard(
      padding: const EdgeInsets.fromLTRB(12, 14, 12, 14),
      child: Row(
        children: [
          SelectionCheckbox(visible: selectionMode, selected: selected),
          AssetAvatar(
            asset: AppAssets.businessWorkerAvatar1,
            size: 74,
            background: const Color(0xFFEAF5FF),
          ),
          const SizedBox(width: 14),
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
                        style: AppTextStyles.sectionTitle.copyWith(
                          fontSize: 20,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      '$unitPrice/天',
                      style: AppTextStyles.body.copyWith(
                        color: businessBlue,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 6),
                Row(
                  children: [
                    if (_firstNonEmpty([json['status']]).isNotEmpty)
                      SoftPill(
                        text: _statusLabel(json['status']),
                        color: AppColors.greenDark,
                        background: AppColors.greenSoft,
                      ),
                  ],
                ),
                const SizedBox(height: 8),
                Row(
                  children: [
                    const Icon(
                      LucideIcons.phone,
                      size: 12,
                      color: AppColors.subtle,
                    ),
                    const SizedBox(width: 4),
                    Text(
                      _firstNonEmpty([json['phone']], fallback: '未填写手机号'),
                      style: AppTextStyles.small,
                    ),
                  ],
                ),
              ],
            ),
          ),
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                isSettled ? '结清' : '欠$unpaid元',
                style: AppTextStyles.body.copyWith(
                  color: isSettled ? businessGreen : AppColors.red,
                  fontWeight: FontWeight.w900,
                  fontSize: 18,
                ),
              ),
              const SizedBox(width: 4),
              const Icon(
                LucideIcons.chevronRight,
                size: 18,
                color: AppColors.subtle,
              ),
            ],
          ),
        ],
      ),
    );
  }
}

String _statusLabel(Object? value) {
  return switch ('$value'.trim().toLowerCase()) {
    'active' => '在用',
    'inactive' => '停用',
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
