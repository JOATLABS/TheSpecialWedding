# Project TODO Backlog

Consolidated from in-code TODO comments. Categories: feature, refactor, analytics, theming, content, future.

## Feature

- Gallery Upload (`app/admin/gallery/upload/page.tsx`): Add logout control in header when gallery management UI expands.
- RSVP Form (`app/components/RSVPForm.tsx`): Plus-one customization state reserved for future enhancement; currently handled by dynamic fields.

## Refactor

- Admin Dashboard (`app/admin/page.tsx`): Consider lifting userProfile fetch/state into AdminContext if multiple dashboard widgets need it.

## Future

- Profile Update (`app/admin/profile/page.tsx`): Use update response payload to optimistically update UI instead of refetching profile.

## Content

- Privacy Modal (`app/components/PrivacyModal.tsx`): Use weddingName prop to personalize privacy policy copy.

## Analytics

- Budget Category Card (`app/components/budget/BudgetCategoryCard.tsx`): Display or remove subcategoriesTotal; could add aggregated metric to UI.

## Theming

- Landing Layout (`app/components/landing-page/LandingLayout.tsx`): Theme hook return currently unused; plan dynamic palette adjustments or remove call result.

## Notes

- All unused variables causing noise have been removed or underscored. Remaining TODOs are intentional placeholders.
- Revisit quarterly or before major release to either implement or delete stale items.
