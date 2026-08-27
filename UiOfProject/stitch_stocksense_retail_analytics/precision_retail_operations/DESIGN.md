---
name: Precision Retail Operations
colors:
  surface: '#f8f9ff'
  surface-dim: '#d6dae5'
  surface-bright: '#f8f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#eff3ff'
  surface-container: '#eaeef9'
  surface-container-high: '#e4e8f3'
  surface-container-highest: '#dee2ee'
  on-surface: '#171c24'
  on-surface-variant: '#404848'
  inverse-surface: '#2c3139'
  inverse-on-surface: '#edf1fc'
  outline: '#707978'
  outline-variant: '#c0c8c7'
  surface-tint: '#386664'
  primary: '#003735'
  on-primary: '#ffffff'
  primary-container: '#1f4e4c'
  on-primary-container: '#8fbebb'
  inverse-primary: '#a0cfcc'
  secondary: '#2c6292'
  on-secondary: '#ffffff'
  secondary-container: '#96c8fe'
  on-secondary-container: '#195483'
  tertiary: '#4c2617'
  on-tertiary: '#ffffff'
  tertiary-container: '#663c2b'
  on-tertiary-container: '#e2a891'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#bcece8'
  primary-fixed-dim: '#a0cfcc'
  on-primary-fixed: '#00201f'
  on-primary-fixed-variant: '#1f4e4c'
  secondary-fixed: '#d0e4ff'
  secondary-fixed-dim: '#9bcbff'
  on-secondary-fixed: '#001d34'
  on-secondary-fixed-variant: '#054a78'
  tertiary-fixed: '#ffdbce'
  tertiary-fixed-dim: '#f5b9a2'
  on-tertiary-fixed: '#321205'
  on-tertiary-fixed-variant: '#663c2b'
  background: '#f8f9ff'
  on-background: '#171c24'
  surface-variant: '#dee2ee'
typography:
  h1:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.02em
  h2:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.01em
  h3:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  data-tabular:
    fontFamily: JetBrains Mono
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
  label-caps:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.05em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  container-max: 1200px
  sidebar-width: 240px
  gutter-default: 24px
  gutter-tight: 16px
  padding-card: 20px
  stack-sm: 8px
  stack-md: 16px
---

## Brand & Style
The design system is engineered for high-utility, data-dense enterprise environments. It prioritizes clarity and information density over decorative flair, adopting a **Modern Corporate** aesthetic with a focus on systematic precision. 

The visual narrative is built on stability and analytical rigor. By utilizing a high-contrast neutral base with deep professional accents, the interface reduces cognitive load for users managing complex inventory lifecycles. Every element is designed to feel functional, robust, and dependable, ensuring that critical alerts for stock levels are immediately actionable without visual distraction.

## Colors
The palette is rooted in professional "Deep Teal" and "Muted Steel Blue" to establish authority. Backgrounds use a light grey to reduce screen glare during long shifts, while surfaces remain white to create a clear "layer" for data visualization.

- **Primary Brand Accent:** Use for primary actions, active navigation states, and key headers.
- **Surface Borders:** Use `#E3E6EA` for all structural divisions to maintain a crisp, organized grid.
- **Semantic Logic:** 
  - **Healthy Stock:** Forest Green for positive status.
  - **Low Stock:** Muted Gold for caution.
  - **Stock-out Risk:** Muted Brick Red for critical attention.
  - **Overstock:** Muted Plum for supply chain inefficiency.

## Typography
The system uses **Inter** for all UI copy to ensure maximum legibility across densities. 

- **Data Tables:** All numerical values must use **JetBrains Mono** to ensure columns align perfectly for easy vertical scanning of figures.
- **Headings:** Semi-bold weight is mandatory for clear hierarchy against dense data sets.
- **Body:** The standard size is 14px to allow for high information density without sacrificing readability.
- **Labels:** Small, uppercase labels with increased tracking should be used for table headers and category tags.

## Layout & Spacing
This design system utilizes a **Fixed-Fluid Hybrid Grid**. The layout is anchored by a persistent left sidebar (240px) and a main content area that expands up to a 1200px maximum width to prevent excessively long line lengths on ultra-wide monitors.

- **Grid:** A 12-column system is used for dashboard layouts.
- **Gutters:** Use 24px gutters for primary dashboard modules; reduce to 16px for secondary toolbars or internal card layouts.
- **Responsive:** On tablet widths, the sidebar collapses into an icon-only rail or a hidden drawer. Content reflows from a 3-column card layout to a single column on mobile.

## Elevation & Depth
Depth is communicated through **Tonal Layers** and **Low-Contrast Outlines** rather than heavy shadows.

- **Level 0 (Background):** `#F6F7F9` – The canvas.
- **Level 1 (Cards/Surface):** White background with a 1px solid border of `#E3E6EA`.
- **Level 2 (Active/Hover):** A very subtle shadow (`0px 4px 6px -1px rgba(0, 0, 0, 0.05)`) is applied only to interactive cards or focused elements to indicate clickability.
- **Overlays:** Modals use a semi-transparent dark overlay (`rgba(26, 31, 39, 0.5)`) to maintain focus on the task at hand.

## Shapes
The shape language is professional and balanced. 

- **Cards & Input Fields:** Use a 8px (0.5rem) radius to soften the technical nature of the data.
- **Buttons:** Match the 8px radius for consistency.
- **Badges/Pills:** Use a fully rounded (Pill) shape to differentiate status indicators from buttons or input fields, making them instantly recognizable as "read-only" data points.

## Components
- **Sidebar:** Fixed left-hand placement. Active states use a 4px left-border accent in Deep Teal and a 10% opacity Deep Teal background tint for the list item.
- **Cards:** Must include a 1px border. Titles should be H3 (18px Semi-bold) with a bottom border separating the header from the content.
- **Badges:** Pill-shaped. Use semantic colors for text and a 15% opacity version of the same color for the background to ensure high legibility.
- **Buttons:** 
  - *Primary:* Deep Teal background, white text.
  - *Secondary:* Ghost style with 1px `#E3E6EA` border and `#1A1F27` text.
- **Data Tables:** Row heights should be a compact 40px. Zebra striping is used (alternating with `#F6F7F9`) to assist in horizontal eye tracking.
- **Charts:** Use the specified colorblind-safe palette. Ensure chart axes use 12px `body-sm` text in Secondary Grey.
- **Input Fields:** 1px border `#E3E6EA`, 8px padding, 14px text. Focus state changes border to Deep Teal.