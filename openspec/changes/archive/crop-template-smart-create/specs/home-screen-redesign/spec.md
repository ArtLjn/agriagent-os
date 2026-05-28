## MODIFIED Requirements

### Requirement: 快捷功能区
The quick actions SHALL be displayed as horizontally scrollable cards, not a grid. The set of available quick actions SHALL be limited to features with dedicated screens.

#### Scenario: Quick action cards
- **WHEN** quick actions are displayed
- **THEN** they MUST be in a horizontal scrollable row
- **AND** each card MUST have a low-saturation background color

#### Scenario: Planting card color
- **WHEN** the planting planning card is rendered
- **THEN** its background MUST be `#EDFDF3`
- **AND** tapping it MUST navigate to the cycle creation screen

#### Scenario: Crop template card
- **WHEN** the crop template card is rendered
- **THEN** its background MUST be `#FFF8E8`
- **AND** its icon MUST be a seedling or plant icon
- **AND** tapping it MUST navigate to the crop template creation screen

#### Scenario: Removed placeholder actions
- **WHEN** the home screen is displayed
- **THEN** it MUST NOT show the farming reminder, weather trend, or pest identification quick action buttons
- **AND** these features MUST remain accessible through the AI chat interface

## REMOVED Requirements

### Requirement: 农事提醒快捷按钮
**Reason**: This quick action was a placeholder that navigated to the generic AI chat screen. It is being removed to clean up the home screen.
**Migration**: Users can still access farming reminders through the AI chat screen.

### Requirement: 天气趋势快捷按钮
**Reason**: This quick action was a placeholder that navigated to the generic AI chat screen. Weather information is already prominently displayed in the weather card above.
**Migration**: Users can view weather details in the weather card or ask the AI assistant about weather.

### Requirement: 病虫害识别快捷按钮
**Reason**: This quick action was a placeholder that navigated to the generic AI chat screen. No dedicated pest identification feature exists yet.
**Migration**: Users can ask the AI assistant about pest and disease issues.
