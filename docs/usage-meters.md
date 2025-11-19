# Usage Meters

Usage components provide a consistent, accessible way to display remaining allowances without exposing raw numbers in the UI.

## Components
- `UsageMeter`: renders an individual progress bar with optional descriptions. When `disabled` it collapses to zero width and displays a "Coming soon" badge with a tooltip.
- `UsageGroup`: wraps a collection of meters with title/description/optional footer, handling layout and section semantics.

## Guidelines
- Clamp values to the available quota before passing to the component; avoid negative numbers.
- Supply descriptive copy instead of numerical readouts so meters communicate intent to screen reader users via `aria-valuenow`.
- For features not yet rolled out, set `disabled` to true and provide a contextual `disabledReason` so the default tooltip text is meaningful.

## Example
```tsx
<UsageGroup
  title="Usage Overview"
  description="Monitor feature availability across your account."
  items=[
    {
      label: "Automation credits",
      value: 40,
      quota: 200,
      description: "Automation triggers remaining."
    },
    {
      label: "Audio bridge",
      value: 0,
      quota: 60,
      disabled: true,
      disabledReason: "Audio bridge launches later this quarter."
    }
  ]
/>
```
