import '../api/api_client.dart';

class LocationRepository {
  LocationRepository(this.client);

  final ApiClient client;

  Future<List<LocationOption>> searchLocations(
    String query, {
    int limit = 20,
  }) async {
    final data = await client.getMap('/locations/search', query: {
      'q': query,
      'limit': limit,
    });
    final items = ApiClient.asList(data['items']);
    return items
        .map((item) => LocationOption.fromJson(
              Map<String, dynamic>.from(item as Map),
            ))
        .toList();
  }
}

class LocationOption {
  const LocationOption({
    required this.name,
    required this.latitude,
    required this.longitude,
    this.displayName,
    this.coordinateSource,
  });

  factory LocationOption.fromJson(Map<String, dynamic> json) {
    return LocationOption(
      name: (json['display_name'] ?? json['name'] ?? '').toString(),
      displayName: json['display_name']?.toString(),
      latitude: (json['lat'] as num).toDouble(),
      longitude: (json['lon'] as num).toDouble(),
      coordinateSource: json['coordinate_source']?.toString(),
    );
  }

  final String name;
  final String? displayName;
  final double latitude;
  final double longitude;
  final String? coordinateSource;
}
