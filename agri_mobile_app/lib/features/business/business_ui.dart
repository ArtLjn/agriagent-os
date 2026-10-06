import 'package:flutter/material.dart';
import 'package:dropdown_search/dropdown_search.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../data/api/api_models.dart';
import '../../data/repositories/business_repository.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';
import '../shell/bottom_tab_bar.dart';

const businessBlue = AppColors.blue;
const businessBlueDark = AppColors.blueDark;
const businessCardRadius = 20.0;
const businessGreen = AppColors.greenDark;
const businessGreenDark = AppColors.greenDark;

class BusinessPageFrame extends StatelessWidget {
  const BusinessPageFrame({
    super.key,
    required this.title,
    required this.children,
    this.trailingIcon,
    this.trailingOnTap,
    this.bottomBar,
    this.showBottomTabs = false,
    this.onBottomTabChanged,
    this.bottomOverlay,
  });

  final String title;
  final IconData? trailingIcon;
  final VoidCallback? trailingOnTap;
  final List<Widget> children;
  final Widget? bottomBar;
  final bool showBottomTabs;
  final ValueChanged<int>? onBottomTabChanged;
  final Widget? bottomOverlay;

  @override
  Widget build(BuildContext context) {
    final bottomPadding = bottomBar != null
        ? 32.0
        : showBottomTabs
            ? 104.0
            : 32.0;
    return Scaffold(
      backgroundColor: AppColors.background,
      bottomNavigationBar: showBottomTabs
          ? AppBottomTabBar(
              selectedIndex: 1,
              onChanged: onBottomTabChanged ?? (_) {},
            )
          : bottomBar,
      body: Stack(
        fit: StackFit.expand,
        children: [
          DecoratedBox(
            decoration: const BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [Colors.white, AppColors.background],
              ),
            ),
            child: SafeArea(
              child: SingleChildScrollView(
                padding: EdgeInsets.fromLTRB(24, 16, 24, bottomPadding),
                child: Center(
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 430),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        BusinessHeader(
                          title: title,
                          trailingIcon: trailingIcon,
                          trailingOnTap: trailingOnTap,
                        ),
                        const SizedBox(height: 16),
                        for (final child in children) ...[
                          child,
                          const SizedBox(height: 16),
                        ],
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
          if (bottomOverlay != null)
            Positioned(
              left: 14,
              right: 14,
              bottom: 24,
              child: SafeArea(
                top: false,
                child: bottomOverlay!,
              ),
            ),
        ],
      ),
    );
  }
}

class BusinessHeader extends StatelessWidget {
  const BusinessHeader({
    super.key,
    required this.title,
    this.trailingIcon,
    this.trailingOnTap,
  });

  final String title;
  final IconData? trailingIcon;
  final VoidCallback? trailingOnTap;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 48,
      child: Row(
        children: [
          HeaderIconButton(
            icon: LucideIcons.chevronLeft,
            onTap: () {
              final navigator = Navigator.of(context);
              if (navigator.canPop()) navigator.pop();
            },
          ),
          Expanded(
            child: Text(
              title,
              textAlign: TextAlign.left,
              style: const TextStyle(
                color: AppColors.ink,
                fontSize: 22,
                height: 28 / 22,
                fontWeight: FontWeight.w600,
                letterSpacing: 0,
              ),
            ),
          ),
          if (trailingOnTap != null)
            HeaderIconButton(
                icon: trailingIcon ?? LucideIcons.moreHorizontal,
                onTap: trailingOnTap)
          else
            const SizedBox(width: 12),
        ],
      ),
    );
  }
}

class BusinessCard extends StatelessWidget {
  const BusinessCard({
    super.key,
    required this.child,
    this.padding = EdgeInsets.zero,
  });

  final Widget child;
  final EdgeInsets padding;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: padding,
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(businessCardRadius),
        border: Border.all(color: AppColors.lineSoft),
      ),
      child: child,
    );
  }
}

class BusinessCardHeader extends StatelessWidget {
  const BusinessCardHeader({
    super.key,
    required this.title,
    required this.icon,
    this.trailing,
  });

  final String title;
  final IconData icon;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 12),
      child: Row(
        children: [
          Icon(icon, color: AppColors.muted, size: 18),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              title,
              style: AppTextStyles.sectionTitle.copyWith(
                fontSize: 16,
                height: 24 / 16,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
          if (trailing != null) trailing!,
        ],
      ),
    );
  }
}

class FormRowsCard extends StatelessWidget {
  const FormRowsCard({
    super.key,
    required this.title,
    required this.icon,
    required this.children,
  });

  final String title;
  final IconData icon;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.only(bottom: 12),
          child: Row(children: [
            Icon(icon, color: AppColors.muted, size: 16),
            const SizedBox(width: 8),
            Expanded(child: Text(title, style: AppTextStyles.listTitle)),
          ]),
        ),
        BusinessCard(child: Column(children: children)),
      ],
    );
  }
}

class BusinessFormRow extends StatelessWidget {
  const BusinessFormRow({
    super.key,
    required this.label,
    required this.value,
    this.controller,
    this.large = false,
    this.chevron = false,
    this.keyboardType,
    this.onTap,
    this.hintText,
    this.readOnly = false,
  });

  final String label;
  final String value;
  final TextEditingController? controller;
  final bool large;
  final bool chevron;
  final TextInputType? keyboardType;
  final VoidCallback? onTap;
  final String? hintText;
  final bool readOnly;

  @override
  Widget build(BuildContext context) {
    final field = controller == null
        ? Text(
            value,
            maxLines: large ? 2 : 1,
            overflow: TextOverflow.ellipsis,
            textAlign: TextAlign.right,
            style: TextStyle(
              color: AppColors.ink,
              fontSize: large ? 27 : 16,
              height: large ? 33 / 27 : 23 / 16,
              fontWeight: FontWeight.w600,
              letterSpacing: 0,
            ),
          )
        : TextField(
            controller: controller,
            keyboardType: keyboardType,
            readOnly: readOnly,
            onTap: readOnly ? onTap : null,
            textAlign: TextAlign.right,
            style: TextStyle(
              color: AppColors.ink,
              fontSize: large ? 27 : 16,
              height: large ? 33 / 27 : 23 / 16,
              fontWeight: FontWeight.w600,
              letterSpacing: 0,
            ),
            decoration: InputDecoration(
              hintText: hintText ?? (value.isEmpty ? null : value),
              hintStyle: AppTextStyles.body.copyWith(
                color: AppColors.subtle,
                fontWeight: FontWeight.w500,
              ),
              border: InputBorder.none,
              isDense: true,
              contentPadding: EdgeInsets.zero,
            ),
          );

    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(0),
      child: Container(
        constraints: BoxConstraints(minHeight: large ? 80 : 64),
        padding: const EdgeInsets.symmetric(horizontal: 16),
        decoration: const BoxDecoration(
          border: Border(bottom: BorderSide(color: AppColors.lineSoft)),
        ),
        child: Row(
          children: [
            SizedBox(
              width: 84,
              child: Text(
                label,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  color: large ? AppColors.ink : AppColors.muted,
                  fontSize: large ? 19 : 16,
                  height: 23 / 16,
                  fontWeight: FontWeight.w600,
                  letterSpacing: 0,
                ),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(child: field),
            if (chevron) ...[
              const SizedBox(width: 8),
              const Icon(LucideIcons.chevronRight,
                  size: 22, color: AppColors.subtle),
            ],
          ],
        ),
      ),
    );
  }
}

class ApiRecordDropdownFormRow extends StatefulWidget {
  const ApiRecordDropdownFormRow({
    super.key,
    required this.label,
    required this.future,
    required this.displayNameFor,
    required this.onSelected,
    this.subtitleFor,
    this.selectedItem,
    this.selectedId,
    this.placeholder = '请选择',
    this.sheetTitle = '请选择',
    this.sheetSubtitle = '',
    this.searchHint = '搜索',
    this.emptyText = '没有匹配数据',
    this.optionKeyPrefix = 'api-record-option',
    this.icon = LucideIcons.listChecks,
    this.accent = businessGreen,
  });

  final String label;
  final Future<PageResult<ApiRecord>> future;
  final String Function(ApiRecord item) displayNameFor;
  final String Function(ApiRecord item)? subtitleFor;
  final ApiRecord? selectedItem;
  final int? selectedId;
  final String placeholder;
  final String sheetTitle;
  final String sheetSubtitle;
  final String searchHint;
  final String emptyText;
  final String optionKeyPrefix;
  final IconData icon;
  final Color accent;
  final ValueChanged<ApiRecord> onSelected;

  @override
  State<ApiRecordDropdownFormRow> createState() =>
      _ApiRecordDropdownFormRowState();
}

class _ApiRecordDropdownFormRowState extends State<ApiRecordDropdownFormRow> {
  List<ApiRecord> _lastItems = const [];

  Future<List<ApiRecord>> _loadItems(String filter) async {
    final response = await widget.future.catchError(
      (_) => const PageResult<ApiRecord>(items: [], total: 0),
    );
    final items = response.items;
    _lastItems = items;
    final keyword = filter.trim();
    if (keyword.isEmpty) return items;
    return items.where((item) {
      final subtitle = widget.subtitleFor?.call(item) ?? '';
      return widget.displayNameFor(item).contains(keyword) ||
          subtitle.contains(keyword);
    }).toList();
  }

  @override
  Widget build(BuildContext context) {
    final selected = _selectedItem();
    return Container(
      constraints: const BoxConstraints(minHeight: 56),
      padding: const EdgeInsets.fromLTRB(16, 0, 12, 0),
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: AppColors.lineSoft)),
      ),
      child: Row(
        children: [
          SizedBox(
            width: 84,
            child: Text(
              widget.label,
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
            child: SizedBox(
              height: 56,
              child: DropdownSearch<ApiRecord>(
                selectedItem: selected,
                compareFn: (a, b) => a.id == b.id,
                itemAsString: widget.displayNameFor,
                items: (filter, _) => _loadItems(filter),
                onSelected: (value) {
                  if (value != null) widget.onSelected(value);
                },
                dropdownBuilder: (context, item) => _ApiRecordSelectedView(
                  item: item,
                  placeholder: widget.placeholder,
                  displayNameFor: widget.displayNameFor,
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
                      hintText: widget.searchHint,
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
                          const _BusinessDropdownSheetGrabber(),
                          const SizedBox(height: 14),
                          _BusinessDropdownSheetTitle(
                            title: widget.sheetTitle,
                            subtitle: widget.sheetSubtitle,
                          ),
                          const SizedBox(height: 12),
                          Expanded(child: child),
                        ],
                      ),
                    ),
                  ),
                  itemBuilder: (context, item, _, isSelected) =>
                      _DropdownSearchApiRecordTile(
                    item: item,
                    selected: isSelected,
                    displayNameFor: widget.displayNameFor,
                    subtitleFor: widget.subtitleFor,
                    optionKeyPrefix: widget.optionKeyPrefix,
                    icon: widget.icon,
                    accent: widget.accent,
                  ),
                  emptyBuilder: (context, _) => _ApiRecordDropdownEmptyState(
                    text: widget.emptyText,
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  ApiRecord? _selectedItem() {
    final item = widget.selectedItem;
    if (item != null) return item;
    final selectedId = widget.selectedId;
    if (selectedId == null) return null;
    for (final item in _lastItems) {
      if (item.id == selectedId) return item;
    }
    return null;
  }
}

class _ApiRecordSelectedView extends StatelessWidget {
  const _ApiRecordSelectedView({
    required this.item,
    required this.placeholder,
    required this.displayNameFor,
  });

  final ApiRecord? item;
  final String placeholder;
  final String Function(ApiRecord item) displayNameFor;

  @override
  Widget build(BuildContext context) {
    final selected = item;
    return Align(
      alignment: Alignment.centerRight,
      child: Text(
        selected == null ? placeholder : displayNameFor(selected),
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        textAlign: TextAlign.right,
        style: AppTextStyles.body.copyWith(
          color: selected == null ? AppColors.subtle : AppColors.ink,
          fontSize: 16,
          height: 22 / 16,
          fontWeight: selected == null ? FontWeight.w600 : FontWeight.w600,
        ),
      ),
    );
  }
}

class _DropdownSearchApiRecordTile extends StatelessWidget {
  const _DropdownSearchApiRecordTile({
    required this.item,
    required this.selected,
    required this.displayNameFor,
    required this.subtitleFor,
    required this.optionKeyPrefix,
    required this.icon,
    required this.accent,
  });

  final ApiRecord item;
  final bool selected;
  final String Function(ApiRecord item) displayNameFor;
  final String Function(ApiRecord item)? subtitleFor;
  final String optionKeyPrefix;
  final IconData icon;
  final Color accent;

  @override
  Widget build(BuildContext context) {
    final title = displayNameFor(item);
    final subtitle = subtitleFor?.call(item) ?? '';
    return Container(
      key: Key('$optionKeyPrefix-$title'),
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: selected ? accent.withValues(alpha: 0.08) : AppColors.surface3,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: selected ? accent.withValues(alpha: 0.42) : AppColors.lineSoft,
        ),
      ),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: accent.withValues(alpha: 0.10),
              borderRadius: BorderRadius.circular(13),
            ),
            child: Icon(icon, color: accent, size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppTextStyles.listTitle.copyWith(
                    fontSize: 16,
                    height: 22 / 16,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                if (subtitle.isNotEmpty) ...[
                  const SizedBox(height: 2),
                  Text(
                    subtitle,
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
            color: selected ? accent : AppColors.subtle,
            size: selected ? 19 : 20,
          ),
        ],
      ),
    );
  }
}

class _ApiRecordDropdownEmptyState extends StatelessWidget {
  const _ApiRecordDropdownEmptyState({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 28),
        child: Text(
          text,
          style: AppTextStyles.body.copyWith(
            color: AppColors.muted,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
    );
  }
}

class CyclePickerFormRow extends StatefulWidget {
  const CyclePickerFormRow({
    super.key,
    required this.repository,
    required this.selectedCycleId,
    required this.selectedCycleName,
    required this.onSelected,
    this.label = '关联茬口',
  });

  final BusinessRepository repository;
  final int? selectedCycleId;
  final String selectedCycleName;
  final ValueChanged<ApiRecord> onSelected;
  final String label;

  @override
  State<CyclePickerFormRow> createState() => _CyclePickerFormRowState();
}

class _CyclePickerFormRowState extends State<CyclePickerFormRow> {
  late Future<PageResult<ApiRecord>> _cyclesFuture;
  List<ApiRecord> _lastCycles = const [];

  @override
  void initState() {
    super.initState();
    _cyclesFuture = widget.repository.listAllCycles();
  }

  Future<List<ApiRecord>> _loadCycles(String filter) async {
    final response = await _cyclesFuture.catchError(
      (_) => const PageResult<ApiRecord>(items: [], total: 0),
    );
    final items = response.items;
    _lastCycles = items;
    final keyword = filter.trim();
    if (keyword.isEmpty) return items;
    return items
        .where((item) =>
            _cycleDisplayName(item).contains(keyword) ||
            _cycleSubtitle(item).contains(keyword))
        .toList();
  }

  @override
  Widget build(BuildContext context) {
    final selected = _selectedCycle();
    return Container(
      constraints: const BoxConstraints(minHeight: 56),
      padding: const EdgeInsets.fromLTRB(16, 0, 12, 0),
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: AppColors.lineSoft)),
      ),
      child: Row(
        children: [
          SizedBox(
            width: 84,
            child: Text(
              widget.label,
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
            child: SizedBox(
              height: 56,
              child: DropdownSearch<ApiRecord>(
                key: const Key('cycle-dropdown-search'),
                selectedItem: selected,
                compareFn: (a, b) => a.id == b.id,
                itemAsString: _cycleDisplayName,
                items: (filter, _) => _loadCycles(filter),
                onSelected: (value) {
                  if (value != null) widget.onSelected(value);
                },
                dropdownBuilder: (context, item) => _CycleSelectedView(
                  cycle: item,
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
                      hintText: '搜索茬口',
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
                          const _BusinessDropdownSheetGrabber(),
                          const SizedBox(height: 14),
                          const _BusinessDropdownSheetTitle(
                            title: '选择茬口',
                            subtitle: '选择后自动关联农事、工资和账本记录',
                          ),
                          const SizedBox(height: 12),
                          Expanded(child: child),
                        ],
                      ),
                    ),
                  ),
                  itemBuilder: (context, item, _, isSelected) =>
                      _DropdownSearchCycleTile(
                    cycle: item,
                    selected: isSelected,
                  ),
                  emptyBuilder: (context, _) =>
                      const _CycleDropdownEmptyState(),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  ApiRecord? _selectedCycle() {
    final selectedId = widget.selectedCycleId;
    if (selectedId != null) {
      for (final cycle in _lastCycles) {
        if (cycle.id == selectedId) return cycle;
      }
    }
    final selectedName = widget.selectedCycleName.trim();
    if (selectedName.isEmpty) return null;
    return ApiRecord({
      'id': selectedId,
      'name': selectedName,
    });
  }
}

class _CycleSelectedView extends StatelessWidget {
  const _CycleSelectedView({required this.cycle});

  final ApiRecord? cycle;

  @override
  Widget build(BuildContext context) {
    final selected = cycle;
    return Align(
      alignment: Alignment.centerRight,
      child: Text(
        selected == null ? '选择茬口' : _cycleDisplayName(selected),
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        textAlign: TextAlign.right,
        style: AppTextStyles.body.copyWith(
          color: selected == null ? AppColors.subtle : AppColors.ink,
          fontSize: 16,
          height: 22 / 16,
          fontWeight: selected == null ? FontWeight.w600 : FontWeight.w600,
        ),
      ),
    );
  }
}

class _DropdownSearchCycleTile extends StatelessWidget {
  const _DropdownSearchCycleTile({
    required this.cycle,
    required this.selected,
  });

  final ApiRecord cycle;
  final bool selected;

  @override
  Widget build(BuildContext context) {
    return Container(
      key: Key('cycle-option-${_cycleDisplayName(cycle)}'),
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
            child: const Icon(
              LucideIcons.layers,
              color: businessGreenDark,
              size: 20,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _cycleDisplayName(cycle),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppTextStyles.listTitle.copyWith(
                    fontSize: 16,
                    height: 22 / 16,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                if (_cycleSubtitle(cycle).isNotEmpty) ...[
                  const SizedBox(height: 2),
                  Text(
                    _cycleSubtitle(cycle),
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

class _CycleDropdownEmptyState extends StatelessWidget {
  const _CycleDropdownEmptyState();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 28),
        child: Text(
          '没有匹配茬口',
          style: AppTextStyles.body.copyWith(
            color: AppColors.muted,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
    );
  }
}

class _BusinessDropdownSheetGrabber extends StatelessWidget {
  const _BusinessDropdownSheetGrabber();

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

class _BusinessDropdownSheetTitle extends StatelessWidget {
  const _BusinessDropdownSheetTitle({
    required this.title,
    required this.subtitle,
  });

  final String title;
  final String subtitle;

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
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                subtitle,
                style: AppTextStyles.body.copyWith(
                  color: AppColors.muted,
                  fontSize: 13,
                  height: 18 / 13,
                  fontWeight: FontWeight.w600,
                ),
              ),
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

String _cycleDisplayName(ApiRecord record) {
  return _firstNonEmpty([record.json['name']], fallback: '未命名茬口');
}

String _cycleSubtitle(ApiRecord record) {
  final fieldName = _firstNonEmpty([record.json['field_name']]);
  final crop = _firstNonEmpty([record.json['crop_name']]);
  final stage = _firstNonEmpty([record.json['current_stage_name']]);
  final status = _firstNonEmpty([record.json['status']]);
  return [fieldName, crop, stage, status]
      .where((item) => item.isNotEmpty)
      .join(' · ');
}

String _firstNonEmpty(List<Object?> values, {String fallback = ''}) {
  for (final value in values) {
    final text = '$value'.trim();
    if (value != null && text.isNotEmpty && text != 'null') return text;
  }
  return fallback;
}

class SegmentedFormRow extends StatelessWidget {
  const SegmentedFormRow({
    super.key,
    required this.label,
    required this.options,
    required this.value,
    required this.onChanged,
  });

  final String label;
  final Map<String, String> options;
  final String value;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(minHeight: 66),
      padding: const EdgeInsets.fromLTRB(16, 9, 16, 9),
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: AppColors.lineSoft)),
      ),
      child: Row(
        children: [
          SizedBox(
            width: 84,
            child: Text(
              label,
              style: AppTextStyles.sectionTitle.copyWith(
                fontSize: 16,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
          Expanded(
            child: Container(
              padding: const EdgeInsets.all(3),
              decoration: BoxDecoration(
                color: AppColors.surface2,
                borderRadius: BorderRadius.circular(15),
                border: Border.all(color: AppColors.line),
              ),
              child: Row(
                children: options.entries.map((entry) {
                  final selected = entry.key == value;
                  return Expanded(
                    child: GestureDetector(
                      onTap: () => onChanged(entry.key),
                      child: AnimatedContainer(
                        duration: const Duration(milliseconds: 160),
                        height: 40,
                        alignment: Alignment.center,
                        decoration: BoxDecoration(
                          color: selected ? businessBlue : Colors.transparent,
                          borderRadius: BorderRadius.circular(13),
                          boxShadow: selected
                              ? [
                                  BoxShadow(
                                    color: businessBlue.withValues(alpha: 0.22),
                                    blurRadius: 12,
                                    offset: const Offset(0, 5),
                                  ),
                                ]
                              : null,
                        ),
                        child: Text(
                          entry.value,
                          style: AppTextStyles.listTitle.copyWith(
                            color: selected ? Colors.white : AppColors.ink,
                            fontSize: 15,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ),
                  );
                }).toList(),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class BottomActions extends StatelessWidget {
  const BottomActions({
    super.key,
    required this.secondaryLabel,
    required this.primaryLabel,
    required this.onPrimary,
    this.onSecondary,
    this.primaryEnabled = true,
    this.primaryLoading = false,
    this.showTabs = false,
    this.onBottomTabChanged,
  });

  final String secondaryLabel;
  final String primaryLabel;
  final VoidCallback onPrimary;
  final VoidCallback? onSecondary;
  final bool primaryEnabled;
  final bool primaryLoading;
  final bool showTabs;
  final ValueChanged<int>? onBottomTabChanged;

  @override
  Widget build(BuildContext context) {
    final actions = Container(
      padding: const EdgeInsets.fromLTRB(24, 12, 24, 12),
      decoration: const BoxDecoration(
        color: Colors.white,
        border: Border(top: BorderSide(color: AppColors.lineSoft)),
      ),
      child: Row(
        children: [
          Expanded(
            child: FilledActionButton(
              label: secondaryLabel,
              foreground: businessBlue,
              background: Colors.white,
              borderColor: AppColors.line,
              onTap: onSecondary,
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: FilledActionButton(
              label: primaryLabel,
              foreground: Colors.white,
              background: primaryEnabled ? businessBlue : AppColors.subtle,
              borderColor: primaryEnabled ? businessBlue : AppColors.subtle,
              onTap: primaryEnabled && !primaryLoading ? onPrimary : null,
              loading: primaryLoading,
            ),
          ),
        ],
      ),
    );

    if (!showTabs) return SafeArea(top: false, child: actions);
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        actions,
        AppBottomTabBar(
          selectedIndex: 1,
          onChanged: onBottomTabChanged ?? (_) {},
        ),
      ],
    );
  }
}

class FilledActionButton extends StatelessWidget {
  const FilledActionButton({
    super.key,
    required this.label,
    required this.foreground,
    required this.background,
    required this.borderColor,
    this.onTap,
    this.icon,
    this.loading = false,
    this.height = 56,
  });

  final String label;
  final Color foreground;
  final Color background;
  final Color borderColor;
  final VoidCallback? onTap;
  final IconData? icon;
  final bool loading;
  final double height;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      child: Container(
        height: height,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: background,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: borderColor),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            if (loading) ...[
              SizedBox(
                width: height < 44 ? 17 : 19,
                height: height < 44 ? 17 : 19,
                child: CircularProgressIndicator(
                  strokeWidth: 2.2,
                  valueColor: AlwaysStoppedAnimation<Color>(foreground),
                ),
              ),
              SizedBox(width: height < 44 ? 6 : 8),
            ] else if (icon != null) ...[
              Icon(icon, color: foreground, size: height < 44 ? 19 : 21),
              SizedBox(width: height < 44 ? 6 : 8),
            ],
            Text(
              label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: AppTextStyles.sectionTitle.copyWith(
                color: foreground,
                fontSize: height < 44 ? 14 : 16,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class SoftPill extends StatelessWidget {
  const SoftPill({
    super.key,
    required this.text,
    required this.color,
    required this.background,
  });

  final String text;
  final Color color;
  final Color background;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: color.withValues(alpha: 0.12)),
      ),
      child: Text(
        text,
        style: AppTextStyles.small.copyWith(
          color: color,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}

class HeaderIconButton extends StatelessWidget {
  const HeaderIconButton({super.key, required this.icon, this.onTap});

  final IconData icon;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      child: SizedBox(
        width: 46,
        height: 46,
        child: Icon(icon, size: 27, color: AppColors.ink),
      ),
    );
  }
}

class SearchFieldCard extends StatelessWidget {
  const SearchFieldCard({
    super.key,
    required this.text,
    this.controller,
    this.onChanged,
  });

  final String text;
  final TextEditingController? controller;
  final ValueChanged<String>? onChanged;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 54,
      padding: const EdgeInsets.symmetric(horizontal: 15),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(17),
        border: Border.all(color: AppColors.lineSoft),
      ),
      child: Row(
        children: [
          const Icon(LucideIcons.search, size: 20, color: AppColors.subtle),
          const SizedBox(width: 10),
          Expanded(
            child: controller == null && onChanged == null
                ? Text(
                    text,
                    style: AppTextStyles.body.copyWith(
                      color: AppColors.subtle,
                      fontSize: 15,
                    ),
                  )
                : TextField(
                    controller: controller,
                    onChanged: onChanged,
                    textInputAction: TextInputAction.search,
                    decoration: InputDecoration.collapsed(
                      hintText: text,
                      hintStyle: AppTextStyles.body.copyWith(
                        color: AppColors.subtle,
                        fontSize: 15,
                      ),
                    ),
                    style: AppTextStyles.body.copyWith(
                      color: AppColors.ink,
                      fontSize: 15,
                    ),
                  ),
          ),
        ],
      ),
    );
  }
}

class ChipRail extends StatelessWidget {
  const ChipRail({
    super.key,
    required this.items,
    this.activeIndex = 0,
    this.activeColor = businessBlue,
    this.onSelected,
  });

  final List<String> items;
  final int activeIndex;
  final Color activeColor;
  final ValueChanged<int>? onSelected;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        children: [
          for (var i = 0; i < items.length; i++) ...[
            GestureDetector(
              behavior: HitTestBehavior.opaque,
              onTap: onSelected == null ? null : () => onSelected!(i),
              child: SoftPill(
                text: items[i],
                color: i == activeIndex ? activeColor : AppColors.ink2,
                background: i == activeIndex
                    ? activeColor.withValues(alpha: 0.10)
                    : Colors.white,
              ),
            ),
            const SizedBox(width: 8),
          ],
        ],
      ),
    );
  }
}

class LoadingCard extends StatelessWidget {
  const LoadingCard({super.key});

  @override
  Widget build(BuildContext context) {
    return const BusinessCard(
      padding: EdgeInsets.all(20),
      child: Center(child: CircularProgressIndicator(strokeWidth: 2.4)),
    );
  }
}

class StageEditRow extends StatelessWidget {
  const StageEditRow({
    super.key,
    required this.index,
    required this.title,
    required this.days,
    required this.color,
  });

  final int index;
  final String title;
  final String days;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 56,
      margin: const EdgeInsets.fromLTRB(14, 0, 14, 8),
      padding: const EdgeInsets.symmetric(horizontal: 14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.lineSoft),
      ),
      child: Row(
        children: [
          const Icon(LucideIcons.gripVertical,
              color: AppColors.subtle, size: 20),
          const SizedBox(width: 10),
          Container(
            width: 30,
            height: 30,
            alignment: Alignment.center,
            decoration: BoxDecoration(shape: BoxShape.circle, color: color),
            child: Text(
              '$index',
              style: AppTextStyles.sectionTitle.copyWith(
                color: Colors.white,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Text(
              title,
              style: AppTextStyles.sectionTitle.copyWith(
                fontSize: 17,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Row(
              children: [
                Icon(LucideIcons.calendarDays, color: color, size: 17),
                const SizedBox(width: 6),
                Text(
                  days,
                  style: AppTextStyles.sectionTitle.copyWith(
                    color: color,
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
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

class AddDashedRow extends StatelessWidget {
  const AddDashedRow({super.key, required this.label, this.onTap});

  final String label;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      child: Container(
        height: 52,
        margin: const EdgeInsets.fromLTRB(62, 2, 62, 16),
        alignment: Alignment.center,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: businessGreen.withValues(alpha: 0.52),
            style: BorderStyle.solid,
          ),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(LucideIcons.circlePlus, color: businessGreen, size: 24),
            const SizedBox(width: 8),
            Text(
              label,
              style: AppTextStyles.sectionTitle.copyWith(
                color: businessGreen,
                fontSize: 17,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
