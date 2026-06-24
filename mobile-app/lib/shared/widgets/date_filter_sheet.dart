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

  void _selectDay(DateTime day) {
    setState(() {
      if (_customStart == null ||
          (_customStart != null && _customEnd != null)) {
        _customStart = day;
        _customEnd = null;
        _selected = DateRangePreset.custom;
        return;
      }
      if (day.isBefore(_customStart!)) {
        _customEnd = _customStart;
        _customStart = day;
      } else {
        _customEnd = day;
      }
      _selected = DateRangePreset.custom;
    });
  }

  String _chipText(DateTime? date) {
    if (date == null) return '--';
    return '${date.month.toString().padLeft(2, '0')}.${date.day.toString().padLeft(2, '0')}';
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
                      onChanged: (preset) {
                        setState(() {
                          _selected = preset;
                          _visibleMonth = _monthForPreset(preset);
                          if (preset != DateRangePreset.custom) {
                            _customStart = null;
                            _customEnd = null;
                          }
                        });
                      },
                    ),
                    if (_selected == DateRangePreset.custom) ...[
                      const SizedBox(height: 14),
                      Row(
                        children: [
                          Expanded(
                            child: _CustomRangeChip(
                              label: '开始',
                              dateText: _chipText(_customStart),
                              filled: _customStart != null,
                            ),
                          ),
                          Padding(
                            padding: const EdgeInsets.symmetric(horizontal: 10),
                            child: Icon(
                              LucideIcons.arrowRight,
                              size: 16,
                              color: _customStart != null && _customEnd != null
                                  ? AppColors.blue
                                  : AppColors.subtle,
                            ),
                          ),
                          Expanded(
                            child: _CustomRangeChip(
                              label: '结束',
                              dateText: _chipText(_customEnd),
                              filled: _customEnd != null,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 6),
                      Text(
                        _customStart == null
                            ? '点击日历选择开始日期'
                            : _customEnd == null
                                ? '再点击一次选择结束日期'
                                : '已选定范围，可继续点击修改',
                        textAlign: TextAlign.center,
                        style: AppTextStyles.small.copyWith(
                          color: AppColors.muted,
                          fontSize: 11.5,
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
                        return _CalendarDayCell(
                          day: day,
                          range: range,
                          customStart: _customStart,
                          customEnd: _customEnd,
                          isCustomMode:
                              _selected == DateRangePreset.custom,
                          onTap: day == null
                              ? null
                              : () {
                                  setState(() {
                                    _visibleMonth = DateTime(
                                      day.year,
                                      day.month,
                                    );
                                  });
                                  _selectDay(day);
                                },
                        );
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
                      minimumSize: const Size.fromHeight(50),
                      backgroundColor: AppColors.surface,
                      side: const BorderSide(color: AppColors.line),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(14),
                      ),
                    ),
                    child: const Text(
                      '重置',
                      style: TextStyle(
                        color: AppColors.ink,
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  flex: 2,
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
                      minimumSize: const Size.fromHeight(50),
                      backgroundColor: AppColors.ink,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(14),
                      ),
                    ),
                    child: const Text(
                      '应用筛选',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 15,
                        fontWeight: FontWeight.w800,
                        letterSpacing: 0.1,
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

class _CustomRangeChip extends StatelessWidget {
  const _CustomRangeChip({
    required this.label,
    required this.dateText,
    required this.filled,
  });

  final String label;
  final String dateText;
  final bool filled;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 50,
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: filled ? AppColors.surface2 : AppColors.surface,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(
          color: filled ? AppColors.ink : AppColors.line,
        ),
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(
            label,
            style: const TextStyle(
              color: AppColors.muted,
              fontSize: 10,
              fontWeight: FontWeight.w600,
              letterSpacing: 0.4,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            dateText,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
              color: filled ? AppColors.ink : AppColors.subtle,
              fontSize: 14,
              fontWeight: FontWeight.w800,
              fontFeatures: const [FontFeature.tabularFigures()],
              letterSpacing: -0.2,
            ),
          ),
        ],
      ),
    );
  }
}

class _PresetGrid extends StatelessWidget {
  const _PresetGrid({
    required this.selected,
    required this.onChanged,
  });

  final DateRangePreset selected;
  final ValueChanged<DateRangePreset> onChanged;

  @override
  Widget build(BuildContext context) {
    const presets = DateRangePreset.values;
    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      itemCount: presets.length,
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 3,
        mainAxisSpacing: 8,
        crossAxisSpacing: 8,
        childAspectRatio: 2.8,
      ),
      itemBuilder: (context, index) {
        final preset = presets[index];
        final active = selected == preset;
        return GestureDetector(
          onTap: () => onChanged(preset),
          behavior: HitTestBehavior.opaque,
          child: Container(
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: active ? AppColors.ink : AppColors.surface,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(
                color: active ? AppColors.ink : AppColors.line,
              ),
            ),
            child: Text(
              preset.label,
              style: TextStyle(
                color: active ? Colors.white : AppColors.ink,
                fontSize: 13,
                fontWeight: FontWeight.w700,
                letterSpacing: 0.1,
              ),
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
  const _CalendarDayCell({
    required this.day,
    required this.range,
    required this.customStart,
    required this.customEnd,
    required this.isCustomMode,
    this.onTap,
  });

  final DateTime? day;
  final _DateRange range;
  final DateTime? customStart;
  final DateTime? customEnd;
  final bool isCustomMode;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final cellDay = day;
    if (cellDay == null) return const SizedBox.shrink();

    final bool isStart;
    final bool isEnd;
    final bool inMiddle;
    if (isCustomMode) {
      isStart = customStart != null && _sameDate(cellDay, customStart!);
      isEnd = customEnd != null && _sameDate(cellDay, customEnd!);
      inMiddle = customStart != null &&
          customEnd != null &&
          cellDay.isAfter(customStart!) &&
          cellDay.isBefore(customEnd!);
    } else {
      isStart = range.start != null && _sameDate(cellDay, range.start!);
      isEnd = range.end != null && _sameDate(cellDay, range.end!);
      inMiddle = range.contains(cellDay) && !isStart && !isEnd;
    }

    final isEndpoint = isStart || isEnd;

    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: Container(
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: isEndpoint
              ? AppColors.blue
              : inMiddle
                  ? AppColors.blueSoft
                  : Colors.transparent,
          shape: isEndpoint ? BoxShape.circle : BoxShape.rectangle,
          borderRadius: isEndpoint ? null : BorderRadius.circular(999),
        ),
        child: Text(
          '${cellDay.day}',
          style: AppTextStyles.body.copyWith(
            color: isEndpoint ? Colors.white : AppColors.ink,
            fontWeight:
                (isEndpoint || inMiddle) ? FontWeight.w800 : FontWeight.w500,
          ),
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
