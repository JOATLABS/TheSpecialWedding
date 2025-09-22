# Form Builder System - Complete Guide

## Overview

The Wedding WebApp Form Builder is a comprehensive system for creating, managing, and distributing custom forms for wedding planning. It supports multiple creation methods, various field types, and includes features for data collection, analytics, and email distribution.

## Features

### 1. Form Creation Methods

The system now supports **three ways** to create forms:

#### 1.1 Blank Form Creation
- Start with a minimal template containing basic name and email fields
- Perfect for building custom forms from scratch
- Access via the "Blank Form" option in the create modal
- Template ID: `blank_form`

#### 1.2 Template-Based Creation
- Choose from pre-built templates:
  - **Blank Form** - Basic starting point
  - **Wedding Feedback Form** - Guest experience feedback
  - **Guest Feedback Survey** - Detailed guest satisfaction survey
  - **Vendor Questionnaire** - Vendor information collection
- Templates include pre-configured fields and settings
- Access via the "Use Template" option

#### 1.3 Form Duplication
- Create an exact copy of an existing form
- Includes all fields, settings, and configurations
- Perfect for creating variations of successful forms
- Access via the "Duplicate" button on any form card

### 2. Supported Field Types

The form builder supports comprehensive field types:
- `text` - Single line text input
- `email` - Email address with validation
- `phone` - Phone number input
- `number` - Numeric input
- `date` - Date picker
- `textarea` - Multi-line text input
- `select` - Dropdown selection
- `radio` - Radio button group
- `checkbox` - Multiple choice checkboxes
- `rating` - Star rating (1-5)
- `scale` - Numeric scale selection
- `file_upload` - File attachment support

### 3. Form Management

#### Creating Forms
```javascript
// API Endpoints

// Create from template
POST /admin/forms/from-template/{template_id}?form_name={name}

// Duplicate existing form
POST /admin/forms/duplicate/{form_id}?new_name={name}

// Direct form creation (advanced)
POST /admin/forms
Body: {
  name: "Form Name",
  settings: { ... },
  fields: [ ... ]
}
```

#### Managing Forms
- **Edit**: Modify form fields and settings
- **Delete**: Remove forms and associated data
- **View Responses**: Access submitted form data
- **Analytics**: View submission statistics
- **Send**: Distribute forms via email

### 4. Form Distribution

Forms can be distributed through:
- **Email campaigns** with customizable messages
- **Direct link sharing** for public access
- **Embedded forms** on wedding websites

Email distribution features:
- Bulk recipient management
- Custom email templates
- Reminder scheduling
- Delivery tracking

### 5. Data Collection & Analytics

#### Response Collection
- Public form submission without authentication
- Data validation and sanitization
- Secure storage with audit trails
- Real-time response tracking

#### Analytics Dashboard
- Submission count and trends
- Completion rates
- Field-level analytics
- Response time metrics
- Distribution performance

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