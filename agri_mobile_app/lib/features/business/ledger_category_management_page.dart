import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../data/api/api_models.dart';
import '../../data/repositories/business_repository.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';
import 'business_ui.dart';

class LedgerCategoryManagementPage extends StatefulWidget {
  const LedgerCategoryManagementPage({
    super.key,
    required this.repository,
    this.initialRecordType = 'cost',
  });

  static const routePath = '/ledger-categories';

  final BusinessRepository repository;
  final String initialRecordType;

  @override
  State<LedgerCategoryManagementPage> createState() =>
      _LedgerCategoryManagementPageState();
}

class _LedgerCategoryManagementPageState
    extends State<LedgerCategoryManagementPage> {
  late String _recordType;
  late Future<PageResult<ApiRecord>> _categoriesFuture;
  bool _deleting = false;

  @override
  void initState() {
    super.initState();
    _recordType = widget.initialRecordType == 'income' ? 'income' : 'cost';
    _categoriesFuture = widget.repository.listCostCategories();
  }

  void _reload() {
    setState(() {
      _categoriesFuture = widget.repository.listCostCategories();
    });
  }

  Future<void> _showCreateSheet() async {
    final created = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) => _CreateCategorySheet(
        repository: widget.repository,
        recordType: _recordType,
      ),
    );
    if (created == true) {
      _reload();
      _showMessage('分类已新增');
    }
  }

  Future<void> _deleteCategory(ApiRecord category) async {
    final isDefault = category.json['is_default'] as bool? ?? false;
    final categoryId = category.id;
    if (categoryId == null) {
      _showMessage('分类缺少 ID，不能删除');
      return;
    }
    if (isDefault) {
      _showMessage('系统预设分类不能删除');
      return;
    }
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('删除分类'),
        content: Text('确定删除「${_categoryName(category)}」吗？'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('取消'),
          ),
          TextButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('删除'),
          ),
        ],
      ),
    );
    if (confirmed != true || _deleting) return;
    setState(() => _deleting = true);
    try {
      await widget.repository.deleteCostCategory(categoryId);
      _reload();
      _showMessage('分类已删除');
    } catch (_) {
      _showMessage('删除分类失败');
    } finally {
      if (mounted) setState(() => _deleting = false);
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
      title: '分类管理',
      trailingIcon: LucideIcons.plus,
      trailingOnTap: _showCreateSheet,
      bottomBar: BottomActions(
        primaryLabel: '新增分类',
        secondaryLabel: '返回',
        onPrimary: _showCreateSheet,
        onSecondary: () => Navigator.of(context).maybePop(),
        showTabs: false,
      ),
      children: [
        _CategoryTypeSwitch(
          value: _recordType,
          onChanged: (value) => setState(() => _recordType = value),
        ),
        FutureBuilder<PageResult<ApiRecord>>(
          future: _categoriesFuture,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return const _CategoryStateCard(
                icon: LucideIcons.loaderCircle,
                text: '正在加载分类',
              );
            }
            if (snapshot.hasError) {
              return const _CategoryStateCard(
                icon: LucideIcons.circleAlert,
                text: '分类加载失败，请稍后再试',
              );
            }
            final categories = (snapshot.data?.items ?? const <ApiRecord>[])
                .where((item) => '${item.json['type']}' == _recordType)
                .toList();
            if (categories.isEmpty) {
              return const _CategoryStateCard(
                icon: LucideIcons.tags,
                text: '暂无分类，先新增一个常用分类。',
              );
            }
            return _CategoryListCard(
              categories: categories,
              onDelete: _deleteCategory,
            );
          },
        ),
        const _CategoryTipCard(),
      ],
    );
  }
}

class _CategoryTypeSwitch extends StatelessWidget {
  const _CategoryTypeSwitch({
    required this.value,
    required this.onChanged,
  });

  final String value;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    return BusinessCard(
      child: Column(
        children: [
          BusinessCardHeader(
            title: '分类类型',
            icon: LucideIcons.tags,
            trailing: Text(
              value == 'income' ? '收入' : '支出',
              style: AppTextStyles.small.copyWith(
                color: AppColors.blue,
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
            child: SegmentedButton<String>(
              segments: const [
                ButtonSegment(
                  value: 'cost',
                  label: Text('支出'),
                  icon: Icon(LucideIcons.arrowUpRight, size: 18),
                ),
                ButtonSegment(
                  value: 'income',
                  label: Text('收入'),
                  icon: Icon(LucideIcons.arrowDownLeft, size: 18),
                ),
              ],
              selected: {value},
              showSelectedIcon: false,
              onSelectionChanged: (values) => onChanged(values.first),
            ),
          ),
        ],
      ),
    );
  }
}

class _CreateCategorySheet extends StatefulWidget {
  const _CreateCategorySheet({
    required this.repository,
    required this.recordType,
  });

  final BusinessRepository repository;
  final String recordType;

  @override
  State<_CreateCategorySheet> createState() => _CreateCategorySheetState();
}

class _CreateCategorySheetState extends State<_CreateCategorySheet> {
  final _nameController = TextEditingController();
  bool _saving = false;

  @override
  void dispose() {
    _nameController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final name = _nameController.text.trim();
    if (name.isEmpty || _saving) return;
    setState(() => _saving = true);
    try {
      await widget.repository.createCostCategory({
        'name': name,
        'type': widget.recordType,
        'icon': widget.recordType == 'income' ? 'hand-coins' : 'leaf',
        'sort_order': 0,
      });
      if (mounted) Navigator.of(context).pop(true);
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context)
          ..hideCurrentSnackBar()
          ..showSnackBar(const SnackBar(content: Text('新增分类失败')));
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      top: false,
      child: Padding(
        padding: EdgeInsets.only(
          bottom: MediaQuery.viewInsetsOf(context).bottom,
        ),
        child: Container(
          margin: const EdgeInsets.fromLTRB(12, 0, 12, 12),
          padding: const EdgeInsets.fromLTRB(16, 10, 16, 16),
          decoration: const BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.vertical(top: Radius.circular(26)),
            boxShadow: [
              BoxShadow(
                color: Color(0x1A10271D),
                blurRadius: 26,
                offset: Offset(0, -10),
              ),
            ],
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const _CategorySheetGrabber(),
              const SizedBox(height: 16),
              Text(
                widget.recordType == 'income' ? '新增收入分类' : '新增支出分类',
                style: AppTextStyles.sectionTitle.copyWith(
                  fontSize: 20,
                  height: 26 / 20,
                  fontWeight: FontWeight.w900,
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _nameController,
                autofocus: true,
                textInputAction: TextInputAction.done,
                onSubmitted: (_) => _submit(),
                decoration: InputDecoration(
                  hintText: '输入分类名称',
                  filled: true,
                  fillColor: AppColors.surface2,
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(14),
                    borderSide: BorderSide.none,
                  ),
                  contentPadding: const EdgeInsets.symmetric(
                    horizontal: 14,
                    vertical: 13,
                  ),
                ),
              ),
              const SizedBox(height: 16),
              SizedBox(
                height: 48,
                child: FilledButton(
                  onPressed: _saving ? null : _submit,
                  child: Text(_saving ? '保存中' : '保存分类'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _CategoryListCard extends StatelessWidget {
  const _CategoryListCard({
    required this.categories,
    required this.onDelete,
  });

  final List<ApiRecord> categories;
  final ValueChanged<ApiRecord> onDelete;

  @override
  Widget build(BuildContext context) {
    return BusinessCard(
      child: Column(
        children: [
          BusinessCardHeader(
            title: '分类列表',
            icon: LucideIcons.listTree,
            trailing: Text(
              '${categories.length} 个',
              style: AppTextStyles.small.copyWith(
                color: AppColors.muted,
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
          ListView.separated(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            itemCount: categories.length,
            separatorBuilder: (_, __) => const SizedBox(height: 10),
            itemBuilder: (context, index) {
              final category = categories[index];
              return _CategoryListTile(
                category: category,
                onDelete: () => onDelete(category),
              );
            },
          ),
        ],
      ),
    );
  }
}

class _CategoryListTile extends StatelessWidget {
  const _CategoryListTile({
    required this.category,
    required this.onDelete,
  });

  final ApiRecord category;
  final VoidCallback onDelete;

  @override
  Widget build(BuildContext context) {
    final isDefault = category.json['is_default'] as bool? ?? false;
    final accent = isDefault ? businessGreenDark : AppColors.blue;
    return Container(
      constraints: const BoxConstraints(minHeight: 64),
      padding: const EdgeInsets.fromLTRB(12, 10, 8, 10),
      decoration: BoxDecoration(
        color: AppColors.surface3,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.lineSoft),
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
            child: Icon(_categoryIcon('${category.json['icon'] ?? ''}'),
                color: accent, size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(
                  _categoryName(category),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppTextStyles.listTitle.copyWith(
                    fontSize: 16,
                    height: 22 / 16,
                    fontWeight: FontWeight.w900,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  isDefault ? '系统预设' : '自定义分类',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppTextStyles.small.copyWith(
                    color: AppColors.muted,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
            ),
          ),
          IconButton(
            tooltip: isDefault ? '系统预设分类不能删除' : '删除分类',
            onPressed: onDelete,
            icon: Icon(
              isDefault ? LucideIcons.lockKeyhole : LucideIcons.trash2,
              color: isDefault ? AppColors.subtle : AppColors.red,
              size: 20,
            ),
          ),
        ],
      ),
    );
  }
}

class _CategoryStateCard extends StatelessWidget {
  const _CategoryStateCard({
    required this.icon,
    required this.text,
  });

  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    return BusinessCard(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          children: [
            Icon(icon, color: AppColors.subtle, size: 28),
            const SizedBox(height: 10),
            Text(
              text,
              textAlign: TextAlign.center,
              style: AppTextStyles.body.copyWith(
                color: AppColors.muted,
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _CategoryTipCard extends StatelessWidget {
  const _CategoryTipCard();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.blueSoft,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.blue.withValues(alpha: 0.14)),
      ),
      child: Row(
        children: [
          const Icon(LucideIcons.info, color: AppColors.blue, size: 20),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              '常用分类在这里维护，记账时只需要选择分类，不用重复输入。',
              style: AppTextStyles.body.copyWith(
                color: AppColors.blueDark,
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

class _CategorySheetGrabber extends StatelessWidget {
  const _CategorySheetGrabber();

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

String _categoryName(ApiRecord category) {
  final value = category.json['name'];
  final text = '$value'.trim();
  if (value == null || text.isEmpty || text == 'null') return '未命名分类';
  return text;
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
