import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../data/api/api_client.dart';
import '../../data/api/api_models.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';
import 'business_ui.dart';

typedef RecordCardBuilder = Widget Function(
  ApiRecord record,
  bool selectionMode,
  bool selected,
);

class BulkDeleteListSection extends StatefulWidget {
  const BulkDeleteListSection({
    super.key,
    required this.items,
    required this.emptyMessage,
    required this.errorMessage,
    required this.deleteTitle,
    required this.deleteSuccessName,
    required this.onDeleteRecord,
    required this.cardBuilder,
    this.hasError = false,
    this.onDeleted,
  });

  final List<ApiRecord> items;
  final bool hasError;
  final String emptyMessage;
  final String errorMessage;
  final String deleteTitle;
  final String deleteSuccessName;
  final Future<void> Function(int id) onDeleteRecord;
  final RecordCardBuilder cardBuilder;
  final VoidCallback? onDeleted;

  @override
  State<BulkDeleteListSection> createState() => _BulkDeleteListSectionState();
}

class _BulkDeleteListSectionState extends State<BulkDeleteListSection> {
  final Set<int> _selectedIds = {};
  bool _deleting = false;

  bool get _selectionMode => _selectedIds.isNotEmpty;

  @override
  Widget build(BuildContext context) {
    if (widget.items.isEmpty && widget.hasError) {
      return BusinessCard(
        padding: const EdgeInsets.all(18),
        child: Text(widget.errorMessage),
      );
    }
    if (widget.items.isEmpty) {
      return BusinessCard(
        padding: const EdgeInsets.all(18),
        child: Text(widget.emptyMessage),
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (_selectionMode) ...[
          BulkSelectionBar(
            selectedCount: _selectedIds.length,
            deleting: _deleting,
            onCancel: _clearSelection,
            onDelete: _confirmDelete,
          ),
          const SizedBox(height: 12),
        ],
        for (final item in widget.items) ...[
          _SelectableRecordCard(
            selected: item.id != null && _selectedIds.contains(item.id),
            selectionMode: _selectionMode,
            onTap: () => _handleTap(item),
            onLongPress: () => _startSelection(item),
            child: widget.cardBuilder(
              item,
              _selectionMode,
              item.id != null && _selectedIds.contains(item.id),
            ),
          ),
          const SizedBox(height: 12),
        ],
      ],
    );
  }

  void _startSelection(ApiRecord record) {
    final id = record.id;
    if (id == null) return;
    setState(() {
      _selectedIds.add(id);
    });
  }

  void _handleTap(ApiRecord record) {
    if (!_selectionMode) return;
    final id = record.id;
    if (id == null) return;
    setState(() {
      if (!_selectedIds.add(id)) {
        _selectedIds.remove(id);
      }
    });
  }

  void _clearSelection() {
    setState(_selectedIds.clear);
  }

  Future<void> _confirmDelete() async {
    if (_selectedIds.isEmpty || _deleting) return;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('删除选中的${widget.deleteTitle}？'),
        content: Text(
          '将删除 ${_selectedIds.length} 项，删除后不可恢复。',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('取消'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: AppColors.red),
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('确认删除'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    await _deleteSelected();
  }

  Future<void> _deleteSelected() async {
    final ids = _selectedIds.toList();
    setState(() {
      _deleting = true;
    });
    try {
      for (final id in ids) {
        await widget.onDeleteRecord(id);
      }
      if (!mounted) return;
      setState(() {
        _selectedIds.clear();
        _deleting = false;
      });
      widget.onDeleted?.call();
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
            content: Text('已删除 ${ids.length} 个${widget.deleteSuccessName}')),
      );
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _deleting = false;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(ApiClient.userMessageFor(error))),
      );
    }
  }
}

class BulkSelectionBar extends StatelessWidget {
  const BulkSelectionBar({
    super.key,
    required this.selectedCount,
    required this.deleting,
    required this.onCancel,
    required this.onDelete,
  });

  final int selectedCount;
  final bool deleting;
  final VoidCallback onCancel;
  final VoidCallback onDelete;

  @override
  Widget build(BuildContext context) {
    return BusinessCard(
      padding: const EdgeInsets.fromLTRB(12, 12, 12, 12),
      child: Row(
        children: [
          Expanded(
            child: Text(
              '已选 $selectedCount 个',
              style: AppTextStyles.sectionTitle.copyWith(
                color: AppColors.ink,
                fontSize: 16,
                fontWeight: FontWeight.w900,
              ),
            ),
          ),
          SizedBox(
            width: 88,
            child: FilledActionButton(
              label: '取消',
              foreground: AppColors.muted,
              background: Colors.white,
              borderColor: AppColors.line,
              height: 40,
              onTap: deleting ? null : onCancel,
            ),
          ),
          const SizedBox(width: 10),
          SizedBox(
            width: 112,
            child: FilledActionButton(
              label: deleting ? '删除中' : '删除 $selectedCount 项',
              foreground: Colors.white,
              background: AppColors.red,
              borderColor: AppColors.red,
              icon: LucideIcons.trash2,
              height: 40,
              onTap: deleting ? null : onDelete,
            ),
          ),
        ],
      ),
    );
  }
}

class _SelectableRecordCard extends StatelessWidget {
  const _SelectableRecordCard({
    required this.child,
    required this.selectionMode,
    required this.selected,
    required this.onTap,
    required this.onLongPress,
  });

  final Widget child;
  final bool selectionMode;
  final bool selected;
  final VoidCallback onTap;
  final VoidCallback onLongPress;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      onLongPress: onLongPress,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 160),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(businessCardRadius + 4),
          border: Border.all(
            color: selected ? businessBlue : Colors.transparent,
            width: 2,
          ),
        ),
        child: child,
      ),
    );
  }
}

class SelectionCheckbox extends StatelessWidget {
  const SelectionCheckbox({
    super.key,
    required this.visible,
    required this.selected,
  });

  final bool visible;
  final bool selected;

  @override
  Widget build(BuildContext context) {
    return AnimatedSwitcher(
      duration: const Duration(milliseconds: 160),
      child: visible
          ? Padding(
              key: const ValueKey('visible'),
              padding: const EdgeInsets.only(right: 10),
              child: IgnorePointer(
                child: Checkbox(
                  value: selected,
                  onChanged: (_) {},
                  visualDensity: VisualDensity.compact,
                  activeColor: businessBlue,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(6),
                  ),
                ),
              ),
            )
          : const SizedBox.shrink(key: ValueKey('hidden')),
    );
  }
}
