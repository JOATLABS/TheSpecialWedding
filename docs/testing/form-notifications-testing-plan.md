# Form Notifications System - Testing Plan

## Overview
This document outlines the comprehensive testing strategy for the form response notification system, covering both backend and frontend functionality across multiple test types.

## Test Architecture

### Test Categories
1. **Unit Tests**: Individual component and service testing
2. **Integration Tests**: API endpoint and service integration testing
3. **End-to-End Tests**: Complete user workflow testing
4. **Component Tests**: React component behavior testing

### Test Structure
```
tests/
├── unit/                           # Backend unit tests (Python/pytest)
│   ├── test_notification_service.py
│   └── test_form_models.py
├── integration/                    # Backend integration tests
│   ├── test_notification_api.py
│   └── test_form_response_flow.py
├── frontend/                       # Frontend component tests
│   ├── components/
│   │   ├── NotificationBadge.test.tsx
│   │   └── FormResponsesPage.test.tsx
│   └── pages/
│       └── ProfileNotifications.test.tsx
├── e2e/                           # End-to-end Playwright tests
│   ├── form-notification-workflow.spec.ts
│   └── notification-preferences.spec.ts
└── fixtures/                      # Test data and factories
    ├── form_data.json
    └── notification_data.json
```

## Backend Testing

### Unit Tests (`tests/unit/`)

#### 1. Notification Service Tests (`test_notification_service.py`)
- **notify_form_response()**: Email sending and in-app notification creation
- **get_notification_preferences()**: User preference retrieval
- **update_notification_preferences()**: Preference updates
- **get_unread_form_response_count()**: Unread count calculation
- **_send_form_response_email()**: Email template rendering and delivery

#### 2. Form Models Tests (`test_form_models.py`)
- **FormResponse model**: Review status fields validation
- **UpdateResponseReviewRequest**: Request validation
- **NotificationPreferences**: Preference structure validation

### Integration Tests (`tests/integration/`)

#### 1. Notification API Tests (`test_notification_api.py`)
- **GET /admin/notifications/preferences**: Fetch user preferences
- **PUT /admin/notifications/preferences**: Update preferences
- **GET /admin/notifications/unread-count**: Get unread response count
- **PATCH /admin/forms/{form_id}/responses/{response_id}/review**: Mark as reviewed

#### 2. Form Response Flow Tests (`test_form_response_flow.py`)
- **Complete notification workflow**: Form submission → notification trigger → email sent
- **Review status updates**: Mark as reviewed/unreviewed
- **Preference enforcement**: Respect user notification settings
- **Error handling**: Failed email delivery, invalid preferences

## Frontend Testing

### Component Tests (`tests/frontend/components/`)

#### 1. NotificationBadge Tests (`NotificationBadge.test.tsx`)
- **Count display**: Proper count formatting (99+)
- **Conditional rendering**: Show/hide based on count and showZero
- **Dark mode**: Proper styling in light/dark themes
- **Responsive design**: Mobile vs desktop sizing

#### 2. Form Responses Page Tests (`FormResponsesPage.test.tsx`)
- **Response listing**: Display responses with review status
- **Status filtering**: Filter by read/unread status
- **Review toggle**: Mark responses as reviewed/unreviewed
- **Badge display**: Show unread count in header
- **Loading states**: Handle API loading and updating states

### Page Tests (`tests/frontend/pages/`)

#### 1. Profile Notifications Tests (`ProfileNotifications.test.tsx`)
- **Tab navigation**: Switch between notification settings
- **Toggle switches**: Email and instant notification controls
- **Form selection**: Checkbox list for per-form preferences
- **Settings persistence**: Save and load preferences
- **Validation**: Prevent invalid preference combinations

## End-to-End Tests (`tests/e2e/`)

### 1. Form Notification Workflow (`form-notification-workflow.spec.ts`)
**Test Scenario**: Complete form submission and notification flow
1. Admin creates a form
2. Admin enables email notifications in preferences
3. User submits form response
4. Admin receives email notification
5. Admin sees unread badge in dashboard
6. Admin marks response as reviewed
7. Badge count updates

### 2. Notification Preferences (`notification-preferences.spec.ts`)
**Test Scenario**: Notification preference management
1. Admin navigates to profile settings
2. Opens notifications tab
3. Toggles email notifications on/off
4. Changes from instant to digest notifications
5. Selects specific forms for notifications
6. Saves preferences and verifies persistence
7. Tests preference enforcement in actual notifications

## Test Data & Fixtures

### Form Data (`fixtures/form_data.json`)
```json
{
  "test_form": {
    "name": "Wedding Feedback Form",
    "settings": {
      "title": "How was your wedding experience?",
      "description": "We'd love to hear about your special day!"
    },
    "fields": [
      {
        "id": "rating",
        "label": "Overall Rating",
        "type": "rating",
        "required": true
      }
    ]
  }
}
```

### Notification Data (`fixtures/notification_data.json`)
```json
{
  "default_preferences": {
    "email_enabled": true,
    "instant_notifications": true,
    "digest_frequency": "daily",
    "forms": []
  },
  "test_response": {
    "responses": {
      "rating": 5,
      "feedback": "Amazing experience!"
    },
    "submitted_by_email": "bride@example.com",
    "submitted_by_name": "Jane Doe"
  }
}
```

## Test Execution Strategy

### CI/CD Integration
1. **Unit Tests**: Run on every commit
2. **Integration Tests**: Run on pull requests
3. **E2E Tests**: Run on staging deployments
4. **Component Tests**: Run with unit tests

### Test Commands
```bash
# Backend tests
pytest tests/unit/ -v
pytest tests/integration/ -v

# Frontend tests
npm run test:components
npm run test:pages

# E2E tests
npx playwright test tests/e2e/

# All tests
npm run test:all
```

### Performance Benchmarks
- **Unit Tests**: < 30 seconds total
- **Integration Tests**: < 2 minutes total
- **E2E Tests**: < 5 minutes total
- **Component Tests**: < 1 minute total

## Test Coverage Goals

### Backend Coverage
- **Notification Service**: 95%+ line coverage
- **API Endpoints**: 100% endpoint coverage
- **Model Validation**: 100% validation rule coverage

### Frontend Coverage
- **Components**: 90%+ component coverage
- **User Interactions**: 100% interaction coverage
- **State Management**: 95%+ state change coverage

### E2E Coverage
- **Critical Paths**: 100% main workflow coverage
- **Error Scenarios**: 80% error path coverage
- **Mobile Responsive**: 100% mobile flow coverage

## Success Criteria

### Functional Requirements
- ✅ Form submissions trigger notifications
- ✅ Email notifications contain response preview
- ✅ In-app badges show accurate unread counts
- ✅ Review status persists across sessions
- ✅ Preferences control notification behavior
- ✅ Mobile-responsive interface works correctly
- ✅ Dark mode displays properly

### Performance Requirements
- ✅ Notification emails sent within 5 seconds
- ✅ Badge counts update within 2 seconds
- ✅ Preference changes save within 3 seconds
- ✅ Page loads complete within 2 seconds

### Security Requirements
- ✅ Only authorized users receive notifications
- ✅ Email content doesn't expose sensitive data
- ✅ Preference updates require authentication
- ✅ Response data access properly controlled

## Test Maintenance

### Regular Updates
- **Monthly**: Review test coverage and add missing scenarios
- **Per Feature**: Update tests when notification features change
- **Per Release**: Run full test suite before production deployment

### Test Data Management
- **Cleanup**: Automated test data cleanup after test runs
- **Isolation**: Each test uses isolated data sets
- **Versioning**: Test data versioned with application releases

---

This testing plan ensures comprehensive coverage of the form notification system across all layers of the application, from individual components to complete user workflows.