import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../data/api/api_models.dart';
import '../../data/repositories/business_repository.dart';
import '../../theme/app_colors.dart';
import 'business_ui.dart';

class WageCreatePage extends StatefulWidget {
  const WageCreatePage({
    super.key,
    required this.repository,
    this.onBottomTabChanged,
  });

  static const routePath = '/wage-create';

  final BusinessRepository repository;
  final ValueChanged<int>? onBottomTabChanged;

  @override
  State<WageCreatePage> createState() => _WageCreatePageState();
}

class _WageCreatePageState extends State<WageCreatePage> {
  final _workerName = TextEditingController();
  final _operationType = TextEditingController();
  final _quantity = TextEditingController();
  final _unitPrice = TextEditingController();
  final _paidAmount = TextEditingController();
  final _note = TextEditingController();
  DateTime _workDateTime = DateTime.now();
  String _payType = 'daily';
  int? _selectedCycleId;
  String _selectedCycleName = '';
  bool _saving = false;

  @override
  void dispose() {
    _workerName.dispose();
    _operationType.dispose();
    _quantity.dispose();
    _unitPrice.dispose();
    _paidAmount.dispose();
    _note.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (_saving) return;
    setState(() => _saving = true);
    try {
      await widget.repository.createWage({
        'cycle_id': _selectedCycleId,
        'operation_type': _operationType.text.trim(),
        'worker_name': _workerName.text.trim(),
        'pay_type': _payType,
        'quantity':
            num.tryParse(_quantity.text.trim()) ?? _quantity.text.trim(),
        'unit_price':
            num.tryParse(_unitPrice.text.trim()) ?? _unitPrice.text.trim(),
        'paid_amount':
            num.tryParse(_paidAmount.text.trim()) ?? _paidAmount.text.trim(),
        'work_date': _workDateText,
        'recorded_at': _recordedAtPayload,
        'note': _note.text.trim(),
        'client_request_id': DateTime.now().microsecondsSinceEpoch.toString(),
      }..removeWhere((_, value) => value == null || value == ''));
      _showMessage('保存工资成功');
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

  void _selectWorker(ApiRecord worker) {
    final json = worker.json;
    setState(() {
      _workerName.text = _workerNameText(json);
      final payType = json['default_pay_type']?.toString();
      if (payType == 'daily' || payType == 'piece') {
        _payType = payType!;
      }
      final unitPrice = json['default_unit_price']?.toString() ?? '';
      if (unitPrice.isNotEmpty && _unitPrice.text.trim().isEmpty) {
        _unitPrice.text = unitPrice;
      }
    });
  }

  Future<void> _pickWorkDateTime() async {
    final pickedDate = await showDatePicker(
      context: context,
      initialDate: _workDateTime,
      firstDate: DateTime(2020),
      lastDate: DateTime.now().add(const Duration(days: 1)),
      helpText: '选择作业日期',
      cancelText: '取消',
      confirmText: '下一步',
    );
    if (pickedDate == null || !mounted) return;

    final pickedTime = await showTimePicker(
      context: context,
      initialTime: TimeOfDay.fromDateTime(_workDateTime),
      helpText: '选择作业时间',
      cancelText: '取消',
      confirmText: '确定',
    );
    if (pickedTime == null) return;

    setState(() {
      _workDateTime = DateTime(
        pickedDate.year,
        pickedDate.month,
        pickedDate.day,
        pickedTime.hour,
        pickedTime.minute,
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    return BusinessPageFrame(
      title: '记工资',
      trailingIcon: LucideIcons.history,
      bottomBar: BottomActions(
        secondaryLabel: '取消',
        primaryLabel: _saving ? '保存中' : '保存工资',
        onPrimary: _save,
        onSecondary: () => Navigator.of(context).maybePop(),
        showTabs: true,
        onBottomTabChanged: widget.onBottomTabChanged,
      ),
      children: [
        _WageAmountHero(
          payType: _payType,
          quantity: _quantity.text,
          unitPrice: _unitPrice.text,
          paidAmount: _paidAmount.text,
          onPayTypeChanged: (value) => setState(() => _payType = value),
        ),
        FormRowsCard(
          title: '用工信息',
          icon: LucideIcons.handCoins,
          children: [
            CyclePickerFormRow(
              repository: widget.repository,
              selectedCycleId: _selectedCycleId,
              selectedCycleName: _selectedCycleName,
              onSelected: (cycle) => setState(() {
                _selectedCycleId = cycle.id;
                _selectedCycleName = cycle.name;
              }),
            ),
            ApiRecordDropdownFormRow(
              key: const Key('worker-dropdown-search'),
              label: '工人姓名',
              future: widget.repository.listWorkerSummaries(activeOnly: true),
              selectedItem: _selectedWorkerRecord(),
              placeholder: '选择工人',
              sheetTitle: '选择工人',
              sheetSubtitle: '选择后自动带出计薪方式和默认单价',
              searchHint: '搜索工人',
              emptyText: '还没有工人档案，可先到工人管理中新增。',
              optionKeyPrefix: 'worker-option',
              icon: LucideIcons.userRound,
              accent: businessGreen,
              displayNameFor: (worker) => _workerNameText(worker.json),
              subtitleFor: (worker) => _workerSubtitle(worker.json),
              onSelected: _selectWorker,
            ),
            BusinessFormRow(
              label: '作业类型',
              value: '',
              controller: _operationType,
              hintText: '输入作业类型',
            ),
            _WageDateTimeFormRow(
              label: '作业时间',
              dateText: _workDateText,
              timeText: _workTimeText,
              onTap: _pickWorkDateTime,
            ),
          ],
        ),
        FormRowsCard(
          title: '工资金额',
          icon: LucideIcons.coins,
          children: [
            SegmentedFormRow(
              label: '计薪方式',
              options: const {'daily': '按天', 'piece': '计件'},
              value: _payType,
              onChanged: (value) => setState(() => _payType = value),
            ),
            BusinessFormRow(
              label: '数量',
              value: '',
              controller: _quantity,
              hintText: '输入数量',
              keyboardType: TextInputType.number,
            ),
            BusinessFormRow(
              label: '单价',
              value: '',
              controller: _unitPrice,
              hintText: '输入单价',
              keyboardType: TextInputType.number,
            ),
            BusinessFormRow(
              label: '已付',
              value: '',
              controller: _paidAmount,
              hintText: '输入已付金额',
              keyboardType: TextInputType.number,
            ),
            BusinessFormRow(
              label: '备注',
              value: '',
              controller: _note,
              hintText: '补充说明',
            ),
          ],
        ),
      ],
    );
  }

  ApiRecord? _selectedWorkerRecord() {
    final name = _workerName.text.trim();
    if (name.isEmpty) return null;
    return ApiRecord({'name': name});
  }

  String get _workDateText => _dateText(_workDateTime);

  String get _workTimeText => _timeText(TimeOfDay.fromDateTime(_workDateTime));

  String get _recordedAtPayload {
    final value = DateTime(
      _workDateTime.year,
      _workDateTime.month,
      _workDateTime.day,
      _workDateTime.hour,
      _workDateTime.minute,
    );
    return value.toIso8601String();
  }
}

String _dateText(DateTime date) {
  final month = date.month.toString().padLeft(2, '0');
  final day = date.day.toString().padLeft(2, '0');
  return '${date.year}-$month-$day';
}

String _timeText(TimeOfDay time) {
  final hour = time.hour.toString().padLeft(2, '0');
  final minute = time.minute.toString().padLeft(2, '0');
  return '$hour:$minute';
}

String _workerNameText(Map<String, dynamic> json) {
  return json['name']?.toString() ?? '未命名工人';
}

String _workerSubtitle(Map<String, dynamic> json) {
  final payType = switch (json['default_pay_type']?.toString()) {
    'piece' => '计件',
    _ => '按天',
  };
  final price = json['default_unit_price']?.toString();
  if (price == null || price.isEmpty) return payType;
  return '$payType · 默认单价 $price';
}

class _WageDateTimeFormRow extends StatelessWidget {
  const _WageDateTimeFormRow({
    required this.label,
    required this.dateText,
    required this.timeText,
    required this.onTap,
  });

  final String label;
  final String dateText;
  final String timeText;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      key: const ValueKey('wage-datetime-row'),
      onTap: onTap,
      child: Container(
        constraints: const BoxConstraints(minHeight: 64),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        decoration: const BoxDecoration(
          border: Border(bottom: BorderSide(color: AppColors.lineSoft)),
        ),
        child: Row(
          children: [
            SizedBox(
              width: 116,
              child: Text(
                label,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  color: AppColors.muted,
                  fontSize: 16,
                  height: 23 / 16,
                  fontWeight: FontWeight.w600,
                  letterSpacing: 0,
                ),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    dateText,
                    key: const ValueKey('wage-date-text'),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: AppColors.ink,
                      fontSize: 16,
                      height: 22 / 16,
                      fontWeight: FontWeight.w800,
                      letterSpacing: 0,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    timeText,
                    key: const ValueKey('wage-time-text'),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: AppColors.subtle,
                      fontSize: 13,
                      height: 18 / 13,
                      fontWeight: FontWeight.w600,
                      letterSpacing: 0,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 8),
            const Icon(
              LucideIcons.chevronRight,
              size: 22,
              color: AppColors.subtle,
            ),
          ],
        ),
      ),
    );
  }
}

class _WageAmountHero extends StatelessWidget {
  const _WageAmountHero({
    required this.payType,
    required this.quantity,
    required this.unitPrice,
    required this.paidAmount,
    required this.onPayTypeChanged,
  });

  final String payType;
  final String quantity;
  final String unitPrice;
  final String paidAmount;
  final ValueChanged<String> onPayTypeChanged;

  @override
  Widget build(BuildContext context) {
    final q = num.tryParse(quantity.replaceAll(RegExp(r'[^0-9.]'), '')) ?? 0;
    final p = num.tryParse(unitPrice.replaceAll(RegExp(r'[^0-9.]'), '')) ?? 0;
    final total = q * p;
    final paid = num.tryParse(paidAmount.replaceAll(RegExp(r'[^0-9.]'), '')) ?? 0;
    final unpaid = total - paid;
    final isPiece = payType == 'piece';
    final accent = isPiece ? AppColors.purple : AppColors.blue;
    final accentSoft = isPiece ? AppColors.purpleSoft : AppColors.blueSoft;
    final hasTotal = total > 0;
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 18, 20, 18),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [AppColors.surface, accentSoft.withValues(alpha: 0.55)],
        ),
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: AppColors.lineSoft),
        boxShadow: const [
          BoxShadow(
            color: Color(0x08000000),
            blurRadius: 18,
            offset: Offset(0, 8),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 28,
                height: 28,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                    colors: [
                      accent,
                      accent.withValues(alpha: 0.75),
                    ],
                  ),
                  borderRadius: BorderRadius.circular(8),
                  boxShadow: [
                    BoxShadow(
                      color: accent.withValues(alpha: 0.3),
                      blurRadius: 8,
                      offset: const Offset(0, 3),
                    ),
                  ],
                ),
                child: const Icon(
                  LucideIcons.coins,
                  size: 14,
                  color: Colors.white,
                ),
              ),
              const SizedBox(width: 10),
              const Expanded(
                child: Text(
                  '工资计算',
                  style: TextStyle(
                    color: AppColors.ink,
                    fontSize: 16,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 0,
                  ),
                ),
              ),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                decoration: BoxDecoration(
                  color: accentSoft,
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      isPiece
                          ? LucideIcons.package
                          : LucideIcons.calendarDays,
                      size: 12,
                      color: accent,
                    ),
                    const SizedBox(width: 4),
                    Text(
                      isPiece ? '计件' : '按天',
                      style: TextStyle(
                        color: accent,
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
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                '¥',
                style: TextStyle(
                  color: hasTotal ? accent : AppColors.subtle,
                  fontSize: 22,
                  fontWeight: FontWeight.w800,
                  height: 1.1,
                ),
              ),
              const SizedBox(width: 2),
              Flexible(
                child: FittedBox(
                  fit: BoxFit.scaleDown,
                  alignment: Alignment.centerLeft,
                  child: AnimatedSwitcher(
                    duration: const Duration(milliseconds: 240),
                    transitionBuilder: (child, anim) => FadeTransition(
                      opacity: anim,
                      child: SlideTransition(
                        position: Tween<Offset>(
                          begin: const Offset(0, 0.08),
                          end: Offset.zero,
                        ).animate(anim),
                        child: child,
                      ),
                    ),
                    child: Text(
                      hasTotal ? _trimNumber(total) : '0',
                      key: ValueKey('wage-total-$total'),
                      style: TextStyle(
                        color: hasTotal ? AppColors.ink : AppColors.subtle,
                        fontSize: 40,
                        fontWeight: FontWeight.w900,
                        height: 1.05,
                        letterSpacing: -0.5,
                      ),
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 8),
              Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: Text(
                  hasTotal
                      ? (isPiece ? '$_trimQ($q) × $_trimQ($p)' : '$q 天 × ¥$p')
                      : '输入数量与单价',
                  style: TextStyle(
                    color: hasTotal ? AppColors.muted : AppColors.subtle,
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          if (hasTotal && paid > 0)
            Container(
              padding:
                  const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
              decoration: BoxDecoration(
                color: AppColors.surface.withValues(alpha: 0.7),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Row(
                children: [
                  const Icon(
                    LucideIcons.wallet,
                    size: 13,
                    color: AppColors.subtle,
                  ),
                  const SizedBox(width: 5),
                  const Text(
                    '已付',
                    style: TextStyle(
                      color: AppColors.muted,
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const Spacer(),
                  Text(
                    '¥${_trimNumber(paid)}',
                    style: const TextStyle(
                      color: AppColors.greenDark,
                      fontSize: 13,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  const SizedBox(width: 10),
                  Container(
                    width: 1,
                    height: 12,
                    color: AppColors.line,
                  ),
                  const SizedBox(width: 10),
                  const Text(
                    '未付',
                    style: TextStyle(
                      color: AppColors.muted,
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(width: 5),
                  Text(
                    unpaid > 0 ? '¥${_trimNumber(unpaid)}' : '已结清',
                    style: TextStyle(
                      color: unpaid > 0 ? AppColors.red : AppColors.subtle,
                      fontSize: 13,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ],
              ),
            )
          else
            Row(
              children: [
                _WageHint(icon: LucideIcons.userRound, text: '选择工人'),
                const SizedBox(width: 14),
                _WageHint(icon: LucideIcons.hash, text: '填数量'),
                const SizedBox(width: 14),
                _WageHint(icon: LucideIcons.circleDollarSign, text: '填单价'),
              ],
            ),
        ],
      ),
    );
  }
}

class _WageHint extends StatelessWidget {
  const _WageHint({required this.icon, required this.text});

  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 11, color: AppColors.subtle),
        const SizedBox(width: 4),
        Text(
          text,
          style: const TextStyle(
            color: AppColors.subtle,
            fontSize: 11.5,
            fontWeight: FontWeight.w600,
          ),
        ),
      ],
    );
  }
}

String _trimNumber(num value) {
  if (value == value.toInt()) return '${value.toInt()}';
  return value.toStringAsFixed(2).replaceAll(RegExp(r'0+$'), '').replaceAll(RegExp(r'\.$'), '');
}

String _trimQ(num value) {
  if (value == value.toInt()) return '${value.toInt()}';
  return value.toStringAsFixed(1);
}
