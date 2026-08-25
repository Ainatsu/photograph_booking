# Photographer Booking Mobile Design System

Updated: 2026-08-15

This document is the source of truth for the Vue + Ionic + Capacitor mobile app. It follows `docs/apple_design_SKILL.md`: content-first composition, direct response, spatial continuity, system typography, restrained materials, predictable navigation, and inclusive interaction.

## Product Direction

- Product: consumer photographer discovery, booking, portfolio, messaging, and publishing app.
- Desired feeling: calm, capable, trustworthy, visually rich through photography rather than decorative UI.
- Platform behavior: iOS-first Ionic mode with Android-safe touch targets and standard system navigation.
- Primary content: photographs, creator identity, package facts, project status, messages, and clear actions.

## Core Principles

1. Respond on pointer-down. Tappable elements visibly respond within 100ms.
2. Keep motion interruptible. Never block input while a transition runs.
3. Preserve spatial consistency. Forward/back and open/close transitions use matching paths.
4. Use materials to communicate hierarchy. Blur belongs to floating navigation, sheets, and popovers only.
5. Keep photography dominant. UI surfaces remain neutral and avoid ornamental gradients or color fields.
6. Show one primary action per screen. Secondary and destructive actions are visually subordinate.
7. Respect safe areas, Dynamic Type, reduced motion, reduced transparency, and increased contrast.

## Tokens

Implementation lives in `mobile-app/src/theme/tokens.css`.

### Color

| Role | Light | Dark |
| --- | --- | --- |
| App background | `#F2F2F7` | `#000000` |
| Primary surface | `#FFFFFF` | `#1C1C1E` |
| Secondary surface | `#F2F2F7` | `#2C2C2E` |
| Primary text | `#1C1C1E` | `#F5F5F7` |
| Secondary text | `#5A5A60` | `#C7C7CC` |
| Action blue | `#0A67D0` | `#409CFF` |
| Destructive | `#D70015` | `#FF453A` |

- Use semantic variables only. Do not add screen-specific hex colors for standard states.
- Body text must meet 4.5:1 contrast; large text and large icons must meet 3:1.
- Color never acts as the only status signal.

### Typography

- Font stack: Apple system font, PingFang SC, Microsoft YaHei, system-ui.
- Body: 16px minimum, line-height 1.5 or greater.
- Labels: 12-14px with normal letter spacing.
- Navigation title: 17px, semibold.
- Section title: 20px, bold.
- Large title: 28-34px, tight leading, used only for true page hierarchy.
- Prices and counters use tabular figures.
- Layout must tolerate browser text scaling without clipping or overlap.

### Spacing And Shape

- Spacing follows a 4/8pt rhythm: 4, 8, 12, 16, 20, 24, 32, 40, 48.
- Minimum interactive target: 48x48px; visually smaller icons keep the full hit area.
- Standard radii: 8px compact, 12px controls, 16px cards, 22px sheets.
- Do not nest cards inside cards. Grouped sections can use separators instead.

## Navigation

- Bottom tab bar contains exactly five labeled top-level destinations.
- Selected tabs use action color and weight, not a raised container.
- Detail pages use a predictable back button in the top-left.
- Sticky top and bottom chrome use translucent material with content scrolling underneath.
- Deep pages keep a visible escape route and preserve back-stack state.
- Search remains reachable from primary content pages.

## Components

### Buttons

- Primary: solid action blue, white text, one per screen.
- Secondary: secondary surface with action-blue text.
- Destructive: danger-tinted surface with danger text, spatially separated.
- Icon-only: familiar Lucide symbol plus an accessible label.
- Press state: scale to roughly 0.97 and darken immediately without shifting layout.
- Disabled: semantic disabled state, no interaction, approximately 42% opacity.

### Forms

- Every field has a visible label; placeholder text is supplementary.
- Input height is at least 48px and uses the appropriate input type/inputmode.
- Validation occurs on blur or submit, and errors appear next to the field with a recovery path.
- Async submission disables the action and shows progress.
- Long publishing forms preserve drafts and warn before discarding unsaved changes.

### Cards And Lists

- Media cards prioritize the image; metadata is compact and scannable.
- Reserve image space with `aspect-ratio` to prevent layout shift.
- Lazy-load below-fold images.
- Use a single low elevation for standalone cards; grouped settings and facts use separators.
- Lists over roughly 50 complex items should be virtualized or progressively loaded.

### Sheets And Modals

- Modal tasks use a 48% scrim and a thick material foreground.
- Sheets enter from and dismiss toward the bottom, matching their source direction.
- Dismiss controls are always visible; unsaved work requires confirmation.
- Motion uses transform and opacity only. Reduced motion replaces movement with a short cross-fade.

## Motion

- Tap feedback: 80-100ms.
- Standard state transition: 180-300ms.
- Default motion is critically damped and has no decorative bounce.
- Bounce is reserved for momentum-driven gestures.
- User input can interrupt every transition.
- Animate only transform, opacity, and materialization properties that do not trigger layout.
- Haptics are reserved for meaningful commit, selection, success, and error events.

## Accessibility And Responsive Requirements

- Test at 375px, 768px, tablet portrait, and phone landscape.
- No horizontal page scroll; fixed chrome reserves safe-area-aware content insets.
- Focus rings remain visible for keyboard and switch users.
- Meaningful images have alt text; icon buttons have accessible names.
- Support `prefers-reduced-motion`, `prefers-reduced-transparency`, and `prefers-contrast`.
- Light and dark themes are independently checked for contrast and state clarity.

## Prohibited Patterns

- Neumorphism, heavy skeuomorphism, decorative gradients, or stacked translucent surfaces.
- Emoji used as structural icons.
- Marketing-style hero sections inside the operational app.
- Hover-only actions, tiny icon hit areas, hidden labels, or color-only status.
- Fixed-duration gesture animations that cannot be interrupted.
- Arbitrary z-index values, random spacing, random corner radii, or per-screen color palettes.
