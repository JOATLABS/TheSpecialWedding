# Form Builder System - Implementation Guide (January 2025)

## Overview

The Wedding WebApp Form Builder is a comprehensive system for creating, managing, and distributing custom forms for wedding planning. It supports multiple creation methods, various field types, and includes features for data collection, analytics, and email distribution.

## Features

### 1. Form Creation Methods

The planner workspace now delivers all three promised creation paths with glassmorphic styling, accessible focus states, and secur
e defaults applied automatically.

#### 1.1 Template-Based Creation (implemented)
- Choose from curated templates within the "Create New Form" modal
- Templates ship with Apple glass-inspired copy, required fields, and consistent success messaging
- Accessible through the primary CTA on `/admin/forms`

#### 1.2 Blank Form Creation (implemented)
- Select "Start from scratch" to generate an empty, sanitised form using `POST /admin/forms`
- Configurable toggles control whether the form is public and whether email addresses are collected by default
- Titles, descriptions, and button labels are sanitised to avoid script injection while matching Apple glass tone

#### 1.3 Form Duplication (implemented)
- Choose "Duplicate an existing form" when launching the modal
- Calls the dedicated duplication endpoint to copy fields/settings while resetting submissions and unread counters
- Keeps analytics clean so the clone begins with zero responses and its own planner view state

### 2. Supported Field Types

Template metadata references the field types below, but only a subset is exercised by the current UI. File uploads, rating, scale, and SMS-related fields require additional work before they can be surfaced reliably.
- `text`
- `email`
- `phone`
- `number`
- `date`
- `textarea`
- `select`
- `radio`
- `checkbox`
- `rating` (planned)
- `scale` (planned)
- `file_upload` (planned)

### 3. Form Management

#### Creating Forms
```javascript
// API Endpoints currently in use

// Create from template
POST /admin/forms/from-template/{template_id}?form_name={name}

// Duplicate existing form
POST /admin/forms/{form_id}/duplicate
Body: { new_name: "Vendor Intake Copy" }

// Direct form creation
POST /admin/forms
Body: {
  name: "Form Name",
  settings: { ... },
  fields: [ ... ]
}

// Persist planner view state for unread badge accuracy
POST /admin/forms/{form_id}/views
Body: { scope: "responses" | "analytics", submission_count?: number }
```

#### Managing Forms (current capabilities)
- **Edit**: Modify form fields and settings
- **Delete**: Remove forms and associated data
- **View Responses**: Access submitted form data
- **Send**: Distribute forms via email

#### Still to build
- Field-level analytics (current dashboard focuses on distribution funnel metrics)
- Embed widgets for wedding microsites

### 4. Form Distribution

Forms can be distributed through:
- **Email campaigns** with customizable messages (implemented)
- **Direct link sharing** for public access (implemented)
- **Embedded forms** on wedding websites (planned – no embed widget available yet)

Email distribution roadmap:
- Bulk recipient management (basic list support exists; segmentation tooling pending)
- Custom email templates (limited to text editing)
- Reminder scheduling (not yet implemented)
- Delivery tracking (not yet implemented)

### 5. Data Collection & Analytics

#### Response Collection
- Public form submission without authentication
- Data validation and sanitization
- Secure storage with audit trails
- Real-time response tracking

#### Analytics Dashboard (implemented)
- Submission count and trends sourced from `/admin/saas/analytics/platform`
- Completion, open, and click-through rates with automated performance tips
- Field-level analytics and response time metrics remain on the roadmap

### 6. Security Features

- **Authentication**: Role-based access control (Wedding Planner, Root Admin)
- **Authorization**: Wedding-scoped data isolation
- **Validation**: Comprehensive input sanitization
- **XSS Protection**: HTML escaping for all user content
- **Rate Limiting**: Protection against spam submissions
- **Audit Logging**: Security event tracking

## UI Components & Testing IDs

For automated testing, the following IDs are available:

### Form Management Page
- `#create-form-button` - Main create form button
- `#edit-form-{formId}` - Edit form button
- `#duplicate-form-{formId}` - Duplicate form button
- `#delete-form-{formId}` - Delete form button

### Create Form Modal
- `#creation-type-blank` - Select blank form option
- `#creation-type-template` - Select template option
- `#creation-type-duplicate` - Select duplicate option
- `#form-name-input` - Form name input field
- `#template-select` - Template selection dropdown
- `#duplicate-form-select` - Form selection for duplication
- `#confirm-create-button` - Create form button
- `#cancel-create-button` - Cancel creation button

### Form Send Page
- `#email-input` - Recipient email input
- `#send-form-button` - Send form button
- Category selection buttons for recipients

## API Reference

### Form Endpoints

#### Get Form Templates
```http
GET /admin/form-templates
Authorization: Bearer {token}

Response: {
  templates: [
    {
      id: string,
      name: string,
      description: string,
      category: string,
      fields: [...]
    }
  ]
}
```

#### Create Form from Template
```http
POST /admin/forms/from-template/{template_id}?form_name={name}
Authorization: Bearer {token}

Response: {
  id: string,
  message: "Form created successfully"
}
```

#### Duplicate Form
```http
POST /admin/forms/duplicate/{form_id}?new_name={name}
Authorization: Bearer {token}

Response: {
  id: string,
  message: "Form duplicated successfully"
}
```

#### Get Forms
```http
GET /admin/forms?wedding_id={id}
Authorization: Bearer {token}

Response: [
  {
    id: string,
    name: string,
    settings: {...},
    fields: [...],
    submission_count: number,
    created_at: datetime
  }
]
```

#### Get Form Analytics
```http
GET /admin/forms/{form_id}/analytics
Authorization: Bearer {token}

Response: {
  total_responses: number,
  completion_rate: number,
  field_analytics: {...},
  response_trends: [...]
}
```

## Best Practices

### Form Design
1. **Start Simple**: Use blank forms for basic needs
2. **Leverage Templates**: Use pre-built templates for common scenarios
3. **Test Before Sending**: Always preview forms before distribution
4. **Required Fields**: Limit required fields to essentials
5. **Clear Labels**: Use descriptive, concise field labels

### Data Management
1. **Regular Exports**: Export response data regularly
2. **Privacy**: Only collect necessary information
3. **Validation**: Set appropriate validation rules
4. **Analytics**: Monitor form performance regularly

### Security
1. **Access Control**: Limit form access to authorized users
2. **Data Sanitization**: Always sanitize user inputs
3. **Audit Logs**: Review security events regularly
4. **Updates**: Keep the system updated with security patches

## Troubleshooting

### Common Issues

#### "Cannot create blank form"
- **Solution**: Ensure the blank_form template is available in the templates list
- **Check**: GET /admin/form-templates should include blank_form

#### "Form duplication fails"
- **Cause**: Insufficient permissions or form doesn't exist
- **Solution**: Verify form ID and user permissions

#### "Email distribution not working"
- **Cause**: Missing or invalid RESEND_API_KEY
- **Solution**: Configure email service credentials in environment

#### "Form not accessible publicly"
- **Cause**: Form settings have is_public: false
- **Solution**: Update form settings to enable public access

## Version History

### v2.0.0 (Current)
- Added blank form creation option
- Implemented form duplication feature
- Enhanced UI with creation type selection
- Added comprehensive testing IDs
- Improved error handling and validation

### v1.0.0
- Initial form builder implementation
- Template-based creation only
- Basic field types support
- Email distribution system

## Future Enhancements

- Conditional logic for fields
- Advanced validation rules
- Multi-page forms
- Form versioning
- A/B testing capabilities
- Integration with wedding guest lists
- Automated reminder sequences
- Export to multiple formats (PDF, Excel)

---

*Last Updated: January 2025*
*Documentation Version: 2.0.0*