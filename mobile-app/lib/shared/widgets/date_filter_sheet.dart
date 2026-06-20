import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';

enum DateRangePreset {
  currentMonth,
  previousMonth,
  last7Days,
  last30Days,
  currentYear,
  allTime,
  custom,
}

extension DateRangePresetLabel on DateRangePreset {
  String get label {
    return switch (this) {
      DateRangePreset.currentMonth => '本月',
      DateRangePreset.previousMonth => '上月',
      DateRangePreset.last7Days => '近7天',
      DateRangePreset.last30Days => '近30天',
      DateRangePreset.currentYear => '本年',
      DateRangePreset.allTime => '全部时间',
      DateRangePreset.custom => '自定义',
    };
  }
}

class DateFilterSelection {
  const DateFilterSelection({
    required this.preset,
    required this.visibleMonth,
    this.customStart,
    this.customEnd,
  });

  final DateRangePreset preset;
  final DateTime visibleMonth;
  final DateTime? customStart;
  final DateTime? customEnd;

  bool get hasCustomRange =>
      preset == DateRangePreset.custom && customStart != null && customEnd != null;
}

Future<DateFilterSelection?> showDateFilterSheet({
  required BuildContext context,
  required DateRangePreset selected,
  required DateTime visibleMonth,
  DateTime? customStart,
  DateTime? customEnd,
}) {
  return showModalBottomSheet<DateFilterSelection>(
    context: context,
    backgroundColor: Colors.transparent,
    isScrollControlled: true,
    builder: (context) {
      return DateFilterSheet(
        selected: selected,
        visibleMonth: visibleMonth,
        customStart: customStart,
        customEnd: customEnd,
      );
    },
  );
}

class DateFilterSheet extends StatefulWidget {
  const DateFilterSheet({
    super.key,
    required this.selected,
    required this.visibleMonth,
    this.customStart,
    this.customEnd,
  });

  final DateRangePreset selected;
  final DateTime visibleMonth;
  final DateTime? customStart;
  final DateTime? customEnd;

  @override
  State<DateFilterSheet> createState() => _DateFilterSheetState();
}

class _DateFilterSheetState extends State<DateFilterSheet> {
  late DateRangePreset _selected = widget.selected;
  late DateTime _visibleMonth = DateTime(
    widget.visibleMonth.year,
    widget.visibleMonth.month,
  );
  DateTime? _customStart;
  DateTime? _customEnd;

  @override
  void initState() {
    super.initState();
    _customStart = widget.customStart;
    _customEnd = widget.customEnd;
  }

  Future<void> _pickCustomRange() async {
    final now = DateTime.now();
    final initial = (_customStart != null && _customEnd != null)
        ? DateTimeRange(start: _customStart!, end: _customEnd!)
        : null;
    final picked = await showDateRangePicker(
      context: context,
      firstDate: DateTime(now.year - 5),
      lastDate: DateTime(now.year, 12, 31),
      initialDateRange: initial,
      helpText: '选择日期范围',
      locale: const Locale('zh', 'CN'),
    );
    if (picked == null) return;
    setState(() {
      _selected = DateRangePreset.custom;
      _customStart = picked.start;
      _customEnd = picked.end;
      _visibleMonth = DateTime(picked.start.year, picked.start.month);
    });
  }

  String get _customRangeLabel {
    if (_customStart == null || _customEnd == null) return '未选择';
    String fmt(DateTime d) =>
        '${d.year}.${d.month.toString().padLeft(2, '0')}.${d.day.toString().padLeft(2, '0')}';
    return '${fmt(_customStart!)} - ${fmt(_customEnd!)}';
  }

  @override
  Widget build(BuildContext context) {
    final days = _calendarDays(_visibleMonth);
    final range = _selectedRange();
    return SafeArea(
      top: false,
      child: Container(
        height: MediaQuery.sizeOf(context).height * 0.82,
        padding: const EdgeInsets.fromLTRB(20, 10, 20, 20),
        constraints: BoxConstraints(
          maxHeight: MediaQuery.sizeOf(context).height * 0.9,
        ),
        decoration: const BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
          boxShadow: [
            BoxShadow(
              color: Color(0x1A111827),
              blurRadius: 24,
              offset: Offset(0, -8),
            ),
          ],
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Expanded(
              child: SingleChildScrollView(
                child: Column(
                  children: [
                    Container(
                      width: 44,
                      height: 5,
                      decoration: BoxDecoration(
                        color: const Color(0xFFD0D5DD),
                        borderRadius: BorderRadius.circular(999),
                      ),
                    ),
                    const SizedBox(height: 16),
                    Row(
                      children: [
                        const Expanded(
                          child: Text('日期筛选', style: AppTextStyles.title),
                        ),
                        IconButton(
                          onPressed: () => Navigator.of(context).pop(),
                          icon: const Icon(LucideIcons.x),
                          color: AppColors.muted,
                        ),
                      ],
                    ),
                    const SizedBox(height: 10),
                    _PresetGrid(
                      selected: _selected,
                      customRangeLabel:
                          _selected == DateRangePreset.custom ? _customRangeLabel : null,
                      onChanged: (preset) {
                        if (preset == DateRangePreset.custom) {
                          _pickCustomRange();
                          return;
                        }
                        setState(() {
                          _selected = preset;
                          _visibleMonth = _monthForPreset(preset);
                        });
                      },
                    ),
                    if (_selected == DateRangePreset.custom) ...[
                      const SizedBox(height: 12),
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 14,
                          vertical: 10,
                        ),
                        decoration: BoxDecoration(
                          color: AppColors.blueSoft,
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Row(
                          children: [
                            const Icon(
                              LucideIcons.calendarRange,
                              size: 16,
                              color: AppColors.blue,
                            ),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                _customRangeLabel,
                                style: AppTextStyles.body.copyWith(
                                  color: AppColors.blue,
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                            ),
                            GestureDetector(
                              onTap: _pickCustomRange,
                              child: Text(
                                '修改',
                                style: AppTextStyles.small.copyWith(
                                  color: AppColors.blue,
                                  fontWeight: FontWeight.w800,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                    const SizedBox(height: 20),
                    Row(
                      children: [
                        IconButton(
                          key: const Key('date-filter-prev-month'),
                          onPressed: () => setState(() {
                            _selected = DateRangePreset.currentMonth;
                            _visibleMonth = DateTime(
                              _visibleMonth.year,
                              _visibleMonth.month - 1,
                            );
                          }),
                          icon: const Icon(LucideIcons.chevronLeft),
                          color: AppColors.ink,
                        ),
                        Expanded(
                          child: Text(
                            '${_visibleMonth.year}年${_visibleMonth.month}月',
                            textAlign: TextAlign.center,
                            style: AppTextStyles.dateTitle,
                          ),
                        ),
                        IconButton(
                          key: const Key('date-filter-next-month'),
                          onPressed: () => setState(() {
                            _selected = DateRangePreset.currentMonth;
                            _visibleMonth = DateTime(
                              _visibleMonth.year,
                              _visibleMonth.month + 1,
                            );
                          }),
                          icon: const Icon(LucideIcons.chevronRight),
                          color: AppColors.ink,
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    const _WeekdayRow(),
                    const SizedBox(height: 6),
                    GridView.builder(
                      shrinkWrap: true,
                      physics: const NeverScrollableScrollPhysics(),
                      itemCount: days.length,
                      gridDelegate:
                          const SliverGridDelegateWithFixedCrossAxisCount(
                        crossAxisCount: 7,
                        mainAxisSpacing: 6,
                        crossAxisSpacing: 4,
                      ),
                      itemBuilder: (context, index) {
                        final day = days[index];
                        return _CalendarDayCell(day: day, range: range);
                      },
                    ),
                    const SizedBox(height: 16),
                  ],
                ),
              ),
            ),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: () => setState(() {
                      _selected = DateRangePreset.currentMonth;
                      _visibleMonth = _monthForPreset(_selected);
                    }),
                    style: OutlinedButton.styleFrom(
                      minimumSize: const Size.fromHeight(52),
                      side: const BorderSide(color: Color(0xFF8DB5FF)),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(16),
                      ),
                    ),
                    child: Text(
                      '重置',
                      style: AppTextStyles.sectionTitle.copyWith(
                        color: AppColors.blue,
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  flex: 2,
                  child: DecoratedBox(
                    decoration: BoxDecoration(
                      gradient: const LinearGradient(
                        colors: [Color(0xFF1473FF), Color(0xFF2F73F6)],
                      ),
                      borderRadius: BorderRadius.circular(16),
                      boxShadow: const [
                        BoxShadow(
                          color: Color(0x261473FF),
                          blurRadius: 16,
                          offset: Offset(0, 8),
                        ),
                      ],
                    ),
                    child: TextButton(
                      key: const Key('date-filter-confirm'),
                      onPressed: () => Navigator.of(context).pop(
                        DateFilterSelection(
                          preset: _selected,
                          visibleMonth: _visibleMonth,
                          customStart: _customStart,
                          customEnd: _customEnd,
                        ),
                      ),
                      style: TextButton.styleFrom(
                        minimumSize: const Size.fromHeight(52),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(16),
                        ),
                      ),
                      child: Text(
                        '确认',
                        style: AppTextStyles.sectionTitle.copyWith(
                          color: Colors.white,
                          fontSize: 18,
                        ),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  DateTime _monthForPreset(DateRangePreset preset) {
    final base = DateTime(widget.visibleMonth.year, widget.visibleMonth.month);
    if (preset == DateRangePreset.previousMonth) {
      return DateTime(base.year, base.month - 1);
    }
    return base;
  }

  _DateRange _selectedRange() {
    final base = DateTime(_visibleMonth.year, _visibleMonth.month);
    return switch (_selected) {
      DateRangePreset.currentMonth => _DateRange(
          DateTime(base.year, base.month, 1),
          DateTime(base.year, base.month + 1, 0),
        ),
      DateRangePreset.previousMonth => _DateRange(
          DateTime(base.year, base.month - 1, 1),
          DateTime(base.year, base.month, 0),
        ),
      DateRangePreset.last7Days => _DateRange(
          DateTime(base.year, base.month, 9).subtract(const Duration(days: 6)),
          DateTime(base.year, base.month, 9),
        ),
      DateRangePreset.last30Days => _DateRange(
          DateTime(base.year, base.month, 9).subtract(const Duration(days: 29)),
          DateTime(base.year, base.month, 9),
        ),
      DateRangePreset.currentYear => _DateRange(
          DateTime(base.year),
          DateTime(base.year, 12, 31),
        ),
      DateRangePreset.allTime => const _DateRange(null, null),
      DateRangePreset.custom => _DateRange(_customStart, _customEnd),
    };
  }
}

class _PresetGrid extends StatelessWidget {
  const _PresetGrid({
    required this.selected,
    required this.onChanged,
    this.customRangeLabel,
  });

  final DateRangePreset selected;
  final ValueChanged<DateRangePreset> onChanged;
  final String? customRangeLabel;

  @override
  Widget build(BuildContext context) {
    const presets = DateRangePreset.values;
    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      itemCount: presets.length,
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 3,
        mainAxisSpacing: 10,
        crossAxisSpacing: 10,
        childAspectRatio: 2.7,
      ),
      itemBuilder: (context, index) {
        final preset = presets[index];
        final active = selected == preset;
        return OutlinedButton(
          onPressed: () => onChanged(preset),
          style: OutlinedButton.styleFrom(
            backgroundColor: active ? AppColors.blueSoft : AppColors.surface,
            side: BorderSide(
              color: active ? const Color(0xFF8DB5FF) : AppColors.line,
            ),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(14),
            ),
          ),
          child: Text(
            preset.label,
            style: AppTextStyles.body.copyWith(
              color: active ? AppColors.blue : AppColors.ink,
              fontWeight: FontWeight.w800,
            ),
          ),
        );
      },
    );
  }
}

class _WeekdayRow extends StatelessWidget {
  const _WeekdayRow();

  @override
  Widget build(BuildContext context) {
    return Row(
      children: ['一', '二', '三', '四', '五', '六', '日'].map((weekday) {
        return Expanded(
          child: Center(
            child: Text(
              weekday,
              style: AppTextStyles.small.copyWith(color: AppColors.subtle),
            ),
          ),
        );
      }).toList(),
    );
  }
}

class _CalendarDayCell extends StatelessWidget {
  const _CalendarDayCell({required this.day, required this.range});

  final DateTime? day;
  final _DateRange range;

  @override
  Widget build(BuildContext context) {
    final cellDay = day;
    if (cellDay == null) return const SizedBox.shrink();
    final inRange = range.contains(cellDay);
    final isEnd = range.end != null && _sameDate(cellDay, range.end!);
    return Container(
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: isEnd
            ? AppColors.blue
            : inRange
                ? AppColors.blueSoft
                : Colors.transparent,
        shape: isEnd ? BoxShape.circle : BoxShape.rectangle,
        borderRadius: isEnd ? null : BorderRadius.circular(999),
      ),
      child: Text(
        '${cellDay.day}',
        style: AppTextStyles.body.copyWith(
          color: isEnd ? Colors.white : AppColors.ink,
          fontWeight: isEnd || inRange ? FontWeight.w800 : FontWeight.w500,
        ),
      ),
    );
  }
}

class _DateRange {
  const _DateRange(this.start, this.end);

  final DateTime? start;
  final DateTime? end;

  bool contains(DateTime date) {
    if (start == null || end == null) return false;
    final day = DateTime(date.year, date.month, date.day);
    return !day.isBefore(start!) && !day.isAfter(end!);
  }
}

List<DateTime?> _calendarDays(DateTime month) {
  final first = DateTime(month.year, month.month);
  final total = DateTime(month.year, month.month + 1, 0).day;
  final leading = first.weekday - 1;
  return [
    for (var i = 0; i < leading; i++) null,
    for (var day = 1; day <= total; day++)
      DateTime(month.year, month.month, day),
  ];
}

bool _sameDate(DateTime a, DateTime b) {
  return a.year == b.year && a.month == b.month && a.day == b.day;
}
