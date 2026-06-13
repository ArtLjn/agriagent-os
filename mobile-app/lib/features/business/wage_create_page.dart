import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../data/repositories/business_repository.dart';
import '../../shared/assets/app_assets.dart';
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
  final _workDate = TextEditingController(text: _todayText());
  final _quantity = TextEditingController();
  final _unitPrice = TextEditingController();
  final _paidAmount = TextEditingController();
  final _note = TextEditingController();
  String _payType = 'daily';
  int? _selectedCycleId;
  String _selectedCycleName = '';
  bool _saving = false;

  @override
  void dispose() {
    _workerName.dispose();
    _operationType.dispose();
    _workDate.dispose();
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
        'work_date': _workDate.text.trim(),
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
        const AiLandscapeBanner(
          title: '工资记录',
          subtitle: '记录用工工资，自动同步人工成本',
          asset: AppAssets.recordQuickWage,
          accent: AppColors.amber,
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
            BusinessFormRow(
              label: '工人姓名',
              value: '',
              controller: _workerName,
              hintText: '输入或选择工人',
              chevron: true,
            ),
            BusinessFormRow(
              label: '作业类型',
              value: '',
              controller: _operationType,
              hintText: '输入作业类型',
            ),
            BusinessFormRow(
              label: '作业日期',
              value: '',
              controller: _workDate,
              hintText: '选择日期',
              chevron: true,
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
        const AssistEntryCard(
          text: '保存后同步到账本人工成本',
          icon: LucideIcons.badgeCheck,
        ),
      ],
    );
  }
}

String _todayText() {
  final now = DateTime.now();
  final month = now.month.toString().padLeft(2, '0');
  final day = now.day.toString().padLeft(2, '0');
  return '${now.year}-$month-$day';
}
