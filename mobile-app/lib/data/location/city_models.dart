class CityArea {
  const CityArea({
    required this.name,
    required this.latitude,
    required this.longitude,
  });

  final String name;
  final double latitude;
  final double longitude;
}

class CityEntry {
  const CityEntry({
    required this.name,
    required this.latitude,
    required this.longitude,
    required this.areas,
  });

  final String name;
  final double latitude;
  final double longitude;
  final List<CityArea> areas;
}

class ProvinceEntry {
  const ProvinceEntry({
    required this.name,
    required this.cities,
  });

  final String name;
  final List<CityEntry> cities;
}
