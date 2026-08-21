class FarmLocationSuggestion {
  const FarmLocationSuggestion({
    required this.city,
    this.latitude,
    this.longitude,
  });

  final String city;
  final double? latitude;
  final double? longitude;
}

abstract class LocationService {
  Future<FarmLocationSuggestion?> requestCurrentFarmLocation();
}
