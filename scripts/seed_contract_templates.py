"""
Seed Default Contract Templates

Run this script to create system contract templates for each vendor category.
Templates include placeholders that auto-populate with vendor/wedding data.

Usage:
    python scripts/seed_contract_templates.py
"""

import asyncio
import os
import sys
from datetime import datetime

from bson import ObjectId

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import init_database, mongo  # noqa: E402

# Standard placeholders available in all templates
STANDARD_PLACEHOLDERS = [
    {
        "key": "{{vendor_name}}",
        "label": "Vendor Business Name",
        "source": "vendor",
        "field_path": "business_name",
    },
    {
        "key": "{{vendor_email}}",
        "label": "Vendor Email",
        "source": "vendor",
        "field_path": "email",
    },
    {
        "key": "{{vendor_phone}}",
        "label": "Vendor Phone",
        "source": "vendor",
        "field_path": "phone",
    },
    {
        "key": "{{vendor_address}}",
        "label": "Vendor Address",
        "source": "vendor",
        "field_path": "address",
    },
    {
        "key": "{{couple_names}}",
        "label": "Couple Names",
        "source": "wedding",
        "field_path": "couple_names",
    },
    {
        "key": "{{wedding_date}}",
        "label": "Wedding Date",
        "source": "wedding",
        "field_path": "date",
    },
    {
        "key": "{{wedding_venue}}",
        "label": "Wedding Venue",
        "source": "wedding",
        "field_path": "venue",
    },
    {
        "key": "{{total_amount}}",
        "label": "Total Contract Amount",
        "source": "contract",
        "field_path": "total_amount",
    },
    {
        "key": "{{deposit_amount}}",
        "label": "Deposit Amount",
        "source": "contract",
        "field_path": "deposit_amount",
    },
    {
        "key": "{{service_category}}",
        "label": "Service Category",
        "source": "vendor",
        "field_path": "service_category",
    },
    {
        "key": "{{planner_name}}",
        "label": "Planner Name",
        "source": "planner",
        "field_path": "name",
    },
    {
        "key": "{{planner_email}}",
        "label": "Planner Email",
        "source": "planner",
        "field_path": "email",
    },
    {
        "key": "{{planner_company}}",
        "label": "Planner Company",
        "source": "planner",
        "field_path": "company_name",
    },
    {
        "key": "{{contract_date}}",
        "label": "Contract Date",
        "source": "system",
        "field_path": "current_date",
    },
    {
        "key": "{{contract_number}}",
        "label": "Contract Number",
        "source": "contract",
        "field_path": "contract_number",
    },
]


DEFAULT_TEMPLATES = [
    {
        "name": "Photography Services Contract",
        "description": "Standard contract template for wedding photography services",
        "service_category": "photographer",
        "sections": [
            {
                "id": str(ObjectId()),
                "title": "Parties",
                "content": """This Photography Services Agreement ("Agreement") is entered into as of {{contract_date}}

BETWEEN:

**Service Provider (Photographer):**
{{vendor_name}}
{{vendor_address}}
Email: {{vendor_email}}
Phone: {{vendor_phone}}

AND

**Client:**
{{couple_names}}
Planning Contact: {{planner_name}} ({{planner_email}})
Company: {{planner_company}}

Contract Reference: {{contract_number}}""",
                "order": 1,
            },
            {
                "id": str(ObjectId()),
                "title": "Event Details",
                "content": """**Wedding Date:** {{wedding_date}}
**Venue:** {{wedding_venue}}
**Service Type:** {{service_category}}

The Photographer agrees to provide photography services for the wedding celebration detailed above.""",
                "order": 2,
            },
            {
                "id": str(ObjectId()),
                "title": "Services & Deliverables",
                "content": """The Photographer shall provide the following services:

1. Professional photography coverage as discussed
2. High-resolution edited digital images
3. Online gallery for image viewing and downloading
4. [Additional services as agreed]

**Coverage Hours:** As specified in the quote
**Estimated Delivery:** 6-8 weeks after the event""",
                "order": 3,
            },
            {
                "id": str(ObjectId()),
                "title": "Investment & Payment",
                "content": """**Total Investment:** ${{total_amount}}

**Payment Schedule:**
- Deposit (50%): ${{deposit_amount}} due upon signing
- Final Balance: Due 14 days before the wedding date

All payments are non-refundable but may be applied to a rescheduled date.""",
                "order": 4,
            },
        ],
        "terms_and_conditions": """**TERMS AND CONDITIONS**

1. **Copyright:** The Photographer retains copyright to all images. Client receives a print release for personal use.

2. **Model Release:** Client grants permission for the Photographer to use images for portfolio and marketing purposes.

3. **Limitation of Liability:** Photographer's liability is limited to the total amount paid under this contract.

4. **Force Majeure:** Neither party shall be liable for delays or failures due to circumstances beyond their control.

5. **Entire Agreement:** This document represents the entire agreement between the parties.""",
        "cancellation_policy": """**CANCELLATION POLICY**

- More than 90 days before event: Deposit forfeited, no additional charges
- 30-90 days before event: 50% of total fee due
- Less than 30 days before event: 100% of total fee due

Rescheduling is permitted with at least 30 days notice, subject to availability.""",
        "default_deposit_percentage": 50,
        "default_payment_schedule": [
            {
                "percentage": 50,
                "description": "Deposit - Due upon signing",
                "days_before_event": None,
            },
            {"percentage": 50, "description": "Final Balance", "days_before_event": 14},
        ],
    },
    {
        "name": "Catering Services Contract",
        "description": "Standard contract template for wedding catering services",
        "service_category": "caterer",
        "sections": [
            {
                "id": str(ObjectId()),
                "title": "Parties",
                "content": """This Catering Services Agreement ("Agreement") is entered into as of {{contract_date}}

BETWEEN:

**Caterer:**
{{vendor_name}}
{{vendor_address}}
Email: {{vendor_email}}
Phone: {{vendor_phone}}

AND

**Client:**
{{couple_names}}
Planning Contact: {{planner_name}} ({{planner_email}})

Contract Reference: {{contract_number}}""",
                "order": 1,
            },
            {
                "id": str(ObjectId()),
                "title": "Event Details",
                "content": """**Event Date:** {{wedding_date}}
**Venue:** {{wedding_venue}}
**Event Type:** Wedding Reception

The Caterer agrees to provide food and beverage services for the wedding celebration.""",
                "order": 2,
            },
            {
                "id": str(ObjectId()),
                "title": "Menu & Services",
                "content": """**Services Include:**
- Menu as selected and confirmed
- Professional service staff
- All necessary equipment and tableware
- Setup and cleanup

**Guest Count:** To be confirmed 14 days prior
**Service Style:** [Plated/Buffet/Family Style]

Final menu selections due 30 days before event.""",
                "order": 3,
            },
            {
                "id": str(ObjectId()),
                "title": "Investment & Payment",
                "content": """**Estimated Total:** ${{total_amount}}

Note: Final amount may vary based on confirmed guest count.

**Payment Schedule:**
- Deposit (25%): ${{deposit_amount}} due upon signing
- Progress Payment (50%): Due 30 days before event
- Final Balance (25%): Due on event day or within 7 days after""",
                "order": 4,
            },
        ],
        "terms_and_conditions": """**TERMS AND CONDITIONS**

1. **Guest Count:** Final guest count required 14 days before event. Client will be charged for confirmed count or actual attendance, whichever is greater.

2. **Dietary Requirements:** Must be communicated at least 14 days in advance.

3. **Venue Access:** Caterer requires access to venue at least 4 hours before service.

4. **Alcohol:** Caterer requires appropriate licenses for alcohol service if applicable.

5. **Leftovers:** Due to food safety regulations, leftovers cannot be provided to guests.""",
        "cancellation_policy": """**CANCELLATION POLICY**

- More than 60 days before event: Deposit forfeited
- 30-60 days before event: 50% of estimated total due
- Less than 30 days before event: 100% of estimated total due

Menu changes may be made up to 30 days before event without penalty.""",
        "default_deposit_percentage": 25,
        "default_payment_schedule": [
            {
                "percentage": 25,
                "description": "Deposit - Due upon signing",
                "days_before_event": None,
            },
            {
                "percentage": 50,
                "description": "Progress Payment",
                "days_before_event": 30,
            },
            {"percentage": 25, "description": "Final Balance", "days_before_event": 0},
        ],
    },
    {
        "name": "Florist Services Contract",
        "description": "Standard contract template for wedding floral services",
        "service_category": "florist",
        "sections": [
            {
                "id": str(ObjectId()),
                "title": "Parties",
                "content": """This Floral Services Agreement is entered into as of {{contract_date}}

**Florist:** {{vendor_name}}
**Contact:** {{vendor_email}} | {{vendor_phone}}

**Client:** {{couple_names}}
**Planner:** {{planner_name}} ({{planner_company}})

Contract #: {{contract_number}}""",
                "order": 1,
            },
            {
                "id": str(ObjectId()),
                "title": "Event & Delivery",
                "content": """**Wedding Date:** {{wedding_date}}
**Delivery Location:** {{wedding_venue}}

Florist will deliver and set up all floral arrangements prior to the ceremony.""",
                "order": 2,
            },
            {
                "id": str(ObjectId()),
                "title": "Floral Package",
                "content": """**Package Includes:**
- Bridal bouquet
- Bridesmaid bouquets (quantity TBD)
- Boutonnieres
- Ceremony arrangements
- Reception centerpieces
- Additional items as specified

*Final selections and quantities to be confirmed 6 weeks before event.*""",
                "order": 3,
            },
            {
                "id": str(ObjectId()),
                "title": "Investment",
                "content": """**Total:** ${{total_amount}}
**Deposit:** ${{deposit_amount}} (due upon signing)

Seasonal flower availability may affect final selections. Substitutions of equal or greater value may be made with client approval.""",
                "order": 4,
            },
        ],
        "terms_and_conditions": """**TERMS**

1. Flower availability is subject to seasonal and market conditions.
2. Final design consultation required 6 weeks before event.
3. Setup and breakdown services included.
4. Fresh flowers are perishable; timing recommendations will be provided.""",
        "cancellation_policy": """**CANCELLATION**

- 60+ days: Deposit forfeited
- 30-60 days: 50% of total
- Under 30 days: 100% of total""",
        "default_deposit_percentage": 50,
        "default_payment_schedule": [
            {"percentage": 50, "description": "Deposit", "days_before_event": None},
            {"percentage": 50, "description": "Final Balance", "days_before_event": 14},
        ],
    },
    {
        "name": "DJ/Music Services Contract",
        "description": "Standard contract template for DJ and music entertainment services",
        "service_category": "dj",
        "sections": [
            {
                "id": str(ObjectId()),
                "title": "Agreement",
                "content": """**DJ SERVICES AGREEMENT**

Date: {{contract_date}}
Contract #: {{contract_number}}

**DJ/Entertainment:** {{vendor_name}}
**Email:** {{vendor_email}} | **Phone:** {{vendor_phone}}

**Clients:** {{couple_names}}
**Coordinator:** {{planner_name}} ({{planner_email}})""",
                "order": 1,
            },
            {
                "id": str(ObjectId()),
                "title": "Event Information",
                "content": """**Event Date:** {{wedding_date}}
**Venue:** {{wedding_venue}}
**Event Type:** Wedding Reception

**Service Hours:** [Start Time] - [End Time]""",
                "order": 2,
            },
            {
                "id": str(ObjectId()),
                "title": "Services",
                "content": """**Package Includes:**
- Professional DJ services
- Sound system appropriate for venue
- Wireless microphones for toasts/speeches
- Music consultation
- MC services as requested
- Dance floor lighting

**Playlist Planning:** DJ will coordinate with clients for must-play and do-not-play lists.""",
                "order": 3,
            },
            {
                "id": str(ObjectId()),
                "title": "Investment",
                "content": """**Total Fee:** ${{total_amount}}
**Deposit:** ${{deposit_amount}}

Overtime rate: $[X]/hour if event extends beyond contracted hours.""",
                "order": 4,
            },
        ],
        "terms_and_conditions": """**TERMS**

1. DJ arrives 1-2 hours early for setup.
2. Venue must provide adequate power supply.
3. Final timeline due 2 weeks before event.
4. Song requests can be submitted up to 1 week before event.""",
        "cancellation_policy": """**CANCELLATION**

Deposit is non-refundable. Cancellation within 30 days requires full payment.""",
        "default_deposit_percentage": 50,
        "default_payment_schedule": [
            {"percentage": 50, "description": "Deposit", "days_before_event": None},
            {"percentage": 50, "description": "Balance Due", "days_before_event": 7},
        ],
    },
    {
        "name": "Venue Rental Contract",
        "description": "Standard contract template for wedding venue rental",
        "service_category": "venue",
        "sections": [
            {
                "id": str(ObjectId()),
                "title": "Venue Rental Agreement",
                "content": """**VENUE RENTAL AGREEMENT**

Contract Date: {{contract_date}}
Contract #: {{contract_number}}

**Venue:** {{vendor_name}}
**Address:** {{vendor_address}}
**Contact:** {{vendor_email}} | {{vendor_phone}}

**Client:** {{couple_names}}
**Event Coordinator:** {{planner_name}}""",
                "order": 1,
            },
            {
                "id": str(ObjectId()),
                "title": "Event Details",
                "content": """**Event Date:** {{wedding_date}}
**Event Type:** Wedding Ceremony & Reception

**Rental Period:**
- Setup Access: [Time]
- Event: [Time] - [Time]
- Breakdown Completion: [Time]""",
                "order": 2,
            },
            {
                "id": str(ObjectId()),
                "title": "Venue Inclusions",
                "content": """**Rental Includes:**
- Exclusive use of designated spaces
- Tables and chairs (quantity specified)
- Parking facilities
- Restroom facilities
- On-site coordinator
- [Additional venue amenities]

**Guest Capacity:** [Maximum guests allowed]""",
                "order": 3,
            },
            {
                "id": str(ObjectId()),
                "title": "Investment & Terms",
                "content": """**Rental Fee:** ${{total_amount}}

**Payment Schedule:**
- Deposit to Reserve: ${{deposit_amount}}
- Balance Due: 30 days before event

**Security Deposit:** [Amount] - Refundable pending damage inspection""",
                "order": 4,
            },
        ],
        "terms_and_conditions": """**TERMS AND CONDITIONS**

1. **Insurance:** Client must provide event liability insurance.
2. **Vendors:** All outside vendors must be approved by venue.
3. **Noise:** Music must comply with local ordinances.
4. **Decorations:** No confetti, glitter, or items that may damage property.
5. **Catering:** [Venue catering requirements if any]""",
        "cancellation_policy": """**CANCELLATION**

- 180+ days: Deposit forfeited
- 90-180 days: 50% of rental fee
- Under 90 days: 100% of rental fee

Date changes subject to availability and may incur fees.""",
        "default_deposit_percentage": 50,
        "default_payment_schedule": [
            {
                "percentage": 50,
                "description": "Deposit to Reserve Date",
                "days_before_event": None,
            },
            {"percentage": 50, "description": "Final Balance", "days_before_event": 30},
        ],
    },
    {
        "name": "Videography Services Contract",
        "description": "Standard contract template for wedding videography services",
        "service_category": "videographer",
        "sections": [
            {
                "id": str(ObjectId()),
                "title": "Agreement",
                "content": """**VIDEOGRAPHY SERVICES AGREEMENT**

Date: {{contract_date}} | Contract #: {{contract_number}}

**Videographer:** {{vendor_name}}
**Contact:** {{vendor_email}} | {{vendor_phone}}

**Clients:** {{couple_names}}
**Planner:** {{planner_name}} ({{planner_company}})""",
                "order": 1,
            },
            {
                "id": str(ObjectId()),
                "title": "Event Details",
                "content": """**Wedding Date:** {{wedding_date}}
**Location:** {{wedding_venue}}

**Coverage:** [Hours of coverage]""",
                "order": 2,
            },
            {
                "id": str(ObjectId()),
                "title": "Deliverables",
                "content": """**Package Includes:**
- Full ceremony and reception coverage
- Highlight film (3-5 minutes)
- Full-length documentary edit
- Raw footage (optional)
- Online delivery via private link

**Delivery Timeline:** 12-16 weeks after event""",
                "order": 3,
            },
            {
                "id": str(ObjectId()),
                "title": "Investment",
                "content": """**Total:** ${{total_amount}}
**Deposit:** ${{deposit_amount}} (non-refundable)
**Balance:** Due 2 weeks before wedding""",
                "order": 4,
            },
        ],
        "terms_and_conditions": """**TERMS**

1. Copyright retained by videographer; client receives usage license.
2. Music licensing included for standard licensed tracks.
3. Client responsible for providing timeline and key moments list.
4. Equipment failure backup provisions in place.""",
        "cancellation_policy": """Deposit non-refundable. Full balance due if cancelled within 30 days.""",
        "default_deposit_percentage": 50,
        "default_payment_schedule": [
            {"percentage": 50, "description": "Deposit", "days_before_event": None},
            {"percentage": 50, "description": "Final Balance", "days_before_event": 14},
        ],
    },
    {
        "name": "Generic Vendor Services Contract",
        "description": "Flexible contract template for any vendor service",
        "service_category": "other",
        "sections": [
            {
                "id": str(ObjectId()),
                "title": "Service Agreement",
                "content": """**SERVICE AGREEMENT**

Date: {{contract_date}}
Contract #: {{contract_number}}

**Service Provider:**
{{vendor_name}}
{{vendor_email}} | {{vendor_phone}}

**Client:**
{{couple_names}}
Contact: {{planner_name}} ({{planner_email}})""",
                "order": 1,
            },
            {
                "id": str(ObjectId()),
                "title": "Event & Service Details",
                "content": """**Event Date:** {{wedding_date}}
**Location:** {{wedding_venue}}
**Service Type:** {{service_category}}

**Service Description:**
[Describe services to be provided]""",
                "order": 2,
            },
            {
                "id": str(ObjectId()),
                "title": "Investment",
                "content": """**Total Fee:** ${{total_amount}}
**Deposit:** ${{deposit_amount}}

**Payment Schedule:**
[Specify payment terms]""",
                "order": 3,
            },
        ],
        "terms_and_conditions": """[Add specific terms and conditions for this service]""",
        "cancellation_policy": """[Add cancellation policy]""",
        "default_deposit_percentage": 50,
        "default_payment_schedule": [
            {"percentage": 50, "description": "Deposit", "days_before_event": None},
            {"percentage": 50, "description": "Final Balance", "days_before_event": 14},
        ],
    },
]


async def seed_contract_templates():
    """Seed the database with default contract templates"""
    await init_database()

    collection = mongo.db["contract_templates"]

    print("Seeding contract templates...")

    for template_data in DEFAULT_TEMPLATES:
        # Check if template already exists
        existing = await collection.find_one(
            {"name": template_data["name"], "is_system_template": True}
        )

        if existing:
            print(f"  - Template '{template_data['name']}' already exists, skipping")
            continue

        template = {
            **template_data,
            "placeholders": STANDARD_PLACEHOLDERS,
            "is_system_template": True,
            "is_public": True,
            "is_active": True,
            "usage_count": 0,
            "created_by": "system@thespecialwedding.io",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

        result = await collection.insert_one(template)
        print(
            f"  + Created template: {template_data['name']} (ID: {result.inserted_id})"
        )

    # Create index
    await collection.create_index("service_category")
    await collection.create_index("is_system_template")
    await collection.create_index("created_by")

    print("\nContract template seeding complete!")

    # Count templates
    count = await collection.count_documents({"is_system_template": True})
    print(f"Total system templates: {count}")


if __name__ == "__main__":
    asyncio.run(seed_contract_templates())
