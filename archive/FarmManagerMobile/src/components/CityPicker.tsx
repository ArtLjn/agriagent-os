import React, { useState, useMemo, useCallback } from "react";
import {
  View,
  Text,
  Modal,
  TouchableOpacity,
  ScrollView,
  TextInput,
  StyleSheet,
} from "react-native";
import { colors } from "../theme/colors";
import { spacing, fontSize, borderRadius } from "../theme/spacing";
import { PROVINCES, type Province, type City, type Area } from "../data/cities";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";

type PickerLevel = "province" | "city" | "area";

interface CityPickerProps {
  visible: boolean;
  selectedCity: string;
  onSelect: (city: { name: string; lat: number; lon: number }) => void;
  onClose: () => void;
}

const municipalities = new Set(["北京市", "上海市", "天津市", "重庆市"]);

export const CityPicker: React.FC<CityPickerProps> = ({
  visible,
  selectedCity,
  onSelect,
  onClose,
}) => {
  const [level, setLevel] = useState<PickerLevel>("province");
  const [selectedProvince, setSelectedProvince] = useState<Province | null>(
    null
  );
  const [selectedCityData, setSelectedCityData] = useState<City | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  const reset = useCallback(() => {
    setLevel("province");
    setSelectedProvince(null);
    setSelectedCityData(null);
    setSearchQuery("");
  }, []);

  const handleClose = useCallback(() => {
    reset();
    onClose();
  }, [reset, onClose]);

  // Build flat search index for quick lookup
  const searchIndex = useMemo(() => {
    const index: Array<{
      name: string;
      province: string;
      city: string;
      lat: number;
      lon: number;
      type: "province" | "city" | "area";
    }> = [];
    for (const p of PROVINCES) {
      for (const c of p.cities) {
        for (const a of c.areas) {
          index.push({
            name: a.name,
            province: p.name,
            city: c.name,
            lat: a.lat,
            lon: a.lon,
            type: "area",
          });
        }
        index.push({
          name: c.name,
          province: p.name,
          city: c.name,
          lat: c.lat,
          lon: c.lon,
          type: municipalities.has(p.name) ? "area" : "city",
        });
      }
    }
    return index;
  }, []);

  const filteredItems = useMemo(() => {
    if (!searchQuery.trim()) {
      if (level === "province") {
        return PROVINCES.map((p) => ({ type: "province" as const, data: p }));
      }
      if (level === "city" && selectedProvince) {
        return selectedProvince.cities.map((c) => ({
          type: "city" as const,
          data: c,
          provinceName: selectedProvince.name,
        }));
      }
      if (level === "area" && selectedCityData) {
        return selectedCityData.areas.map((a) => ({
          type: "area" as const,
          data: a,
          cityName: selectedCityData.name,
        }));
      }
      return [];
    }

    // Search mode: search across all levels
    const q = searchQuery.trim().toLowerCase();
    const results = searchIndex
      .filter((item) => item.name.toLowerCase().includes(q))
      .slice(0, 50);

    return results.map((item) => ({
      type: item.type as PickerLevel,
      data: item,
      searchResult: true,
    }));
  }, [searchQuery, level, selectedProvince, selectedCityData, searchIndex]);

  const handleSelectProvince = (province: Province) => {
    setSelectedProvince(province);
    setSearchQuery("");

    if (municipalities.has(province.name)) {
      // For municipalities, cities are districts — go directly to area-like selection
      setLevel("city");
    } else {
      setLevel("city");
    }
  };

  const handleSelectCity = (city: City, provinceName: string) => {
    if (municipalities.has(provinceName)) {
      // Municipality district selected
      onSelect({ name: city.name, lat: city.lat, lon: city.lon });
      handleClose();
      return;
    }

    if (city.areas.length === 0) {
      // City with no districts (e.g., some special admin regions)
      onSelect({ name: city.name, lat: city.lat, lon: city.lon });
      handleClose();
      return;
    }

    setSelectedCityData(city);
    setSearchQuery("");
    setLevel("area");
  };

  const handleSelectArea = (area: Area) => {
    onSelect({ name: area.name, lat: area.lat, lon: area.lon });
    handleClose();
  };

  const handleBack = () => {
    if (level === "area") {
      setLevel("city");
      setSelectedCityData(null);
      setSearchQuery("");
    } else if (level === "city") {
      setLevel("province");
      setSelectedProvince(null);
      setSearchQuery("");
    }
  };

  const getTitle = () => {
    if (searchQuery.trim()) return "搜索结果";
    if (level === "province") return "选择省份";
    if (level === "city") {
      if (selectedProvince && municipalities.has(selectedProvince.name)) {
        return `选择${selectedProvince.name.replace("市", "")}市区`;
      }
      return selectedProvince ? selectedProvince.name : "选择城市";
    }
    return selectedCityData ? selectedCityData.name : "选择区县";
  };

  const canGoBack = level !== "province" && !searchQuery.trim();

  return (
    <Modal
      visible={visible}
      transparent
      animationType="slide"
      onRequestClose={handleClose}
    >
      <View style={styles.overlay}>
        <View style={styles.sheet}>
          {/* Header */}
          <View style={styles.header}>
            {canGoBack ? (
              <TouchableOpacity onPress={handleBack} activeOpacity={0.7}>
                <Icon name="chevron-left" size={24} color={colors.primary} />
              </TouchableOpacity>
            ) : (
              <View style={styles.headerPlaceholder} />
            )}
            <Text style={styles.title}>{getTitle()}</Text>
            <TouchableOpacity onPress={handleClose} activeOpacity={0.7}>
              <Icon name="close" size={24} color={colors.textSecondary} />
            </TouchableOpacity>
          </View>

          {/* Search */}
          <View style={styles.searchBox}>
            <Icon name="magnify" size={18} color={colors.textTertiary} />
            <TextInput
              style={styles.searchInput}
              placeholder="搜索城市或区县"
              placeholderTextColor={colors.textTertiary}
              value={searchQuery}
              onChangeText={setSearchQuery}
              autoCorrect={false}
            />
            {searchQuery.length > 0 && (
              <TouchableOpacity onPress={() => setSearchQuery("")}>
                <Icon
                  name="close-circle"
                  size={18}
                  color={colors.textTertiary}
                />
              </TouchableOpacity>
            )}
          </View>

          {/* Breadcrumb */}
          {!searchQuery.trim() && level !== "province" && (
            <View style={styles.breadcrumb}>
              <TouchableOpacity
                onPress={() => {
                  setLevel("province");
                  setSelectedCityData(null);
                  setSearchQuery("");
                }}
              >
                <Text style={styles.breadcrumbText}>省份</Text>
              </TouchableOpacity>
              <Icon
                name="chevron-right"
                size={14}
                color={colors.textTertiary}
              />
              {selectedProvince && (
                <TouchableOpacity
                  onPress={() => {
                    setLevel("city");
                    setSelectedCityData(null);
                    setSearchQuery("");
                  }}
                >
                  <Text style={styles.breadcrumbText}>
                    {selectedProvince.name
                      .replace("市", "")
                      .replace("省", "")
                      .replace("自治区", "")}
                  </Text>
                </TouchableOpacity>
              )}
              {level === "area" && selectedCityData && (
                <>
                  <Icon
                    name="chevron-right"
                    size={14}
                    color={colors.textTertiary}
                  />
                  <Text style={styles.breadcrumbTextActive}>
                    {selectedCityData.name.replace("市", "")}
                  </Text>
                </>
              )}
            </View>
          )}

          {/* List */}
          <ScrollView
            showsVerticalScrollIndicator={false}
            contentContainerStyle={styles.list}
            keyboardShouldPersistTaps="handled"
          >
            {filteredItems.map((item: any, index: number) => {
              let name: string;
              let isSelected = false;
              let onPress: () => void;
              let subtitle: string | undefined;

              if (item.type === "province") {
                name = item.data.name;
                isSelected = selectedProvince?.name === name;
                onPress = () => handleSelectProvince(item.data);
              } else if (item.type === "city") {
                name = item.data.name;
                isSelected = selectedCityData?.name === name;
                onPress = () =>
                  handleSelectCity(
                    item.data,
                    item.provinceName || selectedProvince?.name || ""
                  );
              } else if (item.searchResult) {
                name = item.data.name;
                isSelected = selectedCity === name;
                subtitle = `${item.data.province} · ${item.data.city}`;
                onPress = () => {
                  onSelect({
                    name: item.data.name,
                    lat: item.data.lat,
                    lon: item.data.lon,
                  });
                  handleClose();
                };
              } else {
                name = item.data.name;
                isSelected = selectedCity === name;
                onPress = () => handleSelectArea(item.data);
              }

              return (
                <TouchableOpacity
                  key={`${name}-${index}`}
                  style={[styles.item, isSelected && styles.itemActive]}
                  onPress={onPress}
                  activeOpacity={0.7}
                >
                  <View style={styles.itemLeft}>
                    <Text
                      style={[
                        styles.itemText,
                        isSelected && styles.itemTextActive,
                      ]}
                    >
                      {name}
                    </Text>
                    {subtitle && (
                      <Text style={styles.itemSubtitle}>{subtitle}</Text>
                    )}
                  </View>
                  <View style={styles.itemRight}>
                    {isSelected && (
                      <Icon name="check" size={20} color={colors.primary} />
                    )}
                    {!item.searchResult &&
                      item.type !== "area" &&
                      !municipalities.has(selectedProvince?.name || "") && (
                        <Icon
                          name="chevron-right"
                          size={18}
                          color={colors.textTertiary}
                        />
                      )}
                  </View>
                </TouchableOpacity>
              );
            })}

            {searchQuery.trim() && filteredItems.length === 0 && (
              <View style={styles.empty}>
                <Text style={styles.emptyText}>未找到匹配的城市</Text>
              </View>
            )}
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
};

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: colors.overlay,
    justifyContent: "flex-end",
  },
  sheet: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: borderRadius.xxl,
    borderTopRightRadius: borderRadius.xxl,
    paddingTop: spacing.lg,
    paddingBottom: spacing.xxl,
    maxHeight: "80%",
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.md,
  },
  headerPlaceholder: {
    width: 24,
  },
  title: {
    fontSize: fontSize.lg,
    fontWeight: "700",
    color: colors.text,
  },
  searchBox: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surfaceMuted,
    borderRadius: borderRadius.md,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
    paddingHorizontal: spacing.md,
    height: 44,
  },
  searchInput: {
    flex: 1,
    fontSize: fontSize.md,
    color: colors.text,
    marginLeft: spacing.sm,
    paddingVertical: 0,
  },
  breadcrumb: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.sm,
    gap: 4,
  },
  breadcrumbText: {
    fontSize: fontSize.sm,
    color: colors.primary,
  },
  breadcrumbTextActive: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
  },
  list: {
    paddingHorizontal: spacing.lg,
  },
  item: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.md,
    borderRadius: borderRadius.md,
    marginBottom: spacing.xs,
  },
  itemActive: {
    backgroundColor: colors.primaryMuted,
  },
  itemLeft: {
    flex: 1,
  },
  itemText: {
    fontSize: fontSize.md,
    color: colors.text,
  },
  itemTextActive: {
    fontWeight: "700",
    color: colors.primary,
  },
  itemSubtitle: {
    fontSize: fontSize.xs,
    color: colors.textTertiary,
    marginTop: 2,
  },
  itemRight: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  empty: {
    alignItems: "center",
    paddingVertical: spacing.xl,
  },
  emptyText: {
    fontSize: fontSize.md,
    color: colors.textTertiary,
  },
});
