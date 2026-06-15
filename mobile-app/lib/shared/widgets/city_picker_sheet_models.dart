part of 'city_picker_sheet.dart';

enum _PickerKind { province, city, area, search }

class _PickerItem {
  const _PickerItem._({
    required this.kind,
    required this.name,
    this.subtitle,
    this.province,
    this.city,
    this.area,
    this.search,
    this.provinceName,
    this.canDrillDown = false,
  });

  factory _PickerItem.province(ProvinceEntry province) => _PickerItem._(
        kind: _PickerKind.province,
        name: province.name,
        province: province,
        canDrillDown: true,
      );

  factory _PickerItem.city(CityEntry city, String provinceName) =>
      _PickerItem._(
        kind: _PickerKind.city,
        name: city.name,
        city: city,
        provinceName: provinceName,
        canDrillDown:
            !_municipalities.contains(provinceName) && city.areas.isNotEmpty,
      );

  factory _PickerItem.area(CityArea area) => _PickerItem._(
        kind: _PickerKind.area,
        name: area.name,
        area: area,
      );

  factory _PickerItem.search(_SearchCityItem item) => _PickerItem._(
        kind: _PickerKind.search,
        name: item.name,
        subtitle: '${item.provinceName} · ${item.cityName}',
        search: item,
      );

  final _PickerKind kind;
  final String name;
  final String? subtitle;
  final ProvinceEntry? province;
  final CityEntry? city;
  final CityArea? area;
  final _SearchCityItem? search;
  final String? provinceName;
  final bool canDrillDown;
}

class _SearchCityItem {
  const _SearchCityItem({
    required this.name,
    required this.provinceName,
    required this.cityName,
  });

  final String name;
  final String provinceName;
  final String cityName;
}

List<_SearchCityItem> _buildSearchIndex() {
  final items = <_SearchCityItem>[];
  for (final province in provinces) {
    for (final city in province.cities) {
      items.add(
        _SearchCityItem(
          name: city.name,
          provinceName: province.name,
          cityName: city.name,
        ),
      );
      for (final area in city.areas) {
        items.add(
          _SearchCityItem(
            name: area.name,
            provinceName: province.name,
            cityName: city.name,
          ),
        );
      }
    }
  }
  return items;
}

String _shortName(String name) {
  return name
      .replaceAll('特别行政区', '')
      .replaceAll('维吾尔自治区', '')
      .replaceAll('壮族自治区', '')
      .replaceAll('回族自治区', '')
      .replaceAll('自治区', '')
      .replaceAll('省', '')
      .replaceAll('市', '');
}
