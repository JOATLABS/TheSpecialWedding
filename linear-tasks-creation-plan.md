# Linear Tasks Creation Plan - Wedding WebApp SAAS Technical Debt

## Epic: Q1 2025 Technical Debt Cleanup
**Description**: Comprehensive cleanup of TODO comments, technical debt, and code quality improvements for the Wedding WebApp SAAS platform.

**Labels**: `epic`, `technical-debt`, `q1-2025`

---

## Parent Task Groups

### 1. Email Service Implementation
**Parent Task**: "Complete Email Service Integration"
**Priority**: High
**Estimate**: 8 story points
**Labels**: `email-service`, `high-priority`, `backend`

#### Child Tasks:

**Task 1.1**: Implement actual email service in user management
- **File**: `/app/services/user_management_service.py:106`
- **Description**: Replace placeholder email service with actual email provider integration (Resend/SendGrid)
- **Priority**: High
- **Estimate**: 3 story points
- **Acceptance Criteria**:
  - Replace TODO comment with working email service
  - Integrate with existing email provider
  - Add error handling and logging
  - Update tests

**Task 1.2**: Implement welcome email functionality
- **File**: `/app/services/user_management_service.py:373`
- **Description**: Add welcome email sending when new users register
- **Priority**: High
- **Estimate**: 2 story points
- **Acceptance Criteria**:
  - Send welcome email on successful registration
  - Include user onboarding information
  - Handle email failures gracefully

**Task 1.3**: Complete EmailService class implementation
- **File**: `/app/services/user_management_service.py:390`
- **Description**: Implement the send_email method in EmailService class
- **Priority**: High
- **Estimate**: 3 story points
- **Acceptance Criteria**:
  - Complete email sending functionality
  - Add email templates support
  - Implement retry logic
  - Add email logging

### 2. SAAS Dashboard Enhancements
**Parent Task**: "Complete SAAS Dashboard Features"
**Priority**: High
**Estimate**: 5 story points
**Labels**: `saas`, `dashboard`, `revenue`

#### Child Tasks:

**Task 2.1**: Implement revenue calculation
- **File**: `/app/api/saas_config.py:408`
- **Description**: Calculate monthly revenue based on active subscriptions
- **Priority**: High
- **Estimate**: 5 story points
- **Acceptance Criteria**:
  - Query subscription data from database
  - Calculate monthly recurring revenue (MRR)
  - Include different subscription tiers
  - Add revenue analytics endpoint
  - Update dashboard to display revenue metrics

### 3. Content Management Features
**Parent Task**: "Implement Content Management Features"
**Priority**: Medium
**Estimate**: 8 story points
**Labels**: `cms`, `admin`, `frontend`

#### Child Tasks:

**Task 3.1**: Implement content editing modal
- **File**: `/app/admin/saas/page.tsx:385`
- **Description**: Create modal interface for editing website content sections
- **Priority**: Medium
- **Estimate**: 5 story points
- **Acceptance Criteria**:
  - Create modal component for content editing
  - Add rich text editor
  - Save content changes to backend
  - Preview functionality

**Task 3.2**: Add plus-ones support to email service
- **File**: `/app/services/email_service_resend.py:281`
- **Description**: Extend email service to handle plus-one guest invitations
- **Priority**: Medium
- **Estimate**: 3 story points
- **Acceptance Criteria**:
  - Identify plus-one guests in email sending
  - Customize email content for plus-ones
  - Update email templates

### 4. Guest Management Improvements
**Parent Task**: "Complete Guest Management Features"
**Priority**: Medium
**Estimate**: 3 story points
**Labels**: `guest-management`, `api`

#### Child Tasks:

**Task 4.1**: Implement plus ones API endpoint
- **File**: `/app/admin/guests/page.tsx:141`
- **Description**: Create API endpoint for fetching plus-one guest data
- **Priority**: Medium
- **Estimate**: 3 story points
- **Acceptance Criteria**:
  - Create plus-ones API endpoint
  - Update frontend to fetch plus-ones data
  - Add plus-ones to guest list display

### 5. Component Refactoring
**Parent Task**: "Refactor Large React Components"
**Priority**: Low-Medium
**Estimate**: 13 story points
**Labels**: `refactoring`, `maintainability`, `frontend`

#### Child Tasks:

**Task 5.1**: Refactor SAAS admin page component
- **File**: `/app/admin/saas/page.tsx` (1346 lines)
- **Description**: Break down large SAAS admin component into smaller, reusable components
- **Priority**: Medium
- **Estimate**: 5 story points
- **Acceptance Criteria**:
  - Split into logical sub-components (Analytics, Configuration, User Management)
  - Maintain existing functionality
  - Improve component testability
  - Add proper TypeScript interfaces

**Task 5.2**: Refactor wedding admin page component
- **File**: `/app/admin/weddings/[id]/page.tsx` (1016 lines)
- **Description**: Break down large wedding admin component into smaller components
- **Priority**: Medium
- **Estimate**: 5 story points
- **Acceptance Criteria**:
  - Split into feature-specific components
  - Extract custom hooks for data management
  - Improve performance with proper memoization

**Task 5.3**: Refactor reminders admin page component
- **File**: `/app/admin/reminders/page.tsx` (933 lines)
- **Description**: Break down reminders component into smaller, manageable pieces
- **Priority**: Low
- **Estimate**: 3 story points
- **Acceptance Criteria**:
  - Create separate components for reminder creation and management
  - Extract reminder logic into custom hooks
  - Improve code readability

### 6. Dependency Cleanup
**Parent Task**: "Update Dependencies and Remove Deprecated Packages"
**Priority**: Low
**Estimate**: 2 story points
**Labels**: `dependencies`, `maintenance`

#### Child Tasks:

**Task 6.1**: Replace deprecated @types/puppeteer package
- **Description**: Update to supported Puppeteer types or find alternative
- **Priority**: Low
- **Estimate**: 2 story points
- **Acceptance Criteria**:
  - Research current Puppeteer typing solution
  - Update package.json
  - Fix any type issues
  - Test PDF generation functionality

---

## Implementation Priority Order

### Sprint 1 (High Priority - Week 1-2)
1. Email Service Implementation (Tasks 1.1, 1.2, 1.3)
2. Revenue Calculation (Task 2.1)

### Sprint 2 (Medium Priority - Week 3-4)
3. Content Management (Tasks 3.1, 3.2)
4. Guest Management (Task 4.1)

### Sprint 3 (Refactoring - Week 5-6)
5. Component Refactoring (Tasks 5.1, 5.2)

### Sprint 4 (Cleanup - Week 7)
6. Dependency Updates (Task 6.1)
7. Remaining refactoring (Task 5.3)

---

## Story Point Estimation Guide

- **1-2 points**: Simple TODO fixes, minor updates
- **3-5 points**: Feature implementation, moderate complexity
- **8+ points**: Major features, complex refactoring

**Total Estimated Points**: 39 story points (~6-8 weeks)

---

## Quality Gates

Each task should meet these criteria before completion:
- [ ] All TODO comments removed or replaced with implementation
- [ ] Unit tests added/updated
- [ ] Code review completed
- [ ] Integration tests passing
- [ ] Documentation updated if needed

---

## Risk Mitigation

### High-Risk Items:
1. **Email Service Integration**: Test thoroughly with different providers
2. **Revenue Calculation**: Ensure data accuracy and performance
3. **Large Component Refactoring**: Maintain backward compatibility

### Dependencies:
- Email service tasks should be completed before welcome email functionality
- Plus-ones API should be completed before frontend integration
- Revenue calculation depends on subscription data structure

---

## Success Metrics

- [ ] All 7 TODO comments resolved
- [ ] Component sizes reduced by 50%+ 
- [ ] No deprecated dependencies
- [ ] 100% test coverage on new features
- [ ] Performance improvement on large components