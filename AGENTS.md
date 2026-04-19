# AGENTS.md

This file defines the UI and implementation rules for the NYC Airbnb Dash dashboard in this project. Any future edits should preserve these decisions unless the user explicitly asks to change them.

## Product Goal

Build and maintain a polished Airbnb analytics dashboard that feels like a real product rather than a class demo.

The dashboard should stay:
- clean
- light
- spacious
- readable at 100% browser zoom
- visually consistent across future edits

## Core Design Language

The visual style must follow these principles:
- modern, minimal, and professional
- neutral light background
- soft card surfaces with rounded corners
- subtle shadows only
- strong visual hierarchy
- low visual clutter

Avoid:
- heavy borders
- overly saturated decoration
- cramped chart layouts
- inconsistent spacing between sections
- random font-size jumps between components

## Layout Rules

The page structure should stay in this order:
1. Header
2. Filter sidebar
3. Main chart area
4. Bottom time-series section

The intended chart balance is:
- left column: insight banner, KPI cards, map
- right column: scatter chart, bar chart
- bottom row: monthly trend line chart spanning full width

Do not move the line chart back into the right column unless the user explicitly requests it.

## Filter Rules

These filter rules are mandatory:

- All filter labels must be horizontally centered.
- All dropdown placeholder text must be centered.
- All dropdown selected text must be centered.
- All multi-select selected chips should remain visually centered inside the control.
- All slider tick labels must be centered under their tick marks.
- Filter alignment must remain centered even if text or options change later.

If a future edit breaks centered alignment in any filter, that is considered a regression.

## Sidebar Rules

The filter sidebar should remain:
- clean
- vertically structured
- visually lighter than the main content cards

The sidebar should not repeat information already shown clearly elsewhere in the header unless the user asks for duplication.

## Card Rules

All cards should follow these rules:
- rounded corners
- subtle shadow
- consistent internal padding
- clear title
- optional short description

Card heights should feel intentional. Avoid cards that look excessively tall relative to their content.

## Map Rules

The map is the main visual anchor.

The map must:
- feel dominant in the layout
- visually balance the right-side scatter and bar section
- fill its card naturally without awkward inner blank space
- preserve clear hover information

If map size is changed:
- update both the card height and the figure height together
- avoid a situation where the card is much taller than the map itself

## Scatter and Bar Rules

The scatter and bar chart cards should:
- feel compact
- stay visually balanced with each other
- not dominate the page over the map

When resizing these cards:
- adjust both cards together unless there is a clear reason not to
- preserve readability of labels and axes

## Time Series Rules

The line chart should stay:
- full-width
- lighter than the map visually
- compact but readable

Preferred style:
- thinner line
- smaller markers
- restrained grid styling

## Data Presentation Rules

Unknown or placeholder categories should not appear in user-facing charts when they reduce clarity.

Current expectation:
- rows with unknown neighborhood should be excluded in preprocessing
- rows with unknown room type should be excluded in preprocessing

If future datasets introduce placeholder values again, remove them during preprocessing rather than only hiding them in the chart layer.

## CSS Rules

When editing CSS:
- prefer updating existing dashboard classes instead of adding many one-off classes
- keep spacing values consistent across similar components
- avoid conflicting height systems between cards and Plotly graphs

If a chart disappears after a layout change, check first:
1. card min-height
2. graph container height
3. Plotly figure height
4. flex and grid interactions

## Dash and Plotly Rules

When editing charts:
- keep `dcc.Graph` sized intentionally
- ensure figure height and container height agree
- avoid unnecessary mode bar clutter unless needed for the task
- preserve hover clarity and readable labels

## Regression Checklist

Before finishing any dashboard layout edit, verify:
- filter labels are centered
- dropdown text is centered
- slider tick labels are centered
- map is visible
- scatter chart is visible
- bar chart is visible
- line chart is visible
- no large empty white blocks appear inside chart cards
- no duplicate informational labels appear unless intended
- the page still looks balanced at normal browser zoom

## Change Policy

If a request conflicts with these rules:
- follow the user request
- but keep the rest of the dashboard consistent

If the user gives a new visual preference that should become permanent, update this file as part of the change.
