"""Static catalog of pre-built form templates available to every planner.

These power the in-app "create from template" flow and (Phase B) the
public marketing downloads. Each entry conforms to
``FormTemplateDefinition`` from ``app.api.forms`` and is validated at
import time by ``tests/backend/test_form_template_catalog.py``: every
field passes through ``FormField.model_validate``, every
``conditional_logic`` block passes the schema validator added in the
Wave 2 hardening pass, and every field id is unique within its template.

Adding a template
-----------------
1. Append a dict to ``FORM_TEMPLATES`` below.
2. Field types must be one of ``FieldType`` from ``app.models.form``
   (text / email / phone / number / date / textarea / select / radio /
   checkbox / file_upload / rating / scale).
3. Field ids must match ``^[a-zA-Z0-9_-]{1,64}$``.
4. ``conditional_logic`` (optional) must be of the form
   ``{"show_when": {"all": [...]}}`` or ``{"show_when": {"any": [...]}}``
   with conditions ``{"field_id", "operator", "value"}``.
5. Run the catalog test (``pytest tests/backend/test_form_template_catalog.py``)
   before committing.

The catalog is intentionally Python data, not JSON or YAML, so a typo
fails the type-check / unit tests at PR time rather than crashing
production at first request.
"""

from __future__ import annotations

from typing import Any, Dict, List


FORM_TEMPLATES: List[Dict[str, Any]] = [
    # =========================================================================
    # 1. Couple Intake Questionnaire — the first form a planner sends a couple
    # =========================================================================
    {
        "id": "couple_intake",
        "name": "Couple Intake Questionnaire",
        "description": (
            "Capture everything you need from a new couple in one go: names, "
            "vision, guest count, budget range, must-haves, and traditions to "
            "honour. Replaces the back-and-forth of the first three emails."
        ),
        "category": "intake",
        "fields": [
            {
                "id": "partner_one_name",
                "label": "Partner 1 — Full name",
                "type": "text",
                "required": True,
                "order": 1,
            },
            {
                "id": "partner_one_pronouns",
                "label": "Partner 1 — Pronouns",
                "type": "select",
                "required": False,
                "options": ["she/her", "he/him", "they/them", "Other (please share below)"],
                "order": 2,
            },
            {
                "id": "partner_two_name",
                "label": "Partner 2 — Full name",
                "type": "text",
                "required": True,
                "order": 3,
            },
            {
                "id": "partner_two_pronouns",
                "label": "Partner 2 — Pronouns",
                "type": "select",
                "required": False,
                "options": ["she/her", "he/him", "they/them", "Other (please share below)"],
                "order": 4,
            },
            {
                "id": "primary_email",
                "label": "Best email to reach you",
                "type": "email",
                "required": True,
                "order": 5,
            },
            {
                "id": "primary_phone",
                "label": "Best phone number",
                "type": "phone",
                "required": True,
                "order": 6,
            },
            {
                "id": "communication_preference",
                "label": "Preferred way to communicate",
                "type": "radio",
                "required": True,
                "options": ["Email", "Phone call", "Text message", "WhatsApp", "Video call"],
                "order": 7,
            },
            {
                "id": "wedding_date_target",
                "label": "Target wedding date (or 'flexible')",
                "type": "date",
                "required": False,
                "description": "Leave blank if you're still exploring dates.",
                "order": 8,
            },
            {
                "id": "city_or_region",
                "label": "Where do you want to get married?",
                "type": "text",
                "required": True,
                "placeholder": "City, region, or 'destination — open to ideas'",
                "order": 9,
            },
            {
                "id": "guest_count_estimate",
                "label": "Estimated guest count",
                "type": "select",
                "required": True,
                "options": [
                    "Under 50 — intimate",
                    "50–100",
                    "100–150",
                    "150–250",
                    "250+",
                    "Not sure yet",
                ],
                "order": 10,
            },
            {
                "id": "budget_range",
                "label": "Comfortable budget range",
                "type": "select",
                "required": True,
                "options": [
                    "Under $25,000",
                    "$25,000–$50,000",
                    "$50,000–$100,000",
                    "$100,000–$250,000",
                    "$250,000+",
                    "I'd rather discuss live",
                ],
                "order": 11,
            },
            {
                "id": "vision_three_words",
                "label": "Your wedding in three words",
                "type": "text",
                "required": False,
                "placeholder": "e.g. warm, garden-party, cinematic",
                "order": 12,
            },
            {
                "id": "must_have_moments",
                "label": "Must-have moments",
                "type": "textarea",
                "required": False,
                "placeholder": (
                    "First look? Surprise band? Specific tradition? "
                    "Anything that's non-negotiable to you."
                ),
                "order": 13,
            },
            {
                "id": "deal_breakers",
                "label": "Deal-breakers we should know about",
                "type": "textarea",
                "required": False,
                "placeholder": (
                    "Things you absolutely do not want — venue type, music, dress code, etc."
                ),
                "order": 14,
            },
            {
                "id": "cultural_traditions",
                "label": "Cultural or religious traditions to honour",
                "type": "textarea",
                "required": False,
                "placeholder": (
                    "Tell us about traditions you'd like incorporated so we can "
                    "build them into the planning from day one."
                ),
                "order": 15,
            },
            {
                "id": "inspiration_links",
                "label": "Inspiration links (Pinterest, Instagram, blogs)",
                "type": "textarea",
                "required": False,
                "placeholder": "One per line — links to anything that says 'this is us'.",
                "order": 16,
            },
            {
                "id": "how_you_met",
                "label": "How did you two meet?",
                "type": "textarea",
                "required": False,
                "description": "Optional, but it helps us craft a wedding that feels like *you*.",
                "order": 17,
            },
        ],
    },
    # =========================================================================
    # 2. Wedding Day Order of Events — the master timeline form
    # =========================================================================
    {
        "id": "order_of_events",
        "name": "Wedding Day Order of Events",
        "description": (
            "The minute-by-minute timeline shared with the couple, MC, and every "
            "vendor. Captures ceremony milestones, reception flow, and the "
            "song / readings cues so nothing is improvised on the day."
        ),
        "category": "timeline",
        "fields": [
            {
                "id": "ceremony_start_time",
                "label": "Ceremony start time",
                "type": "text",
                "required": True,
                "placeholder": "HH:MM (24h)",
                "order": 1,
            },
            {
                "id": "ceremony_location",
                "label": "Ceremony location",
                "type": "text",
                "required": True,
                "order": 2,
            },
            {
                "id": "officiant_name",
                "label": "Officiant",
                "type": "text",
                "required": True,
                "order": 3,
            },
            {
                "id": "processional_song",
                "label": "Processional song",
                "type": "text",
                "required": False,
                "placeholder": "Title — Artist",
                "order": 4,
            },
            {
                "id": "vows_style",
                "label": "Vows style",
                "type": "radio",
                "required": True,
                "options": [
                    "Traditional",
                    "Personally written",
                    "Mix of traditional and personal",
                    "Surprise — keeping each other in suspense",
                ],
                "order": 5,
            },
            {
                "id": "readings",
                "label": "Readings (one per line)",
                "type": "textarea",
                "required": False,
                "placeholder": "Reader's name — title of reading",
                "order": 6,
            },
            {
                "id": "ring_exchange_song",
                "label": "Ring exchange song (if any)",
                "type": "text",
                "required": False,
                "order": 7,
            },
            {
                "id": "recessional_song",
                "label": "Recessional song",
                "type": "text",
                "required": False,
                "order": 8,
            },
            {
                "id": "cocktail_hour_location",
                "label": "Cocktail hour location",
                "type": "text",
                "required": False,
                "order": 9,
            },
            {
                "id": "reception_entrance_song",
                "label": "Reception entrance song",
                "type": "text",
                "required": False,
                "order": 10,
            },
            {
                "id": "first_dance_song",
                "label": "First dance song",
                "type": "text",
                "required": True,
                "order": 11,
            },
            {
                "id": "parent_dances",
                "label": "Parent dances (e.g. mother–son, father–daughter)",
                "type": "textarea",
                "required": False,
                "placeholder": "Dance name — song — artist (one per line)",
                "order": 12,
            },
            {
                "id": "toast_roster",
                "label": "Toast / speech roster",
                "type": "textarea",
                "required": False,
                "placeholder": "Name — relationship — order",
                "order": 13,
            },
            {
                "id": "cake_cut_time",
                "label": "Cake cut — target time",
                "type": "text",
                "required": False,
                "placeholder": "HH:MM (24h)",
                "order": 14,
            },
            {
                "id": "bouquet_toss",
                "label": "Bouquet toss?",
                "type": "radio",
                "required": False,
                "options": ["Yes", "No", "Undecided"],
                "order": 15,
            },
            {
                "id": "send_off_type",
                "label": "Send-off",
                "type": "select",
                "required": False,
                "options": [
                    "Sparklers",
                    "Confetti / petals",
                    "Bubbles",
                    "Glow sticks",
                    "Quiet exit",
                    "Other (note below)",
                ],
                "order": 16,
            },
            {
                "id": "send_off_song",
                "label": "Send-off song",
                "type": "text",
                "required": False,
                "order": 17,
                "conditional_logic": {
                    "show_when": {
                        "all": [
                            {
                                "field_id": "send_off_type",
                                "operator": "not_equals",
                                "value": "Quiet exit",
                            }
                        ]
                    }
                },
            },
            {
                "id": "do_not_play",
                "label": "Do-NOT-play list",
                "type": "textarea",
                "required": False,
                "placeholder": "Songs / artists / genres your DJ should never put on.",
                "order": 18,
            },
        ],
    },
    # =========================================================================
    # 3. Guest Dietary & Access Survey — RSVP-adjacent, sent ~T-60 days
    # =========================================================================
    {
        "id": "guest_dietary_access",
        "name": "Guest Dietary & Access Survey",
        "description": (
            "Send to every confirmed guest 60 days out. Captures dietary needs, "
            "allergies, accessibility, and child-seat counts so the caterer and "
            "venue have the real numbers before final headcount."
        ),
        "category": "guest",
        "fields": [
            {
                "id": "guest_full_name",
                "label": "Your full name",
                "type": "text",
                "required": True,
                "order": 1,
            },
            {
                "id": "plus_one_name",
                "label": "Plus-one's full name (if any)",
                "type": "text",
                "required": False,
                "order": 2,
            },
            {
                "id": "diet_main",
                "label": "Diet",
                "type": "radio",
                "required": True,
                "options": [
                    "No restrictions",
                    "Vegetarian",
                    "Vegan",
                    "Pescatarian",
                    "Halal",
                    "Kosher",
                    "Gluten-free",
                    "Other (please describe below)",
                ],
                "order": 3,
            },
            {
                "id": "diet_other_detail",
                "label": "Tell us more about your dietary needs",
                "type": "textarea",
                "required": False,
                "placeholder": "Anything specific the kitchen should know.",
                "order": 4,
                "conditional_logic": {
                    "show_when": {
                        "all": [
                            {
                                "field_id": "diet_main",
                                "operator": "equals",
                                "value": "Other (please describe below)",
                            }
                        ]
                    }
                },
            },
            {
                "id": "allergies",
                "label": "Allergies (anaphylaxis-level or significant)",
                "type": "textarea",
                "required": False,
                "placeholder": (
                    "List anything that needs strict avoidance — nuts, shellfish, "
                    "dairy, etc. We share this list directly with the caterer."
                ),
                "order": 5,
            },
            {
                "id": "accessibility_needs",
                "label": "Accessibility needs",
                "type": "checkbox",
                "required": False,
                "options": [
                    "Step-free access",
                    "Reserved seating near the front",
                    "Sign-language interpretation",
                    "Quiet space available during reception",
                    "Other (please describe below)",
                ],
                "order": 6,
            },
            {
                "id": "accessibility_detail",
                "label": "Anything else we should arrange for you?",
                "type": "textarea",
                "required": False,
                "order": 7,
                "conditional_logic": {
                    "show_when": {
                        "any": [
                            {
                                "field_id": "accessibility_needs",
                                "operator": "contains",
                                "value": "Other (please describe below)",
                            }
                        ]
                    }
                },
            },
            {
                "id": "children_count",
                "label": "Number of children attending with you",
                "type": "number",
                "required": False,
                "description": "Helps us reserve high-chairs and kid-friendly meals.",
                "order": 8,
            },
            {
                "id": "song_request",
                "label": "Song you'd love to dance to (one per guest)",
                "type": "text",
                "required": False,
                "placeholder": "Title — Artist",
                "order": 9,
            },
        ],
    },
    # =========================================================================
    # 4. Vendor Onboarding Brief — sent at contract signing
    # =========================================================================
    {
        "id": "vendor_onboarding",
        "name": "Vendor Onboarding Brief",
        "description": (
            "The packet every newly-contracted vendor fills out: legal info, "
            "day-of contact, COI upload, setup / breakdown windows, deliverables. "
            "Eliminates the 'wait, we never got their COI' panic at week of."
        ),
        "category": "vendor",
        "fields": [
            {
                "id": "business_legal_name",
                "label": "Business legal name (as shown on invoices)",
                "type": "text",
                "required": True,
                "order": 1,
            },
            {
                "id": "primary_contact_name",
                "label": "Primary contact name",
                "type": "text",
                "required": True,
                "order": 2,
            },
            {
                "id": "primary_contact_email",
                "label": "Primary contact email",
                "type": "email",
                "required": True,
                "order": 3,
            },
            {
                "id": "primary_contact_phone",
                "label": "Primary contact phone",
                "type": "phone",
                "required": True,
                "order": 4,
            },
            {
                "id": "day_of_contact_phone",
                "label": "Day-of phone (the one you'll actually answer on the day)",
                "type": "phone",
                "required": True,
                "order": 5,
            },
            {
                "id": "ein_or_tax_id",
                "label": "EIN / Tax ID",
                "type": "text",
                "required": False,
                "description": "Required only if you'll invoice us directly.",
                "order": 6,
            },
            {
                "id": "coi_upload",
                "label": "Certificate of Insurance (COI)",
                "type": "file_upload",
                "required": True,
                "description": (
                    "Upload your COI naming the venue and the planner as "
                    "additional insureds. PDF or image, up to 10 MB."
                ),
                "order": 7,
            },
            {
                "id": "arrival_window",
                "label": "Earliest arrival on the day",
                "type": "text",
                "required": True,
                "placeholder": "HH:MM (24h)",
                "order": 8,
            },
            {
                "id": "setup_duration_minutes",
                "label": "Setup duration (minutes)",
                "type": "number",
                "required": True,
                "order": 9,
            },
            {
                "id": "breakdown_duration_minutes",
                "label": "Breakdown duration (minutes)",
                "type": "number",
                "required": True,
                "order": 10,
            },
            {
                "id": "team_size",
                "label": "Team members on-site",
                "type": "number",
                "required": True,
                "order": 11,
            },
            {
                "id": "power_water_needs",
                "label": "Power, water, or rigging needs",
                "type": "textarea",
                "required": False,
                "placeholder": (
                    "e.g. two 20A circuits within 30ft, water hookup for "
                    "espresso bar, rigging point for chandelier."
                ),
                "order": 12,
            },
            {
                "id": "deliverables_summary",
                "label": "Deliverables summary",
                "type": "textarea",
                "required": True,
                "placeholder": (
                    "Spell out exactly what we receive (number of photos, hours "
                    "of coverage, pieces of cake, etc.) so there's no ambiguity."
                ),
                "order": 13,
            },
            {
                "id": "additional_notes",
                "label": "Anything else the planner should know?",
                "type": "textarea",
                "required": False,
                "order": 14,
            },
        ],
    },
    # =========================================================================
    # 5. Photographer / Videographer Shot List — couple → photo vendor, T-21
    # =========================================================================
    {
        "id": "photo_video_shot_list",
        "name": "Photographer & Videographer Shot List",
        "description": (
            "The single source of truth for what the couple wants captured: "
            "family combinations, must-have moments, getting-ready locations, "
            "people to flag — and people to avoid in frame."
        ),
        "category": "creative",
        "fields": [
            {
                "id": "getting_ready_location_partner_one",
                "label": "Getting-ready location — Partner 1",
                "type": "text",
                "required": True,
                "order": 1,
            },
            {
                "id": "getting_ready_location_partner_two",
                "label": "Getting-ready location — Partner 2",
                "type": "text",
                "required": True,
                "order": 2,
            },
            {
                "id": "first_look",
                "label": "First look?",
                "type": "radio",
                "required": True,
                "options": [
                    "Yes — with each other",
                    "Yes — with parents / wedding party",
                    "No — saving for the aisle",
                ],
                "order": 3,
            },
            {
                "id": "first_look_location",
                "label": "First look location (if doing one)",
                "type": "text",
                "required": False,
                "order": 4,
                "conditional_logic": {
                    "show_when": {
                        "any": [
                            {
                                "field_id": "first_look",
                                "operator": "equals",
                                "value": "Yes — with each other",
                            },
                            {
                                "field_id": "first_look",
                                "operator": "equals",
                                "value": "Yes — with parents / wedding party",
                            },
                        ]
                    }
                },
            },
            {
                "id": "family_combinations",
                "label": "Family portrait combinations (one per line)",
                "type": "textarea",
                "required": True,
                "placeholder": (
                    "e.g. Couple + Partner 1's parents\\n"
                    "Couple + Partner 2's grandparents\\n"
                    "Couple + Partner 1's siblings"
                ),
                "description": (
                    "List every grouping you want. The photographer reads this "
                    "out loud during family portraits to keep things moving."
                ),
                "order": 5,
            },
            {
                "id": "must_have_moments_visual",
                "label": "Must-have moments (anything beyond the obvious)",
                "type": "textarea",
                "required": False,
                "placeholder": (
                    "e.g. Grandmother seeing the dress, surprise dance with siblings, "
                    "ring shot with great-grandfather's ring."
                ),
                "order": 6,
            },
            {
                "id": "do_not_photograph",
                "label": "People to NOT photograph (or to handle carefully)",
                "type": "textarea",
                "required": False,
                "placeholder": "Names — and a one-line note on how to handle.",
                "order": 7,
            },
            {
                "id": "shot_inspiration",
                "label": "Reference / inspiration images",
                "type": "file_upload",
                "required": False,
                "description": (
                    "Upload a single PDF or image collage. Easier than 30 "
                    "Pinterest links — gives the photographer one document to scan."
                ),
                "order": 8,
            },
            {
                "id": "delivery_format_preference",
                "label": "Preferred delivery format",
                "type": "checkbox",
                "required": False,
                "options": [
                    "High-res digital gallery",
                    "Printed album",
                    "USB drive",
                    "Highlight reel (video)",
                    "Full ceremony video",
                    "Social-cuts package",
                ],
                "order": 9,
            },
            {
                "id": "social_share_consent",
                "label": "Are you OK with the photographer sharing photos online?",
                "type": "radio",
                "required": True,
                "options": [
                    "Yes — anywhere",
                    "Yes — but please ask before sharing identifiable kids",
                    "Yes — but only after we've shared first",
                    "No — private only",
                ],
                "order": 10,
            },
        ],
    },
    # =========================================================================
    # 6. Bridal / Wedding Party Logistics — sent T-14 days
    # =========================================================================
    {
        "id": "bridal_party_logistics",
        "name": "Wedding Party Logistics",
        "description": (
            "One form per member of the wedding party. Hair / makeup slots, "
            "attire pickup, transport groups, after-party RSVPs — the day-of "
            "details that fall through the cracks otherwise."
        ),
        "category": "bridal_party",
        "fields": [
            {
                "id": "member_full_name",
                "label": "Your full name",
                "type": "text",
                "required": True,
                "order": 1,
            },
            {
                "id": "member_role",
                "label": "Role in the wedding party",
                "type": "select",
                "required": True,
                "options": [
                    "Maid / Matron of honour",
                    "Best person",
                    "Bridesmaid",
                    "Groomsperson",
                    "Flower attendant",
                    "Ring bearer",
                    "Reader",
                    "Officiant",
                    "Other",
                ],
                "order": 2,
            },
            {
                "id": "member_phone",
                "label": "Phone (we'll use this for the day-of group thread)",
                "type": "phone",
                "required": True,
                "order": 3,
            },
            {
                "id": "hair_makeup_slot_preference",
                "label": "Hair & makeup — preferred slot",
                "type": "select",
                "required": False,
                "options": [
                    "First slot",
                    "Mid-morning",
                    "Late morning (just before pictures)",
                    "I'm doing my own — skip me",
                    "No preference",
                ],
                "order": 4,
            },
            {
                "id": "attire_pickup_status",
                "label": "Attire pickup status",
                "type": "radio",
                "required": True,
                "options": [
                    "Picked up — final fit confirmed",
                    "Picked up — fit not yet confirmed",
                    "Not picked up yet",
                ],
                "order": 5,
            },
            {
                "id": "attire_blocker",
                "label": "What's blocking pickup?",
                "type": "textarea",
                "required": False,
                "order": 6,
                "conditional_logic": {
                    "show_when": {
                        "all": [
                            {
                                "field_id": "attire_pickup_status",
                                "operator": "equals",
                                "value": "Not picked up yet",
                            }
                        ]
                    }
                },
            },
            {
                "id": "transport_group",
                "label": "Day-of transport — which group are you in?",
                "type": "select",
                "required": True,
                "options": [
                    "Couple's car",
                    "Wedding party shuttle",
                    "Driving myself",
                    "Riding with family",
                ],
                "order": 7,
            },
            {
                "id": "dietary_for_suite",
                "label": "Dietary needs for the getting-ready suite",
                "type": "textarea",
                "required": False,
                "placeholder": "Allergies / preferences — kept on the suite catering brief.",
                "order": 8,
            },
            {
                "id": "after_party_attending",
                "label": "After-party — coming?",
                "type": "radio",
                "required": False,
                "options": ["Yes", "No", "Trying to make it"],
                "order": 9,
            },
        ],
    },
    # =========================================================================
    # 7. Vendor Performance Review — internal, T+30 days
    # =========================================================================
    {
        "id": "vendor_performance_review",
        "name": "Vendor Performance Review (Internal)",
        "description": (
            "Planner-internal review of each vendor after the wedding. Feeds "
            "your own rolodex — would-rebook flag, tight scoring on the dimensions "
            "that matter, plus notes that surface if you ever assign them again."
        ),
        "category": "vendor",
        "fields": [
            {
                "id": "vendor_business_name",
                "label": "Vendor business name",
                "type": "text",
                "required": True,
                "order": 1,
            },
            {
                "id": "vendor_category",
                "label": "Category",
                "type": "select",
                "required": True,
                "options": [
                    "Photographer",
                    "Videographer",
                    "Florist",
                    "Caterer",
                    "Venue",
                    "DJ",
                    "MC",
                    "Band",
                    "Officiant",
                    "Decorator",
                    "Cake / Bakery",
                    "Hair & Makeup",
                    "Transportation",
                    "Stationery",
                    "Rentals",
                    "Lighting",
                    "Photo Booth",
                    "Other",
                ],
                "order": 2,
            },
            {
                "id": "communication_quality",
                "label": "Communication quality",
                "type": "rating",
                "required": True,
                "description": "Pre-wedding responsiveness and clarity.",
                "order": 3,
            },
            {
                "id": "punctuality",
                "label": "Punctuality on the day",
                "type": "rating",
                "required": True,
                "order": 4,
            },
            {
                "id": "deliverables_quality",
                "label": "Deliverables quality",
                "type": "rating",
                "required": True,
                "order": 5,
            },
            {
                "id": "professionalism",
                "label": "Professionalism with couple & guests",
                "type": "rating",
                "required": True,
                "order": 6,
            },
            {
                "id": "value_for_price",
                "label": "Value for price paid",
                "type": "rating",
                "required": True,
                "order": 7,
            },
            {
                "id": "would_rebook",
                "label": "Would you rebook for another wedding?",
                "type": "radio",
                "required": True,
                "options": [
                    "Yes — first call",
                    "Yes — for the right couple",
                    "Maybe — depends",
                    "No",
                ],
                "order": 8,
            },
            {
                "id": "rebook_caveat",
                "label": "What's the caveat?",
                "type": "textarea",
                "required": False,
                "order": 9,
                "conditional_logic": {
                    "show_when": {
                        "any": [
                            {
                                "field_id": "would_rebook",
                                "operator": "equals",
                                "value": "Yes — for the right couple",
                            },
                            {
                                "field_id": "would_rebook",
                                "operator": "equals",
                                "value": "Maybe — depends",
                            },
                        ]
                    }
                },
            },
            {
                "id": "issues_to_flag",
                "label": "Issues worth flagging in our internal directory",
                "type": "textarea",
                "required": False,
                "placeholder": (
                    "Anything a future planner should know before assigning them "
                    "(behavioural, payment terms, scope creep, no-shows, etc.)."
                ),
                "order": 10,
            },
            {
                "id": "highlights",
                "label": "Standout positives",
                "type": "textarea",
                "required": False,
                "order": 11,
            },
        ],
    },
    # =========================================================================
    # 8. Engagement Session Brief — pre-wedding, couple → photo vendor
    # =========================================================================
    {
        "id": "engagement_session_brief",
        "name": "Engagement Session Brief",
        "description": (
            "Quick form for the couple to scope the engagement shoot: locations, "
            "outfits, vibe, must-include shots. Saves a 45-minute call."
        ),
        "category": "creative",
        "fields": [
            {
                "id": "session_target_date",
                "label": "Target date",
                "type": "date",
                "required": True,
                "order": 1,
            },
            {
                "id": "primary_location",
                "label": "Primary location",
                "type": "text",
                "required": True,
                "placeholder": "Park, neighbourhood, venue — be specific.",
                "order": 2,
            },
            {
                "id": "secondary_location",
                "label": "Secondary location (optional)",
                "type": "text",
                "required": False,
                "order": 3,
            },
            {
                "id": "outfit_count",
                "label": "How many outfit changes are you planning?",
                "type": "select",
                "required": True,
                "options": ["1", "2", "3+"],
                "order": 4,
            },
            {
                "id": "props",
                "label": "Props you're bringing",
                "type": "textarea",
                "required": False,
                "placeholder": "Champagne, blanket, pet, vintage car, etc.",
                "order": 5,
            },
            {
                "id": "must_include_shots",
                "label": "Must-include shots",
                "type": "textarea",
                "required": False,
                "placeholder": "Specific frames or compositions you want to come home with.",
                "order": 6,
            },
            {
                "id": "energy_word",
                "label": "Describe the vibe in one word",
                "type": "text",
                "required": False,
                "placeholder": "playful, cinematic, candid, dramatic…",
                "order": 7,
            },
            {
                "id": "save_the_date_use",
                "label": "Will you use these for save-the-dates?",
                "type": "radio",
                "required": False,
                "options": ["Yes", "No", "Maybe — depends on the gallery"],
                "order": 8,
            },
        ],
    },
    # =========================================================================
    # 9. Day-Of Emergency Contact Sheet — sent T-7 days
    # =========================================================================
    {
        "id": "day_of_emergency_contacts",
        "name": "Day-Of Emergency Contact Sheet",
        "description": (
            "One short form per critical contact. Combine the responses into the "
            "single laminated sheet that lives on every vendor's clipboard and "
            "in the couple's getting-ready suite."
        ),
        "category": "timeline",
        "fields": [
            {
                "id": "contact_full_name",
                "label": "Full name",
                "type": "text",
                "required": True,
                "order": 1,
            },
            {
                "id": "contact_role",
                "label": "Role on the day",
                "type": "select",
                "required": True,
                "options": [
                    "Couple — Partner 1",
                    "Couple — Partner 2",
                    "Planner / Coordinator",
                    "Maid / Matron of honour",
                    "Best person",
                    "Officiant",
                    "Photographer",
                    "Videographer",
                    "Caterer (lead)",
                    "Florist (lead)",
                    "DJ / MC",
                    "Venue manager",
                    "Family — Partner 1",
                    "Family — Partner 2",
                    "Other",
                ],
                "order": 2,
            },
            {
                "id": "contact_phone",
                "label": "Phone (the one you'll actually answer)",
                "type": "phone",
                "required": True,
                "order": 3,
            },
            {
                "id": "contact_email",
                "label": "Email",
                "type": "email",
                "required": False,
                "order": 4,
            },
            {
                "id": "first_call_window",
                "label": "Window during which you'll be reachable on the day",
                "type": "text",
                "required": False,
                "placeholder": "e.g. 09:00–22:00",
                "order": 5,
            },
            {
                "id": "backup_contact_name",
                "label": "Backup contact (if you go silent)",
                "type": "text",
                "required": False,
                "order": 6,
            },
            {
                "id": "backup_contact_phone",
                "label": "Backup contact phone",
                "type": "phone",
                "required": False,
                "order": 7,
            },
            {
                "id": "notes_for_planner",
                "label": "Anything else the planner should know?",
                "type": "textarea",
                "required": False,
                "placeholder": "Preferred contact method, allergies if you'll eat on-site, etc.",
                "order": 8,
            },
        ],
    },
]


__all__ = ["FORM_TEMPLATES"]
