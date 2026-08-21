import 'dart:math' as math;

import 'package:geolocator/geolocator.dart';

import 'cities.dart';
import 'location_service.dart';

class SystemLocationService implements LocationService {
  static const _maxMatchDistanceKm = 180.0;

  @override
  Future<FarmLocationSuggestion?> requestCurrentFarmLocation() async {
    final enabled = await Geolocator.isLocationServiceEnabled();
    if (!enabled) return null;

    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }
    if (permission == LocationPermission.denied ||
        permission == LocationPermission.deniedForever) {
      return null;
    }

    final position = await Geolocator.getCurrentPosition(
      locationSettings: const LocationSettings(
        accuracy: LocationAccuracy.low,
        timeLimit: Duration(seconds: 8),
      ),
    );
    final city = nearestSupportedCity(
      latitude: position.latitude,
      longitude: position.longitude,
    );
    if (city == null) return null;
    return FarmLocationSuggestion(
      city: city,
      latitude: position.latitude,
      longitude: position.longitude,
    );
  }
}

String? nearestSupportedCity({
  required double latitude,
  required double longitude,
}) {
  _CityCenter? nearest;
  var distance = double.infinity;
  for (final city in _supportedCityCenters) {
    final current = _distanceKm(
      latitude,
      longitude,
      city.latitude,
      city.longitude,
    );
    if (current < distance) {
      nearest = city;
      distance = current;
    }
  }
  if (nearest == null || distance > SystemLocationService._maxMatchDistanceKm) {
    return null;
  }
  return nearest.name;
}

double _distanceKm(
  double lat1,
  double lon1,
  double lat2,
  double lon2,
) {
  const earthRadiusKm = 6371.0;
  final dLat = _radians(lat2 - lat1);
  final dLon = _radians(lon2 - lon1);
  final a = math.sin(dLat / 2) * math.sin(dLat / 2) +
      math.cos(_radians(lat1)) *
          math.cos(_radians(lat2)) *
          math.sin(dLon / 2) *
          math.sin(dLon / 2);
  final c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a));
  return earthRadiusKm * c;
}

double _radians(double degree) => degree * math.pi / 180;

class _CityCenter {
  const _CityCenter(this.name, this.latitude, this.longitude);

  final String name;
  final double latitude;
  final double longitude;
}

const _cityCenters = [
  _CityCenter('睢宁县', 33.9127, 117.9411),
  _CityCenter('邳州市', 34.3142, 117.9586),
  _CityCenter('徐州市', 34.2044, 117.2858),
  _CityCenter('宿迁市', 33.963, 118.275),
  _CityCenter('连云港市', 34.5967, 119.2216),
  _CityCenter('临沂市', 35.1047, 118.3564),
  _CityCenter('济宁市', 35.4149, 116.5872),
  _CityCenter('寿光市', 36.8571, 118.7907),
  _CityCenter('南京市', 32.0603, 118.7969),
  _CityCenter('苏州市', 31.2989, 120.5853),
  _CityCenter('合肥市', 31.8206, 117.2272),
  _CityCenter('郑州市', 34.7466, 113.6254),
  _CityCenter('武汉市', 30.5928, 114.3055),
  _CityCenter('成都市', 30.5728, 104.0668),
  _CityCenter('昆明市', 25.0389, 102.7183),
  _CityCenter('广州市', 23.1291, 113.2644),
  _CityCenter('南宁市', 22.817, 108.3669),
  _CityCenter('海口市', 20.0442, 110.1999),
];

List<_CityCenter> get _supportedCityCenters => [
      ..._cityCenters,
      for (final province in provinces)
        for (final city in province.cities)
          _CityCenter(city.name, city.latitude, city.longitude),
    ];
