import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../data/api/api_models.dart';
import '../../data/repositories/business_repository.dart';
import '../../shared/assets/app_assets.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';
import 'business_ui.dart';

class WorkerListPage extends StatelessWidget {
  const WorkerListPage({
    super.key,
    required this.repository,
    this.onBottomTabChanged,
  });

  static const routePath = '/worker-list';

  final BusinessRepository repository;
  final ValueChanged<int>? onBottomTabChanged;

  @override
  Widget build(BuildContext context) {
    return BusinessPageFrame(
      title: '工人管理',
      trailingIcon: LucideIcons.slidersHorizontal,
      showBottomTabs: true,
      onBottomTabChanged: onBottomTabChanged,
      children: [
        const WorkerSummaryBanner(
          asset: AppAssets.businessWorkerHatBanner,
        ),
        Row(
          children: [
            Expanded(
              child: FilledActionButton(
                label: '记一笔工资',
                foreground: Colors.white,
                background: businessBlue,
                borderColor: businessBlue,
                icon: LucideIcons.squarePen,
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
                      repository: repository,
                      onBottomTabChanged: onBottomTabChanged,
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
        const SearchFieldCard(text: '搜索工人姓名'),
        const ChipRail(items: ['全部', '有欠款', '已结清', '停用']),
        FutureBuilder<PageResult<ApiRecord>>(
          future: repository.listWorkerSummaries(),
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return const LoadingCard();
            }
            final items = snapshot.data?.items ?? const <ApiRecord>[];
            if (items.isEmpty && snapshot.hasError) {
              return const BusinessCard(
                padding: EdgeInsets.all(18),
                child: Text('还没有工人档案。'),
              );
            }
            return Column(
              children: [
                for (var index = 0; index < _workerFallbacks.length; index++) ...[
                  WorkerListCard(
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
  final _name = TextEditingController(text: '老王');
  final _phone = TextEditingController(text: '138 0000 0000');
  final _unitPrice = TextEditingController(text: '200 元/天');
  final _note = TextEditingController(text: '西瓜茬口常用工');
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
        .showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    return BusinessPageFrame(
      title: widget.workerId == null ? '新增工人' : '编辑工人',
      bottomBar: BottomActions(
        secondaryLabel: '取消',
        primaryLabel: _saving ? '保存中' : '保存工人',
        onPrimary: _save,
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
            BusinessFormRow(label: '姓名', value: '老王', controller: _name),
            BusinessFormRow(
                label: '手机号', value: '138 0000 0000', controller: _phone),
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
              value: '200 元/天',
              controller: _unitPrice,
            ),
          ],
        ),
        FormRowsCard(
          title: '备注与标签',
          icon: LucideIcons.tags,
          children: [
            const BusinessFormRow(
                label: '标签', value: '常用工    授粉熟练', chevron: true),
            BusinessFormRow(label: '备注', value: '西瓜茬口常用工', controller: _note),
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
  const WorkerListCard({super.key, this.record, this.index = 0});

  final ApiRecord? record;
  final int index;

  @override
  Widget build(BuildContext context) {
    final json = record?.json ?? const <String, Object?>{};
    final fallback = _workerFallbacks[index % _workerFallbacks.length];
    final name = fallback.name;
    final unitPrice = fallback.unitPrice;
    final unpaid = json['unpaid_amount'] ?? fallback.unpaid;
    final isSettled = unpaid == 0 || '$unpaid' == '0';
    return BusinessCard(
      padding: const EdgeInsets.fromLTRB(12, 14, 12, 14),
      child: Row(
        children: [
          AssetAvatar(
            asset: fallback.asset,
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
                    SoftPill(
                      text: '常用',
                      color: businessBlue,
                      background: AppColors.blueSoft,
                    ),
                    const SizedBox(width: 6),
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
                    SoftPill(
                      text: fallback.primaryCycle,
                      color: AppColors.greenDark,
                      background: AppColors.greenSoft,
                    ),
                    const SizedBox(width: 6),
                    if (fallback.secondaryCycle != null)
                      SoftPill(
                        text: fallback.secondaryCycle!,
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
                      fallback.phone,
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

const _workerFallbacks = [
  _WorkerFallback(
    name: '老王',
    phone: '138 0011 2233',
    unitPrice: '200',
    unpaid: '400',
    primaryCycle: '西瓜春茬',
    secondaryCycle: '豆角春茬',
    asset: AppAssets.businessWorkerAvatar1,
  ),
  _WorkerFallback(
    name: '老李',
    phone: '139 0022 3344',
    unitPrice: '220',
    unpaid: '660',
    primaryCycle: '西瓜春茬',
    secondaryCycle: null,
    asset: AppAssets.businessWorkerAvatar2,
  ),
  _WorkerFallback(
    name: '小赵',
    phone: '137 0033 4455',
    unitPrice: '180',
    unpaid: 0,
    primaryCycle: '豆角春茬',
    secondaryCycle: null,
    asset: AppAssets.businessWorkerAvatar1,
  ),
];

class _WorkerFallback {
  const _WorkerFallback({
    required this.name,
    required this.phone,
    required this.unitPrice,
    required this.unpaid,
    required this.primaryCycle,
    required this.secondaryCycle,
    required this.asset,
  });

  final String name;
  final String phone;
  final String unitPrice;
  final Object unpaid;
  final String primaryCycle;
  final String? secondaryCycle;
  final String asset;
}
