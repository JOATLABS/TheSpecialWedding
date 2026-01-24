## 2024-05-23 - Button Loading States
**Learning:** Standardizing loading states within the Button component itself reduces code duplication and ensures a consistent user experience across the application. Manual implementation of loading spinners in parent components often leads to inconsistent spacing, sizing, and accessibility issues.
**Action:** When creating or refactoring button components, always include a built-in `isLoading` prop that handles the disabled state, accessibility attributes, and visual spinner automatically.
