import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../data/location/cities.dart';
import '../../data/location/city_models.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';

part 'city_picker_sheet_models.dart';

const _municipalities = {'北京市', '上海市', '天津市', '重庆市'};

class CityPickerResult {
  const CityPickerResult({
    required this.name,
    required this.latitude,
    required this.longitude,
  });

  final String name;
  final double latitude;
  final double longitude;
}

Future<CityPickerResult?> showCityPickerSheet({
  required BuildContext context,
  required String selectedCity,
  Future<CityPickerResult?> Function()? onUseCurrentLocation,
  Future<List<CityPickerResult>> Function(String query)? onSearchLocations,
}) {
  return showModalBottomSheet<CityPickerResult>(
    context: context,
    isScrollControlled: true,
    useSafeArea: true,
    backgroundColor: Colors.transparent,
    builder: (_) => _CityPickerSheet(
      selectedCity: selectedCity,
      onUseCurrentLocation: onUseCurrentLocation,
      onSearchLocations: onSearchLocations,
    ),
  );
}

enum _PickerLevel { province, city, area }

class _CityPickerSheet extends StatefulWidget {
  const _CityPickerSheet({
    required this.selectedCity,
    this.onUseCurrentLocation,
    this.onSearchLocations,
  });

  final String selectedCity;
  final Future<CityPickerResult?> Function()? onUseCurrentLocation;
  final Future<List<CityPickerResult>> Function(String query)? onSearchLocations;

  @override
  State<_CityPickerSheet> createState() => _CityPickerSheetState();
}

class _CityPickerSheetState extends State<_CityPickerSheet> {
  final TextEditingController _searchController = TextEditingController();
  late final List<_SearchCityItem> _searchIndex = _buildSearchIndex();
  List<CityPickerResult> _remoteSearchResults = const [];
  _PickerLevel _level = _PickerLevel.province;
  ProvinceEntry? _selectedProvince;
  CityEntry? _selectedCity;
  String _query = '';
  bool _locating = false;
  bool _searching = false;
  String? _message;

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final bottomInset = MediaQuery.viewInsetsOf(context).bottom;
    final items = _visibleItems();

    return Padding(
      padding: EdgeInsets.only(bottom: bottomInset),
      child: DecoratedBox(
        decoration: const BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
        ),
        child: ConstrainedBox(
          constraints: BoxConstraints(
            maxHeight: MediaQuery.sizeOf(context).height * 0.82,
          ),
          child: Column(
            children: [
              const SizedBox(height: 10),
              Container(
                width: 42,
                height: 4,
                decoration: BoxDecoration(
                  color: AppColors.line,
                  borderRadius: BorderRadius.circular(999),
                ),
              ),
              const SizedBox(height: 12),
              _buildHeader(),
              _buildSearchBox(),
              if (widget.onUseCurrentLocation != null) _buildRelocateButton(),
              if (_message != null) _buildMessage(),
              if (_query.trim().isEmpty && _level != _PickerLevel.province)
                _buildBreadcrumb(),
              Expanded(child: _buildList(items)),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildHeader() {
    final canGoBack = _query.trim().isEmpty && _level != _PickerLevel.province;
    return Padding(
      padding: const EdgeInsets.fromLTRB(18, 0, 14, 12),
      child: Row(
        children: [
          SizedBox(
            width: 44,
            height: 44,
            child: canGoBack
                ? IconButton(
                    tooltip: '返回上一级',
                    onPressed: _back,
                    icon: const Icon(LucideIcons.chevronLeft, size: 22),
                    color: AppColors.blue,
                  )
                : null,
          ),
          Expanded(
            child: Text(
              _title(),
              textAlign: TextAlign.center,
              style: AppTextStyles.dateTitle,
            ),
          ),
          SizedBox(
            width: 44,
            height: 44,
            child: IconButton(
              tooltip: '关闭',
              onPressed: () => Navigator.of(context).pop(),
              icon: const Icon(LucideIcons.x, size: 22),
              color: AppColors.subtle,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSearchBox() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(18, 0, 18, 12),
      child: Container(
        height: 46,
        padding: const EdgeInsets.symmetric(horizontal: 14),
        decoration: BoxDecoration(
          color: AppColors.surface2,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: AppColors.lineSoft),
        ),
        child: Row(
          children: [
            const Icon(LucideIcons.search, size: 18, color: AppColors.subtle),
            const SizedBox(width: 10),
            Expanded(
              child: TextField(
                controller: _searchController,
                decoration: InputDecoration(
                  border: InputBorder.none,
                  isDense: true,
                  hintText: '搜索城市或区县',
                  hintStyle: AppTextStyles.body.copyWith(
                    color: AppColors.subtle,
                  ),
                ),
                style: AppTextStyles.body.copyWith(fontSize: 15),
                textInputAction: TextInputAction.search,
                onChanged: _onSearchChanged,
              ),
            ),
            if (_query.isNotEmpty)
              IconButton(
                tooltip: '清除搜索',
                onPressed: () {
                  _searchController.clear();
                  setState(() {
                    _query = '';
                    _remoteSearchResults = const [];
                    _searching = false;
                  });
                },
                icon: const Icon(LucideIcons.circleX, size: 18),
                color: AppColors.subtle,
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildRelocateButton() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(18, 0, 18, 12),
      child: OutlinedButton.icon(
        onPressed: _locating ? null : _useCurrentLocation,
        icon: Icon(
          _locating ? LucideIcons.loaderCircle : LucideIcons.locateFixed,
          size: 17,
        ),
        label: Text(_locating ? '定位中...' : '重新定位'),
      ),
    );
  }

  Widget _buildMessage() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(22, 0, 22, 10),
      child: Align(
        alignment: Alignment.centerLeft,
        child: Text(
          _message!,
          style: AppTextStyles.small.copyWith(color: AppColors.red),
        ),
      ),
    );
  }

  Widget _buildBreadcrumb() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(22, 0, 22, 8),
      child: Row(
        children: [
          _BreadcrumbButton(label: '省份', onTap: _resetToProvince),
          const Icon(LucideIcons.chevronRight,
              size: 14, color: AppColors.subtle),
          if (_selectedProvince != null)
            _BreadcrumbButton(
              label: _shortName(_selectedProvince!.name),
              onTap: _resetToCity,
            ),
          if (_level == _PickerLevel.area && _selectedCity != null) ...[
            const Icon(
              LucideIcons.chevronRight,
              size: 14,
              color: AppColors.subtle,
            ),
            Text(_shortName(_selectedCity!.name), style: AppTextStyles.small),
          ],
        ],
      ),
    );
  }

  Widget _buildList(List<_PickerItem> items) {
    if (_query.trim().isNotEmpty && _searching && items.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_query.trim().isNotEmpty && items.isEmpty) {
      return Center(
        child: Text(
          '未找到匹配的城市',
          style: AppTextStyles.body.copyWith(color: AppColors.subtle),
        ),
      );
    }
    return ListView.separated(
      padding: const EdgeInsets.fromLTRB(18, 0, 18, 24),
      keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
      itemBuilder: (context, index) => _CityPickerRow(
        item: items[index],
        selectedCity: widget.selectedCity,
        onTap: _select,
      ),
      separatorBuilder: (_, __) => const SizedBox(height: 4),
      itemCount: items.length,
    );
  }

  List<_PickerItem> _visibleItems() {
    final query = _query.trim();
    if (query.isNotEmpty) {
      if (_remoteSearchResults.isNotEmpty) {
        return _remoteSearchResults
            .map(_SearchCityItem.fromResult)
            .map(_PickerItem.search)
            .toList(growable: false);
      }
      return _searchIndex
          .where((item) => item.name.contains(query))
          .take(50)
          .map(_PickerItem.search)
          .toList(growable: false);
    }
    if (_level == _PickerLevel.province) {
      return provinces.map(_PickerItem.province).toList(growable: false);
    }
    if (_level == _PickerLevel.city && _selectedProvince != null) {
      return _selectedProvince!.cities
          .map((city) => _PickerItem.city(city, _selectedProvince!.name))
          .toList(growable: false);
    }
    if (_level == _PickerLevel.area && _selectedCity != null) {
      return _selectedCity!.areas.map(_PickerItem.area).toList(growable: false);
    }
    return const [];
  }

  void _select(_PickerItem item) {
    switch (item.kind) {
      case _PickerKind.province:
        setState(() {
          _selectedProvince = item.province;
          _selectedCity = null;
          _level = _PickerLevel.city;
        });
      case _PickerKind.city:
        final city = item.city!;
        if (_municipalities.contains(item.provinceName) || city.areas.isEmpty) {
          Navigator.of(context).pop(city.toPickerResult());
          return;
        }
        setState(() {
          _selectedCity = city;
          _level = _PickerLevel.area;
        });
      case _PickerKind.area:
        Navigator.of(context).pop(item.area!.toPickerResult());
      case _PickerKind.search:
        Navigator.of(context).pop(item.search!.toPickerResult());
    }
  }

  void _back() {
    if (_level == _PickerLevel.area) {
      setState(() {
        _level = _PickerLevel.city;
        _selectedCity = null;
      });
      return;
    }
    if (_level == _PickerLevel.city) _resetToProvince();
  }

  Future<void> _useCurrentLocation() async {
    final callback = widget.onUseCurrentLocation;
    if (callback == null || _locating) return;
    setState(() {
      _locating = true;
      _message = null;
    });
    final location = await callback();
    if (!mounted) return;
    if (location == null) {
      setState(() {
        _locating = false;
        _message = '无法获取当前位置';
      });
      return;
    }
    Navigator.of(context).pop(location);
  }

  Future<void> _onSearchChanged(String value) async {
    final query = value.trim();
    setState(() {
      _query = value;
      _remoteSearchResults = const [];
    });
    final search = widget.onSearchLocations;
    if (search == null || query.isEmpty) return;

    setState(() => _searching = true);
    try {
      final results = await search(query);
      if (!mounted || _query.trim() != query) return;
      setState(() {
        _remoteSearchResults = results;
        _searching = false;
      });
    } catch (_) {
      if (!mounted || _query.trim() != query) return;
      setState(() => _searching = false);
    }
  }

  void _resetToProvince() {
    setState(() {
      _level = _PickerLevel.province;
      _selectedProvince = null;
      _selectedCity = null;
    });
  }

  void _resetToCity() {
    setState(() {
      _level = _PickerLevel.city;
      _selectedCity = null;
    });
  }

  String _title() {
    if (_query.trim().isNotEmpty) return '搜索结果';
    if (_level == _PickerLevel.province) return '选择省份';
    if (_level == _PickerLevel.city) {
      final province = _selectedProvince;
      if (province == null) return '选择城市';
      if (_municipalities.contains(province.name)) {
        return '选择${province.name.replaceAll('市', '')}市区';
      }
      return province.name;
    }
    return _selectedCity?.name ?? '选择区县';
  }
}

class _CityPickerRow extends StatelessWidget {
  const _CityPickerRow({
    required this.item,
    required this.selectedCity,
    required this.onTap,
  });

  final _PickerItem item;
  final String selectedCity;
  final ValueChanged<_PickerItem> onTap;

  @override
  Widget build(BuildContext context) {
    final isSelected = selectedCity == item.name;
    return Material(
      color: isSelected ? AppColors.blueSoft : Colors.transparent,
      borderRadius: BorderRadius.circular(14),
      child: InkWell(
        borderRadius: BorderRadius.circular(14),
        onTap: () => onTap(item),
        child: ConstrainedBox(
          constraints: const BoxConstraints(minHeight: 52),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
            child: Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(
                        item.name,
                        style: AppTextStyles.body.copyWith(
                          color: isSelected ? AppColors.blue : AppColors.ink,
                          fontWeight:
                              isSelected ? FontWeight.w800 : FontWeight.w600,
                        ),
                      ),
                      if (item.subtitle != null) ...[
                        const SizedBox(height: 2),
                        Text(item.subtitle!, style: AppTextStyles.small),
                      ],
                    ],
                  ),
                ),
                if (isSelected)
                  const Icon(LucideIcons.check, size: 19, color: AppColors.blue)
                else if (item.canDrillDown)
                  const Icon(
                    LucideIcons.chevronRight,
                    size: 18,
                    color: AppColors.subtle,
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _BreadcrumbButton extends StatelessWidget {
  const _BreadcrumbButton({required this.label, required this.onTap});

  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return TextButton(
      style: TextButton.styleFrom(
        visualDensity: VisualDensity.compact,
        padding: const EdgeInsets.symmetric(horizontal: 4),
        minimumSize: const Size(0, 32),
      ),
      onPressed: onTap,
      child: Text(label),
    );
  }
}
