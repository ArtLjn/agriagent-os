# 全局日期筛选卡片 UI Spec

## Image

- Source image: `/Users/ljn/Documents/demo/explore/output/imagegen/current-app-design/global-calendar-filter-card.png`
- Canvas: `1024x2224px`
- Intended platform: mobile app modal bottom sheet

## Purpose

- A reusable date filter component for billing, records, reports, and future analytics pages.
- It should replace one-off date menus and expose the same range choices everywhere.

## Layout

- Overlay: dimmed page background behind a modal bottom sheet.
- Sheet: white surface, top corners 24px logical radius, drag handle centered.
- Header: title `日期筛选` left, close icon right.
- Quick ranges: 2 rows x 3 columns, labels `本月`, `上月`, `近7天`, `近30天`, `本年`, `全部时间`.
- Month header: previous chevron, center month title such as `2026年6月`, next chevron.
- Calendar: 7-column grid, weekday labels `一 二 三 四 五 六 日`, day cells with selected/range states.
- Footer: secondary outline button `重置`, primary gradient button `确认`.

## Design Tokens

- Background overlay: `#101828` at 32% opacity.
- Sheet surface: `#FFFFFF`.
- Primary: `#1473FF`.
- Primary soft: `#EAF3FF`.
- Text primary: `#101828`.
- Text muted: `#667085`.
- Border: `#E4EAF2`.
- Card radius: 24px top corners.
- Chip radius: 14px.
- Day cell size: 42px logical.
- Grid gap: 8px.

## Interaction

- Tapping a quick range updates the pending range and calendar highlight.
- `重置` returns to `本月`.
- `确认` closes the sheet and returns the selected range.
- Close icon dismisses without applying changes.
- Month chevrons switch visible calendar month.

## Current Implementation Scope

- Use this component first in `全部交易` date filtering.
- Supported range values in code: `本月`, `上月`, `近7天`, `近30天`, `本年`, `全部时间`.
- The calendar grid is visual and range-aware; individual date selection can be expanded later.
