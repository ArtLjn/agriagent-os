import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../data/repositories/business_repository.dart';
import '../../shared/assets/app_assets.dart';
import '../../theme/app_colors.dart';
import 'business_ui.dart';

class FarmLogCreatePage extends StatefulWidget {
  const FarmLogCreatePage({
    super.key,
    required this.repository,
    this.onBottomTabChanged,
  });

  static const routePath = '/farm-log-create';

  final BusinessRepository repository;
  final ValueChanged<int>? onBottomTabChanged;

  @override
  State<FarmLogCreatePage> createState() => _FarmLogCreatePageState();
}

class _FarmLogCreatePageState extends State<FarmLogCreatePage> {
  final _operationType = TextEditingController();
  final _operationDate = TextEditingController(text: _todayText());
  final _note = TextEditingController();
  int? _selectedCycleId;
  String _selectedCycleName = '';
  bool _saving = false;

  @override
  void dispose() {
    _operationType.dispose();
    _operationDate.dispose();
    _note.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (_saving) return;
    setState(() => _saving = true);
    try {
      await widget.repository.createFarmLog({
        'cycle_id': _selectedCycleId,
        'operation_type': _operationType.text.trim(),
        'operation_date': _operationDate.text.trim(),
        'note': _note.text.trim(),
      }..removeWhere((_, value) => value == null || value == ''));
      _showMessage('保存农事成功');
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
      title: '记农事',
      trailingIcon: LucideIcons.history,
      bottomBar: BottomActions(
        secondaryLabel: '取消',
        primaryLabel: _saving ? '保存中' : '保存农事',
        onPrimary: _save,
        onSecondary: () => Navigator.of(context).maybePop(),
        showTabs: true,
        onBottomTabChanged: widget.onBottomTabChanged,
      ),
      children: [
        const AiLandscapeBanner(
          title: '农事记录',
          subtitle: '记录作业过程，后续可用于复盘和报表',
          asset: AppAssets.recordQuickFarm,
          accent: AppColors.green,
        ),
        FormRowsCard(
          title: '作业信息',
          icon: LucideIcons.leaf,
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
              label: '作业类型',
              value: '',
              controller: _operationType,
              hintText: '输入作业类型',
              chevron: true,
            ),
            BusinessFormRow(
              label: '作业日期',
              value: '',
              controller: _operationDate,
              hintText: '选择日期',
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
          text: '保存后同步到农事记录',
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
