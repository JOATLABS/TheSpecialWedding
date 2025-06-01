# Wedding Web App Frontend

## Overview
Next.js-based frontend for the Wedding Web Application, providing guest RSVP functionality, admin management, and wedding event tracking.

## Project Structure
```
app/
├── [slug]/                 # Dynamic wedding pages
│   └── invite/
│       └── [token]/       # Guest invitation pages
├── api/                   # Backend API endpoints
├── core/                  # Core configurations
├── dependencies/          # Auth and dependency injection
├── models/               # Data models
├── services/             # Business logic services
├── utils/                # Utility functions
└── hooks/                # React hooks (e.g., useWedding)
```

## Key Features

### Guest Features
- **RSVP System**: Personal invitation pages with unique tokens
- **Event Selection**: Choose which wedding events to attend
- **Plus One Management**: Add guest companions when allowed
- **Dietary Restrictions**: Specify food preferences/allergies
- **SMS Reminders**: Phone number collection for event reminders

### Admin Features
- **Guest Management**: Import/export guest lists via CSV
- **RSVP Tracking**: Monitor guest responses
- **Check-in System**: Track guest arrivals at events
- **Wedding Management**: Create and manage multiple weddings

## Development Status

### Completed ✅
- [x] Guest invitation page (`/[slug]/invite/[token]`)
- [x] Basic RSVP form submission
- [x] Wedding data fetching
- [x] Guest authentication via tokens
- [x] Plus one conditional rendering

### In Progress 🚧
- [ ] Form validation and error handling
- [ ] Success/confirmation pages
- [ ] Loading states
- [ ] useWedding hook implementation

### Planned 📋
- [ ] Guest dashboard
- [ ] RSVP modification
- [ ] Gallery upload feature
- [ ] Mobile-responsive design
- [ ] Automated testing setup
- [ ] Internationalization (i18n)

## API Integration
The frontend connects to the FastAPI backend at:
- Development: `http://localhost:8000`
- Production: Set via `NEXT_PUBLIC_API_BASE_URL`

### Key Endpoints Used
- `GET /weddings/slug/{slug}` - Fetch wedding by URL slug
- `GET /invite/{token}` - Validate invitation token
- `POST /invite/{token}/rsvp` - Submit RSVP response

## Environment Variables
```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

## Testing Strategy

### Areas Requiring Test Coverage
1. **Invitation Flow**
   - Token validation
   - Guest data loading
   - Form submission

2. **RSVP Form**
   - Event selection
   - Plus one addition
   - Form validation

3. **API Integration**
   - Error handling
   - Loading states
   - Success responses

### Recommended Testing Attributes
Add `data-testid` attributes to key elements:
- `wedding-title`
- `guest-greeting`
- `event-checkbox-{eventType}`
- `dietary-input`
- `phone-input`
- `plus-one-section`
- `submit-rsvp-button`

## Development Guidelines

### Code Style
- TypeScript for type safety
- Async/await for API calls
- Server Components where possible
- Client Components for interactivity

### Component Structure
- Pages in `app/` directory
- Shared components in `app/components/`
- Hooks in `app/hooks/`
- Types in `app/types/`

## Running the Frontend

```bash
# Install dependencies
npm install

# Run development server
npm run dev

# Build for production
npm run build

# Run production build
npm start
```

## Next Steps
1. Implement proper error boundaries
2. Add loading skeletons
3. Create reusable form components
4. Set up testing framework
5. Implement guest dashboard
6. Add analytics tracking

## Notes
- Using Next.js 13+ with App Router
- Server Components for initial data fetching
- Form submissions currently use native HTML forms (consider React Hook Form)
- Mobile-first responsive design approach needed