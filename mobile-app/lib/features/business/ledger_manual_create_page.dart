import 'package:flutter/material.dart';
import 'package:dropdown_search/dropdown_search.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../data/api/api_models.dart';
import '../../data/repositories/business_repository.dart';
import '../../shared/assets/app_assets.dart';
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
        _LedgerHeroBanner(
          asset: AppAssets.businessLedgerFarmBanner,
          amount: _amount.text.trim(),
        ),
        _LedgerQuickCard(
          title: '记一笔',
          icon: LucideIcons.walletCards,
          children: [
            SegmentedFormRow(
              label: '类型',
              options: const {'cost': '支出', 'income': '收入'},
              value: _recordType,
              onChanged: (value) => setState(() {
                _recordType = value;
                _category.clear();
                _customCategory = false;
              }),
            ),
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
              BusinessFormRow(
                label: '自定义分类',
                value: '',
                controller: _category,
                hintText: '输入分类名称',
              ),
            BusinessFormRow(
              label: '金额',
              value: '',
              controller: _amount,
              hintText: '输入金额',
              large: true,
              keyboardType: TextInputType.number,
            ),
            _LedgerDateTimeFormRow(
              label: '日期',
              dateText: _recordDateText,
              timeText: _recordTimeText,
              onTap: _pickDateTime,
            ),
            BusinessFormRow(
              label: '备注',
              value: '',
              controller: _note,
              hintText: '补充说明',
            ),
          ],
        ),
        const AssistEntryCard(text: '可用一句话智能填写'),
        const SizedBox(height: 8),
        const _LedgerHintCard(),
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

class _LedgerDateTimeFormRow extends StatelessWidget {
  const _LedgerDateTimeFormRow({
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
      key: const ValueKey('ledger-datetime-row'),
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
                    key: const ValueKey('ledger-date-text'),
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
                    key: const ValueKey('ledger-time-text'),
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

class _LedgerHeroBanner extends StatelessWidget {
  const _LedgerHeroBanner({
    required this.asset,
    required this.amount,
  });

  final String asset;
  final String amount;

  @override
  Widget build(BuildContext context) {
    final amountText = amount.isEmpty ? '今天随手记一笔' : '￥$amount';
    return Container(
      height: 156,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        color: const Color(0xFFF1F8F3),
        boxShadow: const [
          BoxShadow(
            color: Color(0x080B5C38),
            blurRadius: 14,
            offset: Offset(0, 6),
          ),
        ],
      ),
      clipBehavior: Clip.antiAlias,
      child: Stack(
        children: [
          Positioned.fill(
            child: Image.asset(
              asset,
              fit: BoxFit.cover,
              alignment: Alignment.centerRight,
              errorBuilder: (_, __, ___) => const DecoratedBox(
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.centerLeft,
                    end: Alignment.centerRight,
                    colors: [
                      Color(0xFFE8F8F0),
                      Color(0xFFEAF8FF),
                      Color(0xFFFFF5E6),
                    ],
                  ),
                ),
              ),
            ),
          ),
          Positioned.fill(
            child: DecoratedBox(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.centerLeft,
                  end: Alignment.centerRight,
                  colors: [
                    Colors.white.withValues(alpha: 0.92),
                    Colors.white.withValues(alpha: 0.64),
                    Colors.white.withValues(alpha: 0.04),
                  ],
                  stops: const [0, 0.48, 1],
                ),
              ),
            ),
          ),
          Positioned(
            left: 18,
            top: 18,
            bottom: 16,
            width: 202,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Icon(
                  LucideIcons.receiptText,
                  color: businessGreenDark,
                  size: 24,
                ),
                const Spacer(),
                Text(
                  '农场记账',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppTextStyles.title.copyWith(
                    color: AppColors.navy,
                    fontSize: 25,
                    height: 30 / 25,
                    fontWeight: FontWeight.w900,
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  amountText,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppTextStyles.body.copyWith(
                    color: businessGreenDark,
                    fontSize: 15,
                    height: 20 / 15,
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

class _LedgerQuickCard extends StatelessWidget {
  const _LedgerQuickCard({
    required this.title,
    required this.icon,
    required this.children,
  });

  final String title;
  final IconData icon;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFFEAF0F6)),
        boxShadow: const [
          BoxShadow(
            color: Color(0x04101828),
            blurRadius: 10,
            offset: Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        children: [
          BusinessCardHeader(title: title, icon: icon),
          ...children,
        ],
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
    final options = _categoryOptions(
      response.items,
      widget.recordType,
    );
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
    return Container(
      constraints: const BoxConstraints(minHeight: 56),
      padding: const EdgeInsets.fromLTRB(16, 0, 12, 0),
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: AppColors.lineSoft)),
      ),
      child: Row(
        children: [
          SizedBox(
            width: 116,
            child: Row(
              children: [
                const Expanded(
                  child: Text(
                    '分类',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      color: AppColors.muted,
                      fontSize: 16,
                      height: 23 / 16,
                      fontWeight: FontWeight.w600,
                      letterSpacing: 0,
                    ),
                  ),
                ),
                GestureDetector(
                  behavior: HitTestBehavior.opaque,
                  onTap: widget.onManageTap,
                  child: Padding(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 4,
                      vertical: 10,
                    ),
                    child: Text(
                      '管理',
                      style: AppTextStyles.small.copyWith(
                        color: AppColors.blue,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: SizedBox(
              height: 56,
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
                  placeholder:
                      widget.recordType == 'income' ? '选择收入分类' : '选择支出分类',
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
                      size: 20,
                    ),
                    iconOpened: Icon(
                      LucideIcons.chevronUp,
                      color: businessGreenDark,
                      size: 20,
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
                      padding: const EdgeInsets.fromLTRB(16, 10, 16, 16),
                      decoration: const BoxDecoration(
                        color: Colors.white,
                        borderRadius:
                            BorderRadius.vertical(top: Radius.circular(26)),
                        boxShadow: [
                          BoxShadow(
                            color: Color(0x1A10271D),
                            blurRadius: 26,
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
            fontSize: 16,
            height: 22 / 16,
            fontWeight: FontWeight.w600,
          ),
        ),
      );
    }
    return Align(
      alignment: Alignment.centerRight,
      child: Text(
        selected.name,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        textAlign: TextAlign.right,
        style: AppTextStyles.listTitle.copyWith(
          color: AppColors.ink,
          fontSize: 16,
          height: 22 / 16,
          fontWeight: FontWeight.w800,
        ),
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
            ? businessGreen.withValues(alpha: 0.08)
            : AppColors.surface3,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: selected
              ? businessGreen.withValues(alpha: 0.42)
              : AppColors.lineSoft,
        ),
      ),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: businessGreen.withValues(alpha: 0.10),
              borderRadius: BorderRadius.circular(13),
            ),
            child: Icon(option.icon, color: businessGreenDark, size: 20),
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
                  style: AppTextStyles.listTitle.copyWith(
                    fontSize: 16,
                    height: 22 / 16,
                    fontWeight: FontWeight.w900,
                  ),
                ),
                if (option.subtitle.isNotEmpty) ...[
                  const SizedBox(height: 2),
                  Text(
                    option.subtitle,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: AppTextStyles.body.copyWith(
                      color: AppColors.muted,
                      fontSize: 13,
                      height: 18 / 13,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],
              ],
            ),
          ),
          const SizedBox(width: 10),
          Icon(
            selected ? LucideIcons.check : LucideIcons.chevronRight,
            color: selected ? businessGreenDark : AppColors.subtle,
            size: selected ? 19 : 20,
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
            fontWeight: FontWeight.w700,
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
        width: 38,
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
  const _SheetTitle({required this.title, this.subtitle});

  final String title;
  final String? subtitle;

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
                style: AppTextStyles.sectionTitle.copyWith(
                  fontSize: 20,
                  height: 26 / 20,
                  fontWeight: FontWeight.w900,
                ),
              ),
              if (subtitle != null) ...[
                const SizedBox(height: 4),
                Text(
                  subtitle!,
                  style: AppTextStyles.body.copyWith(
                    color: AppColors.muted,
                    fontSize: 13,
                    height: 18 / 13,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ],
          ),
        ),
        IconButton(
          visualDensity: VisualDensity.compact,
          onPressed: () => Navigator.of(context).pop(),
          icon: const Icon(LucideIcons.x, size: 20),
        ),
      ],
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

class _LedgerHintCard extends StatelessWidget {
  const _LedgerHintCard();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.greenSoft,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.green.withValues(alpha: 0.16)),
      ),
      child: const Row(
        children: [
          Icon(LucideIcons.circleCheckBig,
              color: AppColors.greenDark, size: 20),
          SizedBox(width: 10),
          Expanded(
            child: Text(
              '只填类型、分类、金额和时间即可保存，常用分类可单独维护。',
              style: TextStyle(
                color: AppColors.greenDark,
                fontSize: 13,
                height: 18 / 13,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
