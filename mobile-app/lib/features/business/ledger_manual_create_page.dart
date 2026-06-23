import 'package:flutter/material.dart';
import 'package:dropdown_search/dropdown_search.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../data/api/api_models.dart';
import '../../data/repositories/business_repository.dart';
import '../../shared/widgets/animated_press.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';
import 'business_ui.dart';
import 'ledger_category_management_page.dart';

class LedgerManualCreatePage extends StatefulWidget {
  const LedgerManualCreatePage({
    super.key,
    required this.repository,
    this.onBottomTabChanged,
    this.onSaved,
  });

  static const routePath = '/ledger-manual-create';

  final BusinessRepository repository;
  final ValueChanged<int>? onBottomTabChanged;
  final VoidCallback? onSaved;

  @override
  State<LedgerManualCreatePage> createState() => _LedgerManualCreatePageState();
}

class _LedgerManualCreatePageState extends State<LedgerManualCreatePage> {
  final _category = TextEditingController();
  final _amount = TextEditingController();
  final _note = TextEditingController();
  DateTime _recordDateTime = DateTime.now();
  String _recordType = 'cost';
  bool _customCategory = false;
  int _categoryReloadKey = 0;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _amount.addListener(() {
      if (mounted) setState(() {});
    });
  }

  @override
  void dispose() {
    _category.dispose();
    _amount.dispose();
    _note.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (_saving) return;
    setState(() => _saving = true);
    final amountText = _amount.text.replaceAll(RegExp(r'[^0-9.]'), '');
    final amountValue = num.tryParse(amountText) ?? amountText;
    try {
      await widget.repository.createLedgerRecord({
        'record_type': _recordType,
        'category': _categoryTextForSave(),
        'amount': amountValue,
        'settled_amount': amountValue,
        'settlement_status': 'settled',
        'record_date': _recordDateText,
        'recorded_at': _recordedAtPayload,
        'note': _note.text.trim(),
      }..removeWhere((_, value) => value == null || value == ''));
      _clearFormAfterSave();
      widget.onSaved?.call();
      _showMessage('保存记录成功');
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

  void _clearFormAfterSave() {
    if (!mounted) return;
    setState(() {
      _category.clear();
      _amount.clear();
      _note.clear();
      _recordDateTime = DateTime.now();
      _customCategory = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    return BusinessPageFrame(
      title: '记账',
      trailingIcon: LucideIcons.history,
      bottomBar: BottomActions(
        secondaryLabel: '取消',
        primaryLabel: _saving ? '保存中' : '保存记录',
        primaryEnabled: !_saving,
        primaryLoading: _saving,
        onPrimary: _save,
        onSecondary: () => Navigator.of(context).maybePop(),
        showTabs: true,
        onBottomTabChanged: widget.onBottomTabChanged,
      ),
      children: [
        _AmountHero(
          recordType: _recordType,
          amount: _amount.text.trim(),
          onTypeChanged: (value) => setState(() {
            _recordType = value;
            _category.clear();
            _customCategory = false;
          }),
        ),
        _RecordFormCard(
          children: [
            _LedgerCategoryPickerFormRow(
              repository: widget.repository,
              recordType: _recordType,
              selectedCategory: _category.text.trim(),
              customSelected: _customCategory,
              reloadKey: _categoryReloadKey,
              onManageTap: _openCategoryManagement,
              onSelected: (value) => setState(() {
                _customCategory = value.isCustom;
                _category.text = value.name;
              }),
            ),
            if (_customCategory)
              _CompactFormRow(
                label: '自定义',
                child: TextField(
                  controller: _category,
                  textAlign: TextAlign.right,
                  style: const TextStyle(
                    color: AppColors.ink,
                    fontSize: 16,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 0,
                  ),
                  decoration: InputDecoration(
                    hintText: '输入分类名称',
                    hintStyle: AppTextStyles.body.copyWith(
                      color: AppColors.subtle,
                      fontWeight: FontWeight.w500,
                    ),
                    border: InputBorder.none,
                    isDense: true,
                    contentPadding: EdgeInsets.zero,
                  ),
                ),
              ),
            _CompactFormRow(
              label: '金额',
              prefix: Padding(
                padding: const EdgeInsets.only(right: 4),
                child: Text(
                  '￥',
                  style: TextStyle(
                    color: _amount.text.isEmpty
                        ? AppColors.subtle
                        : AppColors.ink,
                    fontSize: 18,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
              child: TextField(
                controller: _amount,
                keyboardType:
                    const TextInputType.numberWithOptions(decimal: true),
                textAlign: TextAlign.right,
                style: TextStyle(
                  color: _amount.text.isEmpty
                      ? AppColors.subtle
                      : AppColors.ink,
                  fontSize: 22,
                  fontWeight: FontWeight.w800,
                  letterSpacing: 0,
                ),
                decoration: InputDecoration(
                  hintText: '0.00',
                  hintStyle: TextStyle(
                    color: AppColors.subtle,
                    fontSize: 22,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 0,
                  ),
                  border: InputBorder.none,
                  isDense: true,
                  contentPadding: EdgeInsets.zero,
                ),
              ),
            ),
            _LedgerDateTimeFormRow(
              dateText: _recordDateText,
              timeText: _recordTimeText,
              onTap: _pickDateTime,
            ),
            _CompactFormRow(
              label: '备注',
              child: TextField(
                controller: _note,
                textAlign: TextAlign.right,
                style: const TextStyle(
                  color: AppColors.ink,
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                  letterSpacing: 0,
                ),
                decoration: InputDecoration(
                  hintText: '补充说明（可选）',
                  hintStyle: AppTextStyles.body.copyWith(
                    color: AppColors.subtle,
                    fontWeight: FontWeight.w500,
                  ),
                  border: InputBorder.none,
                  isDense: true,
                  contentPadding: EdgeInsets.zero,
                ),
              ),
            ),
          ],
        ),
        _AssistEntryCard(
          onTap: () => Navigator.of(context).maybePop(),
        ),
      ],
    );
  }

  Future<void> _openCategoryManagement() async {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => LedgerCategoryManagementPage(
          repository: widget.repository,
          initialRecordType: _recordType,
        ),
      ),
    );
    if (!mounted) return;
    setState(() {
      _category.clear();
      _customCategory = false;
      _categoryReloadKey += 1;
    });
  }

  String _categoryTextForSave() {
    final text = _category.text.trim();
    if (text.isNotEmpty && text != '自定义') return text;
    return '其他';
  }

  String get _recordDateText => _dateText(_recordDateTime);

  String get _recordTimeText =>
      _timeText(TimeOfDay.fromDateTime(_recordDateTime));

  String get _recordedAtPayload {
    final value = DateTime(
      _recordDateTime.year,
      _recordDateTime.month,
      _recordDateTime.day,
      _recordDateTime.hour,
      _recordDateTime.minute,
    );
    return value.toIso8601String();
  }

  Future<void> _pickDateTime() async {
    final pickedDate = await showDatePicker(
      context: context,
      initialDate: _recordDateTime,
      firstDate: DateTime(2020),
      lastDate: DateTime.now().add(const Duration(days: 1)),
      helpText: '选择记账日期',
      cancelText: '取消',
      confirmText: '下一步',
    );
    if (pickedDate == null || !mounted) return;

    final pickedTime = await showTimePicker(
      context: context,
      initialTime: TimeOfDay.fromDateTime(_recordDateTime),
      helpText: '选择记账时间',
      cancelText: '取消',
      confirmText: '确定',
    );
    if (pickedTime == null) return;

    setState(() {
      _recordDateTime = DateTime(
        pickedDate.year,
        pickedDate.month,
        pickedDate.day,
        pickedTime.hour,
        pickedTime.minute,
      );
    });
  }
}

String _dateText(DateTime value) {
  final month = value.month.toString().padLeft(2, '0');
  final day = value.day.toString().padLeft(2, '0');
  return '${value.year}-$month-$day';
}

String _timeText(TimeOfDay time) {
  final hour = time.hour.toString().padLeft(2, '0');
  final minute = time.minute.toString().padLeft(2, '0');
  return '$hour:$minute';
}

class _AmountHero extends StatelessWidget {
  const _AmountHero({
    required this.recordType,
    required this.amount,
    required this.onTypeChanged,
  });

  final String recordType;
  final String amount;
  final ValueChanged<String> onTypeChanged;

  @override
  Widget build(BuildContext context) {
    final isIncome = recordType == 'income';
    final accent = isIncome ? AppColors.green : AppColors.blue;
    final accentSoft = isIncome ? AppColors.greenSoft : AppColors.blueSoft;
    final amountDisplay = amount.isEmpty ? '0.00' : amount;

    return AnimatedContainer(
      duration: const Duration(milliseconds: 320),
      curve: Curves.easeOutCubic,
      padding: const EdgeInsets.fromLTRB(20, 22, 20, 22),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: AppColors.lineSoft),
        boxShadow: const [
          BoxShadow(
            color: Color(0x06000000),
            blurRadius: 16,
            offset: Offset(0, 6),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _RecordTypeSegmented(
            value: recordType,
            onChanged: onTypeChanged,
          ),
          const SizedBox(height: 20),
          AnimatedSwitcher(
            duration: const Duration(milliseconds: 240),
            transitionBuilder: (child, anim) => FadeTransition(
              opacity: anim,
              child: SlideTransition(
                position: Tween<Offset>(
                  begin: const Offset(0, 0.06),
                  end: Offset.zero,
                ).animate(anim),
                child: child,
              ),
            ),
            child: amount.isEmpty
                ? Text(
                    '今天随手记一笔',
                    key: const ValueKey('hero-hint'),
                    style: TextStyle(
                      color: AppColors.muted,
                      fontSize: 15,
                      height: 22 / 15,
                      fontWeight: FontWeight.w600,
                      letterSpacing: 0,
                    ),
                  )
                : Row(
                    key: ValueKey('hero-amount-$amountDisplay'),
                    crossAxisAlignment: CrossAxisAlignment.baseline,
                    textBaseline: TextBaseline.alphabetic,
                    children: [
                      Text(
                        '￥',
                        style: TextStyle(
                          color: accent,
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
                          child: Text(
                            amountDisplay,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(
                              color: AppColors.ink,
                              fontSize: 40,
                              fontWeight: FontWeight.w900,
                              height: 1.05,
                              letterSpacing: -0.5,
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              AnimatedContainer(
                duration: const Duration(milliseconds: 320),
                curve: Curves.easeOutCubic,
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
                      isIncome
                          ? LucideIcons.arrowDownLeft
                          : LucideIcons.arrowUpRight,
                      size: 13,
                      color: accent,
                    ),
                    const SizedBox(width: 4),
                    Text(
                      isIncome ? '收入' : '支出',
                      style: TextStyle(
                        color: accent,
                        fontSize: 12,
                        fontWeight: FontWeight.w800,
                        letterSpacing: 0.2,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              Text(
                '金额将记录到农场账本',
                style: TextStyle(
                  color: AppColors.subtle,
                  fontSize: 12,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _RecordTypeSegmented extends StatelessWidget {
  const _RecordTypeSegmented({required this.value, required this.onChanged});

  final String value;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: AppColors.surface2,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.line),
      ),
      child: Row(
        children: [
          _SegmentedItem(
            label: '支出',
            icon: LucideIcons.arrowUpRight,
            selected: value == 'cost',
            accent: AppColors.blue,
            onTap: () => onChanged('cost'),
          ),
          _SegmentedItem(
            label: '收入',
            icon: LucideIcons.arrowDownLeft,
            selected: value == 'income',
            accent: AppColors.green,
            onTap: () => onChanged('income'),
          ),
        ],
      ),
    );
  }
}

class _SegmentedItem extends StatelessWidget {
  const _SegmentedItem({
    required this.label,
    required this.icon,
    required this.selected,
    required this.accent,
    required this.onTap,
  });

  final String label;
  final IconData icon;
  final bool selected;
  final Color accent;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: AnimatedPress(
        scale: 0.96,
        onTap: onTap,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 220),
          curve: Curves.easeOutCubic,
          height: 40,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: selected ? accent : Colors.transparent,
            borderRadius: BorderRadius.circular(11),
            boxShadow: selected
                ? [
                    BoxShadow(
                      color: accent.withValues(alpha: 0.28),
                      blurRadius: 10,
                      offset: const Offset(0, 4),
                    ),
                  ]
                : null,
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                icon,
                size: 14,
                color: selected ? Colors.white : AppColors.muted,
              ),
              const SizedBox(width: 6),
              AnimatedDefaultTextStyle(
                duration: const Duration(milliseconds: 220),
                curve: Curves.easeOutCubic,
                style: TextStyle(
                  color: selected ? Colors.white : AppColors.muted,
                  fontSize: 14,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 0.1,
                  fontFamily: null,
                ),
                child: Text(label),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _RecordFormCard extends StatelessWidget {
  const _RecordFormCard({required this.children});

  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: AppColors.lineSoft),
        boxShadow: const [
          BoxShadow(
            color: Color(0x06000000),
            blurRadius: 16,
            offset: Offset(0, 6),
          ),
        ],
      ),
      child: Column(
        children: [
          for (var i = 0; i < children.length; i++) ...[
            children[i],
            if (i != children.length - 1)
              const Padding(
                padding: EdgeInsets.only(left: 20),
                child: Divider(
                  height: 1,
                  thickness: 1,
                  color: AppColors.lineSoft,
                ),
              ),
          ],
        ],
      ),
    );
  }
}

class _CompactFormRow extends StatelessWidget {
  const _CompactFormRow({required this.label, required this.child, this.prefix});

  final String label;
  final Widget child;
  final Widget? prefix;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Text(
            label,
            style: const TextStyle(
              color: AppColors.muted,
              fontSize: 15,
              height: 22 / 15,
              fontWeight: FontWeight.w600,
              letterSpacing: 0,
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Row(
              mainAxisAlignment: MainAxisAlignment.end,
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                if (prefix != null) prefix!,
                Expanded(child: child),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _LedgerDateTimeFormRow extends StatelessWidget {
  const _LedgerDateTimeFormRow({
    required this.dateText,
    required this.timeText,
    required this.onTap,
  });

  final String dateText;
  final String timeText;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return AnimatedPress(
      scale: 0.99,
      onTap: onTap,
      borderRadius: BorderRadius.zero,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
        child: Row(
          children: [
            const Text(
              '日期',
              style: TextStyle(
                color: AppColors.muted,
                fontSize: 15,
                height: 22 / 15,
                fontWeight: FontWeight.w600,
                letterSpacing: 0,
              ),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Row(
                mainAxisAlignment: MainAxisAlignment.end,
                crossAxisAlignment: CrossAxisAlignment.center,
                children: [
                  Text(
                    dateText,
                    style: const TextStyle(
                      color: AppColors.ink,
                      fontSize: 16,
                      height: 22 / 16,
                      fontWeight: FontWeight.w700,
                      letterSpacing: 0,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      color: AppColors.surface2,
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Text(
                      timeText,
                      style: const TextStyle(
                        color: AppColors.muted,
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                        letterSpacing: 0,
                      ),
                    ),
                  ),
                  const SizedBox(width: 6),
                  const Icon(
                    LucideIcons.chevronRight,
                    size: 18,
                    color: AppColors.subtle,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _LedgerOption {
  const _LedgerOption({
    required this.name,
    this.id,
    this.subtitle = '',
    this.icon = LucideIcons.tag,
    this.isCustom = false,
  });

  final String name;
  final int? id;
  final String subtitle;
  final IconData icon;
  final bool isCustom;
}

class _LedgerCategoryPickerFormRow extends StatefulWidget {
  const _LedgerCategoryPickerFormRow({
    required this.repository,
    required this.recordType,
    required this.selectedCategory,
    required this.customSelected,
    required this.reloadKey,
    required this.onManageTap,
    required this.onSelected,
  });

  final BusinessRepository repository;
  final String recordType;
  final String selectedCategory;
  final bool customSelected;
  final int reloadKey;
  final VoidCallback onManageTap;
  final ValueChanged<_LedgerOption> onSelected;

  @override
  State<_LedgerCategoryPickerFormRow> createState() =>
      _LedgerCategoryPickerFormRowState();
}

class _LedgerCategoryPickerFormRowState
    extends State<_LedgerCategoryPickerFormRow> {
  late Future<PageResult<ApiRecord>> _categoriesFuture;
  List<_LedgerOption> _lastOptions = const [];

  @override
  void initState() {
    super.initState();
    _categoriesFuture = widget.repository.listCostCategories();
  }

  @override
  void didUpdateWidget(covariant _LedgerCategoryPickerFormRow oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.reloadKey != widget.reloadKey ||
        oldWidget.recordType != widget.recordType) {
      _lastOptions = const [];
      _categoriesFuture = widget.repository.listCostCategories();
    }
  }

  Future<List<_LedgerOption>> _loadOptions(String filter) async {
    final response = await _categoriesFuture.catchError(
      (_) => const PageResult<ApiRecord>(items: [], total: 0),
    );
    final options = _categoryOptions(response.items, widget.recordType);
    _lastOptions = options;
    final keyword = filter.trim();
    if (keyword.isEmpty) return options;
    return options
        .where((option) =>
            option.name.contains(keyword) || option.subtitle.contains(keyword))
        .toList();
  }

  @override
  Widget build(BuildContext context) {
    final selected = _selectedOption();
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          const Text(
            '分类',
            style: TextStyle(
              color: AppColors.muted,
              fontSize: 15,
              height: 22 / 15,
              fontWeight: FontWeight.w600,
              letterSpacing: 0,
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: SizedBox(
              height: 30,
              child: DropdownSearch<_LedgerOption>(
                key: const Key('ledger-category-dropdown-search'),
                selectedItem: selected,
                compareFn: (a, b) =>
                    a.name == b.name && a.isCustom == b.isCustom,
                itemAsString: (item) => item.name,
                items: (filter, _) => _loadOptions(filter),
                onSelected: (value) {
                  if (value != null) widget.onSelected(value);
                },
                dropdownBuilder: (context, item) => _CategorySelectedView(
                  option: item,
                  placeholder: widget.recordType == 'income'
                      ? '选择收入分类'
                      : '选择支出分类',
                ),
                decoratorProps: const DropDownDecoratorProps(
                  decoration: InputDecoration(
                    border: InputBorder.none,
                    contentPadding: EdgeInsets.zero,
                    isDense: true,
                  ),
                ),
                suffixProps: const DropdownSuffixProps(
                  dropdownButtonProps: DropdownButtonProps(
                    iconClosed: Icon(
                      LucideIcons.chevronDown,
                      color: AppColors.subtle,
                      size: 18,
                    ),
                    iconOpened: Icon(
                      LucideIcons.chevronUp,
                      color: AppColors.ink,
                      size: 18,
                    ),
                  ),
                ),
                popupProps: PopupProps.modalBottomSheet(
                  showSearchBox: true,
                  constraints: const BoxConstraints(maxHeight: 520),
                  modalBottomSheetProps: const ModalBottomSheetProps(
                    backgroundColor: Colors.transparent,
                    isScrollControlled: true,
                  ),
                  searchFieldProps: TextFieldProps(
                    decoration: InputDecoration(
                      hintText: '搜索分类',
                      prefixIcon: const Icon(LucideIcons.search, size: 19),
                      filled: true,
                      fillColor: AppColors.surface2,
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(14),
                        borderSide: BorderSide.none,
                      ),
                      contentPadding: const EdgeInsets.symmetric(
                        horizontal: 12,
                        vertical: 12,
                      ),
                    ),
                  ),
                  containerBuilder: (context, child) => SafeArea(
                    top: false,
                    child: Container(
                      margin: const EdgeInsets.fromLTRB(12, 0, 12, 12),
                      padding: const EdgeInsets.fromLTRB(20, 12, 20, 20),
                      decoration: const BoxDecoration(
                        color: Colors.white,
                        borderRadius:
                            BorderRadius.vertical(top: Radius.circular(28)),
                        boxShadow: [
                          BoxShadow(
                            color: Color(0x14000000),
                            blurRadius: 30,
                            offset: Offset(0, -10),
                          ),
                        ],
                      ),
                      child: Column(
                        children: [
                          const _SheetGrabber(),
                          const SizedBox(height: 14),
                          _SheetTitle(
                            title: '选择分类',
                            subtitle: widget.recordType == 'income'
                                ? '选择收入来源，也可以输入关键字搜索'
                                : '选择支出用途，也可以输入关键字搜索',
                            onManageTap: widget.onManageTap,
                          ),
                          const SizedBox(height: 12),
                          Expanded(child: child),
                        ],
                      ),
                    ),
                  ),
                  itemBuilder: (context, item, _, isSelected) =>
                      _DropdownSearchCategoryTile(
                    option: item,
                    selected: isSelected,
                  ),
                  emptyBuilder: (context, _) => const _DropdownEmptyState(),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  _LedgerOption? _selectedOption() {
    final selectedName = widget.selectedCategory.trim();
    if (selectedName.isEmpty) return null;
    for (final option in _lastOptions) {
      if (option.name == selectedName &&
          option.isCustom == widget.customSelected) {
        return option;
      }
    }
    return _LedgerOption(
      name: selectedName,
      subtitle: widget.customSelected ? '自定义分类' : '',
      icon: widget.customSelected ? LucideIcons.pencilLine : LucideIcons.tag,
      isCustom: widget.customSelected,
    );
  }
}

class _CategorySelectedView extends StatelessWidget {
  const _CategorySelectedView({
    required this.option,
    required this.placeholder,
  });

  final _LedgerOption? option;
  final String placeholder;

  @override
  Widget build(BuildContext context) {
    final selected = option;
    if (selected == null) {
      return Align(
        alignment: Alignment.centerRight,
        child: Text(
          placeholder,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: AppTextStyles.body.copyWith(
            color: AppColors.subtle,
            fontSize: 15,
            fontWeight: FontWeight.w500,
          ),
        ),
      );
    }
    return Align(
      alignment: Alignment.centerRight,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(selected.icon, size: 15, color: AppColors.muted),
          const SizedBox(width: 6),
          Text(
            selected.name,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            textAlign: TextAlign.right,
            style: const TextStyle(
              color: AppColors.ink,
              fontSize: 15,
              fontWeight: FontWeight.w700,
              letterSpacing: 0,
            ),
          ),
        ],
      ),
    );
  }
}

class _DropdownSearchCategoryTile extends StatelessWidget {
  const _DropdownSearchCategoryTile({
    required this.option,
    required this.selected,
  });

  final _LedgerOption option;
  final bool selected;

  @override
  Widget build(BuildContext context) {
    return Container(
      key: Key('ledger-category-option-${option.name}'),
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: selected
            ? AppColors.blueSoft
            : AppColors.surface2,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(
          color: selected ? AppColors.blue : AppColors.line,
        ),
      ),
      child: Row(
        children: [
          Container(
            width: 38,
            height: 38,
            decoration: BoxDecoration(
              color: selected
                  ? AppColors.blue.withValues(alpha: 0.12)
                  : AppColors.surface,
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(
              option.icon,
              color: selected ? AppColors.blue : AppColors.muted,
              size: 18,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  option.name,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    color: AppColors.ink,
                    fontSize: 15,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 0,
                  ),
                ),
                if (option.subtitle.isNotEmpty) ...[
                  const SizedBox(height: 2),
                  Text(
                    option.subtitle,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      color: AppColors.muted,
                      fontSize: 12,
                      fontWeight: FontWeight.w500,
                      letterSpacing: 0,
                    ),
                  ),
                ],
              ],
            ),
          ),
          const SizedBox(width: 10),
          Icon(
            selected ? LucideIcons.check : LucideIcons.chevronRight,
            color: selected ? AppColors.blue : AppColors.subtle,
            size: selected ? 18 : 18,
          ),
        ],
      ),
    );
  }
}

class _DropdownEmptyState extends StatelessWidget {
  const _DropdownEmptyState();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 28),
        child: Text(
          '没有匹配分类',
          style: AppTextStyles.body.copyWith(
            color: AppColors.muted,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
    );
  }
}

class _SheetGrabber extends StatelessWidget {
  const _SheetGrabber();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Container(
        width: 36,
        height: 4,
        decoration: BoxDecoration(
          color: AppColors.line,
          borderRadius: BorderRadius.circular(999),
        ),
      ),
    );
  }
}

class _SheetTitle extends StatelessWidget {
  const _SheetTitle({
    required this.title,
    this.subtitle,
    this.onManageTap,
  });

  final String title;
  final String? subtitle;
  final VoidCallback? onManageTap;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: const TextStyle(
                  color: AppColors.ink,
                  fontSize: 20,
                  fontWeight: FontWeight.w800,
                  letterSpacing: 0,
                ),
              ),
              if (subtitle != null) ...[
                const SizedBox(height: 4),
                Text(
                  subtitle!,
                  style: const TextStyle(
                    color: AppColors.muted,
                    fontSize: 13,
                    fontWeight: FontWeight.w500,
                    letterSpacing: 0,
                  ),
                ),
              ],
            ],
          ),
        ),
        if (onManageTap != null) ...[
          const SizedBox(width: 8),
          AnimatedPress(
            scale: 0.96,
            onTap: onManageTap,
            child: Container(
              padding:
                  const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              decoration: BoxDecoration(
                color: AppColors.blueSoft,
                borderRadius: BorderRadius.circular(999),
              ),
              child: const Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(
                    LucideIcons.settings2,
                    size: 13,
                    color: AppColors.blue,
                  ),
                  SizedBox(width: 4),
                  Text(
                    '管理',
                    style: TextStyle(
                      color: AppColors.blue,
                      fontSize: 13,
                      fontWeight: FontWeight.w700,
                      letterSpacing: 0,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
        IconButton(
          visualDensity: VisualDensity.compact,
          onPressed: () => Navigator.of(context).pop(),
          icon: const Icon(LucideIcons.x, size: 18, color: AppColors.muted),
        ),
      ],
    );
  }
}

class _AssistEntryCard extends StatelessWidget {
  const _AssistEntryCard({required this.onTap});

  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return AnimatedPress(
      scale: 0.98,
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        decoration: BoxDecoration(
          color: AppColors.blueSoft,
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: AppColors.blue.withValues(alpha: 0.12)),
        ),
        child: Row(
          children: [
            Container(
              width: 32,
              height: 32,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(10),
              ),
              child: const Icon(
                LucideIcons.sparkles,
                color: AppColors.blue,
                size: 16,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    '一句话智能填写',
                    style: TextStyle(
                      color: AppColors.ink,
                      fontSize: 15,
                      fontWeight: FontWeight.w700,
                      letterSpacing: 0,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    '说"买了200块化肥"试试',
                    style: TextStyle(
                      color: AppColors.muted,
                      fontSize: 12,
                      fontWeight: FontWeight.w500,
                      letterSpacing: 0,
                    ),
                  ),
                ],
              ),
            ),
            const Icon(
              LucideIcons.chevronRight,
              color: AppColors.blue,
              size: 18,
            ),
          ],
        ),
      ),
    );
  }
}

List<_LedgerOption> _categoryOptions(
  List<ApiRecord> records,
  String recordType,
) {
  final apiOptions = records
      .where((record) => '${record.json['type']}' == recordType)
      .map(
        (record) => _LedgerOption(
          id: record.id,
          name: _ledgerFirstNonEmpty(
            [record.json['name']],
            fallback: '未命名分类',
          ),
          subtitle:
              (record.json['is_default'] as bool? ?? false) ? '系统预设' : '自定义分类',
          icon: _categoryIcon('${record.json['icon'] ?? ''}'),
        ),
      )
      .toList();
  final fallback = recordType == 'income'
      ? const [
          _LedgerOption(
              name: '销售', subtitle: '作物销售收入', icon: LucideIcons.shoppingCart),
          _LedgerOption(
              name: '补贴', subtitle: '农业补贴收入', icon: LucideIcons.handCoins),
          _LedgerOption(
              name: '其他', subtitle: '其他收入', icon: LucideIcons.moreHorizontal),
        ]
      : const [
          _LedgerOption(name: '种子', subtitle: '种苗和种子', icon: LucideIcons.leaf),
          _LedgerOption(
              name: '化肥', subtitle: '肥料和营养剂', icon: LucideIcons.flaskConical),
          _LedgerOption(
              name: '农药', subtitle: '植保投入', icon: LucideIcons.shieldAlert),
          _LedgerOption(name: '人工', subtitle: '工时和工资', icon: LucideIcons.users),
          _LedgerOption(
              name: '水电', subtitle: '水、电、灌溉', icon: LucideIcons.droplets),
          _LedgerOption(name: '地租', subtitle: '土地租金', icon: LucideIcons.house),
          _LedgerOption(
              name: '其他', subtitle: '其他支出', icon: LucideIcons.moreHorizontal),
        ];
  final options = apiOptions.isEmpty ? [...fallback] : apiOptions;
  return [
    ...options,
    const _LedgerOption(
      name: '自定义',
      subtitle: '临时填写，常用分类可到管理页新增',
      icon: LucideIcons.pencilLine,
      isCustom: true,
    ),
  ];
}

IconData _categoryIcon(String icon) {
  return switch (icon) {
    'leaf' => LucideIcons.leaf,
    'flask' => LucideIcons.flaskConical,
    'shield-alert' => LucideIcons.shieldAlert,
    'users' => LucideIcons.users,
    'droplet' => LucideIcons.droplets,
    'home' => LucideIcons.house,
    'shopping-cart' => LucideIcons.shoppingCart,
    'hand-coins' => LucideIcons.handCoins,
    _ => LucideIcons.tag,
  };
}

String _ledgerFirstNonEmpty(
  List<Object?> values, {
  String fallback = '',
}) {
  for (final value in values) {
    final text = '$value'.trim();
    if (value != null && text.isNotEmpty && text != 'null') return text;
  }
  return fallback;
}
