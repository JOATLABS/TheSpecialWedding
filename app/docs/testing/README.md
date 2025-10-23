# Testing Documentation

This directory contains testing-related documentation for the Wedding Web Application.

## Available Documentation

### [ID Attributes Enhancement](./id-attributes-enhancement.md)
Comprehensive documentation of ID attributes added to interactive elements for improved automation testing compatibility. Includes:
- Before/after code examples for all modified elements
- Naming convention standards
- Automation testing benefits
- Files modified across forms, RSVP, and vendor components

### [Form Notifications Testing Plan](./form-notifications-testing-plan.md)
Testing plan for form notification system functionality.

## Quick Reference

### ID Naming Patterns
- **Dynamic Form Fields**: `{field.id}-{type}-{index}` (e.g., `contact-preference-radio-0`)
- **Vendor Fields**: `vendor-field-{field.id}` for consistent vendor form targeting
- **Static Elements**: Semantic names like `form-submit-button`, `rsvp-submit-button`
- **Event-specific**: Descriptive names like `attending-traditional`, `dietary-restrictions`

### Automation Testing
All major form components now include comprehensive ID attributes for reliable automation testing with tools like:
- Selenium WebDriver
- Playwright
- Cypress
- Puppeteer

## Contributing
When adding new interactive elements, follow the established ID naming conventions documented in the enhancement guide.