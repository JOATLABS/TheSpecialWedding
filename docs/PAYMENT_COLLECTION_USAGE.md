# Payment Collection UI - Usage Guide

## Overview

Wedding planners can now collect payments from their couples directly through the platform using Stripe. This guide shows how to integrate the payment collection UI into your wedding management pages.

## Components Created

### 1. `CollectPaymentModal`
**Location**: `app/components/payments/CollectPaymentModal.tsx`

A modal dialog that allows planners to:
- Enter payment amount
- Add optional description
- Generate a secure payment link
- Copy link to clipboard
- Email link to couple

### 2. `PaymentCollectionButton`
**Location**: `app/components/payments/PaymentCollectionButton.tsx`

A reusable button component that opens the payment collection modal.

## Quick Integration

### Add to Any Wedding Page

```typescript
import { PaymentCollectionButton } from '@/components/payments/PaymentCollectionButton';

// In your wedding management component
<PaymentCollectionButton
  weddingId={wedding.id}
  weddingTitle={wedding.title}
/>
```

### Example: Add to Wedding Header

```typescript
"use client";

import { PaymentCollectionButton } from '@/components/payments/PaymentCollectionButton';

export function WeddingHeader({ wedding }) {
  return (
    <div className="flex justify-between items-center">
      <h1>{wedding.title}</h1>

      <div className="flex gap-2">
        <Button variant="outline">Edit Details</Button>
        <PaymentCollectionButton
          weddingId={wedding.id}
          weddingTitle={wedding.title}
        />
      </div>
    </div>
  );
}
```

### Example: Add to Wedding Card Grid

```typescript
import { PaymentCollectionButton } from '@/components/payments/PaymentCollectionButton';

export function WeddingCard({ wedding }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{wedding.title}</CardTitle>
      </CardHeader>
      <CardContent>
        <p>Date: {wedding.date}</p>
        <p>Guests: {wedding.guest_count}</p>
      </CardContent>
      <CardFooter className="flex gap-2">
        <Button variant="outline">Manage</Button>
        <PaymentCollectionButton
          weddingId={wedding.id}
          weddingTitle={wedding.title}
          variant="default"
          size="sm"
        />
      </CardFooter>
    </Card>
  );
}
```

## User Flow

1. **Planner clicks "Collect Payment" button**
   - Modal opens with amount and description fields

2. **Planner enters details**
   - Amount: e.g., `1500.00`
   - Description: "Final payment for wedding services"

3. **System creates payment intent**
   - Calls `/admin/stripe/create-payment-intent` API
   - Generates secure Stripe payment intent
   - Creates shareable payment link

4. **Planner shares link**
   - Link automatically copied to clipboard
   - Can email directly from modal
   - Example link: `https://yoursite.com/pay/pi_abc123...`

5. **Couple pays via link**
   - Opens secure Stripe payment page
   - Enters card details
   - Completes payment

6. **Payment confirmation**
   - Stripe processes payment
   - Webhook updates payment status
   - Planner notified of successful payment

## API Integration

The payment collection uses your existing Stripe integration:

**Endpoint**: `POST /admin/stripe/create-payment-intent`

**Request**:
```json
{
  "amount": 1500.00,
  "currency": "usd",
  "wedding_id": "wedding_123",
  "description": "Final payment for wedding services",
  "metadata": {
    "wedding_title": "Smith-Johnson Wedding",
    "payment_type": "wedding_services"
  }
}
```

**Response**:
```json
{
  "status": "success",
  "payment_intent": {
    "payment_intent_id": "pi_abc123...",
    "client_secret": "pi_abc123..._secret_xyz",
    "amount": 1500.00,
    "currency": "usd",
    "status": "requires_payment_method"
  }
}
```

## Creating the Payment Page (TODO)

To complete the flow, you need to create a payment completion page at:

**File**: `app/pay/[payment_intent_id]/page.tsx`

```typescript
"use client";

import { useEffect, useState } from 'react';
import { Elements, PaymentElement, useStripe, useElements } from '@stripe/react-stripe-js';
import { loadStripe } from '@stripe/stripe-js';

const stripePromise = loadStripe(process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY!);

export default function PaymentPage({ params }) {
  const [clientSecret, setClientSecret] = useState('');

  useEffect(() => {
    // Fetch payment intent details from your API
    // using params.payment_intent_id
  }, [params.payment_intent_id]);

  return (
    <Elements stripe={stripePromise} options={{ clientSecret }}>
      <PaymentForm />
    </Elements>
  );
}

function PaymentForm() {
  const stripe = useStripe();
  const elements = useElements();

  const handleSubmit = async (e) => {
    e.preventDefault();

    const { error } = await stripe.confirmPayment({
      elements,
      confirmParams: {
        return_url: `${window.location.origin}/payment-success`,
      },
    });

    if (error) {
      // Handle error
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <PaymentElement />
      <button type="submit">Pay Now</button>
    </form>
  );
}
```

## Component Props

### PaymentCollectionButton

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `weddingId` | string | required | The wedding ID |
| `weddingTitle` | string | required | Wedding title for display |
| `variant` | 'default' \| 'outline' \| 'ghost' | 'default' | Button style variant |
| `size` | 'default' \| 'sm' \| 'lg' \| 'icon' | 'default' | Button size |
| `className` | string | '' | Additional CSS classes |

### CollectPaymentModal

| Prop | Type | Description |
|------|------|-------------|
| `open` | boolean | Modal open state |
| `onClose` | () => void | Close handler |
| `weddingId` | string | The wedding ID |
| `weddingTitle` | string | Wedding title |
| `onPaymentCreated` | (payment) => void | Callback when payment created |

## Styling

The components use your existing UI components:
- `Dialog` from `@/components/ui/dialog`
- `Button` from `@/components/ui/button`
- `Input` from `@/components/ui/input`
- `Textarea` from `@/components/ui/textarea`

They automatically adapt to your theme (light/dark mode).

## Security Notes

✅ **Authentication Required**: All payment creation endpoints require authentication
✅ **Wedding Ownership Validation**: Backend verifies planner owns the wedding
✅ **Stripe Security**: Payment processing uses Stripe's secure infrastructure
✅ **No Card Data**: Your servers never see card details (handled by Stripe)

## Next Steps

1. **Add button to wedding management pages**
   - Import `PaymentCollectionButton`
   - Pass wedding ID and title

2. **Create payment completion page**
   - Create `app/pay/[payment_intent_id]/page.tsx`
   - Use Stripe Elements for payment form

3. **Add payment tracking**
   - Show payment history per wedding
   - Display payment status (pending/paid/failed)

4. **Email notifications**
   - Auto-send payment link to couple's email
   - Send confirmation when payment received

## Example Implementation

```typescript
// app/admin/weddings/page.tsx
"use client";

import { PaymentCollectionButton } from '@/components/payments/PaymentCollectionButton';

export default function WeddingsPage() {
  const [weddings, setWeddings] = useState([]);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      {weddings.map((wedding) => (
        <Card key={wedding.id}>
          <CardHeader>
            <CardTitle>{wedding.title}</CardTitle>
            <CardDescription>{wedding.date}</CardDescription>
          </CardHeader>
          <CardFooter className="flex gap-2">
            <Button variant="outline" onClick={() => router.push(`/admin/weddings/${wedding.id}`)}>
              Manage
            </Button>
            <PaymentCollectionButton
              weddingId={wedding.id}
              weddingTitle={wedding.title}
              variant="default"
            />
          </CardFooter>
        </Card>
      ))}
    </div>
  );
}
```

## Support

For issues or questions:
- Check the Stripe dashboard for payment status
- Review webhook logs for event processing
- Contact support with payment intent ID

---

**Status**: ✅ Payment Collection UI Ready
**Last Updated**: January 2025
