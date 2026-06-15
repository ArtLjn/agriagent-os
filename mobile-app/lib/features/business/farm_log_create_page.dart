import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../data/repositories/business_repository.dart';
import '../../shared/assets/app_assets.dart';
import '../../theme/app_colors.dart';
import 'business_ui.dart';
import 'farm_log_hero_banner.dart';

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
  final _note = TextEditingController();
  DateTime _operationDate = _today();
  String _operationTime = '08:30';
  int? _selectedCycleId;
  String _selectedCycleName = '';
  bool _saving = false;

  @override
  void dispose() {
    _operationType.dispose();
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
        'operation_date': _operationDateText,
        'operation_time': _operationTimePayload(),
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

  String? _operationTimePayload() {
    return '${_operationDateText}T$_operationTime:00';
  }

  String get _operationDateText => _dateText(_operationDate);

  Future<void> _pickOperationDateTime() async {
    final pickedDate = await showDatePicker(
      context: context,
      initialDate: _operationDate,
      firstDate: DateTime(2020),
      lastDate: DateTime(2035),
      helpText: '选择作业日期',
      cancelText: '取消',
      confirmText: '下一步',
    );
    if (pickedDate == null || !mounted) return;

    final pickedTime = await showTimePicker(
      context: context,
      initialTime: _parseTimeOfDay(_operationTime),
      helpText: '选择作业时间',
      cancelText: '取消',
      confirmText: '确定',
    );
    if (pickedTime == null) return;

    setState(() {
      _operationDate = pickedDate;
      _operationTime = _timeText(pickedTime);
    });
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
        const FarmLogHeroBanner(
          title: '农事记录',
          subtitle: '记录作业过程，后续可用于复盘和报表',
          backgroundAsset: AppAssets.businessFarmLogBanner,
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
            ),
            FarmLogDateTimePickerCard(
              label: '作业时间',
              dateText: _operationDateText,
              timeText: _operationTime,
              onTap: _pickOperationDateTime,
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

DateTime _today() => DateTime.now();

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

TimeOfDay _parseTimeOfDay(String text) {
  final parts = text.split(':');
  if (parts.length != 2) return const TimeOfDay(hour: 8, minute: 30);
  final hour = int.tryParse(parts[0]);
  final minute = int.tryParse(parts[1]);
  if (hour == null || minute == null) {
    return const TimeOfDay(hour: 8, minute: 30);
  }
  if (hour < 0 || hour > 23 || minute < 0 || minute > 59) {
    return const TimeOfDay(hour: 8, minute: 30);
  }
  return TimeOfDay(hour: hour, minute: minute);
}

class FarmLogDateTimePickerCard extends StatelessWidget {
  const FarmLogDateTimePickerCard({
    super.key,
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
      key: const ValueKey('farm-log-datetime-card'),
      onTap: onTap,
      child: Container(
        constraints: const BoxConstraints(minHeight: 76),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
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
                    key: const ValueKey('farm-log-date-text'),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: AppColors.ink,
                      fontSize: 17,
                      height: 23 / 17,
                      fontWeight: FontWeight.w800,
                      letterSpacing: 0,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    timeText,
                    key: const ValueKey('farm-log-time-text'),
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
