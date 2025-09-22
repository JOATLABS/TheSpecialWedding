"""
Test factories for creating test data
"""
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from bson import ObjectId
from faker import Faker
import factory
from factory import Factory, SubFactory, LazyAttribute, LazyFunction

fake = Faker()


class ObjectIdFactory(factory.Factory):
    """Factory for generating ObjectIds"""
    class Meta:
        model = ObjectId
    
    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        return ObjectId()


class UserFactory(Factory):
    """Factory for creating user objects"""
    class Meta:
        model = dict
    
    _id = LazyFunction(lambda: ObjectId())
    email = LazyAttribute(lambda obj: fake.email())
    password_hash = "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW"  # "secret"
    role = "wedding_planner"
    is_active = True
    email_verified = True
    registration_source = "public_signup"
    created_at = LazyFunction(datetime.utcnow)
    updated_at = LazyFunction(datetime.utcnow)
    
    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        return kwargs


class AdminUserFactory(UserFactory):
    """Factory for creating admin user objects"""
    role = "admin"
    hashed_password = "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW"
    
    # Remove password_hash for admin users
    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        if 'password_hash' in kwargs:
            del kwargs['password_hash']
        return kwargs


class SubscriptionPlanFactory(Factory):
    """Factory for creating subscription plan objects"""
    class Meta:
        model = dict
    
    _id = LazyFunction(lambda: ObjectId())
    name = LazyAttribute(lambda obj: fake.random_element(["Starter", "Professional", "Enterprise"]))
    price = LazyAttribute(lambda obj: fake.random_number(digits=2))
    currency = "USD"
    billing_period = "monthly"
    limits = LazyAttribute(lambda obj: {
        "weddings": fake.random_int(min=1, max=50),
        "ai_credits": fake.random_int(min=100, max=5000),
        "vendor_seats": fake.random_int(min=1, max=20),
        "staff_seats": fake.random_int(min=1, max=50)
    })
    features = LazyAttribute(lambda obj: {
        "ai_tools": fake.boolean(),
        "advanced_reporting": fake.boolean(),
        "white_label": fake.boolean(),
        "custom_integrations": fake.boolean(),
        "multi_user_collaboration": fake.boolean()
    })
    is_active = True
    created_at = LazyFunction(datetime.utcnow)
    
    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        return kwargs


class SubscriptionFactory(Factory):
    """Factory for creating subscription objects"""
    class Meta:
        model = dict
    
    plan_id = LazyFunction(lambda: ObjectId())
    status = "active"
    start_date = LazyFunction(lambda: datetime.utcnow() - timedelta(days=10))
    end_date = LazyFunction(lambda: datetime.utcnow() + timedelta(days=20))
    trial_end = None
    current_usage = LazyAttribute(lambda obj: {
        "weddings": 0,
        "ai_credits": 0,
        "vendor_seats": 0,
        "staff_seats": 0
    })
    
    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        return kwargs


class WeddingFactory(Factory):
    """Factory for creating wedding objects"""
    class Meta:
        model = dict
    
    _id = LazyFunction(lambda: ObjectId())
    title = LazyAttribute(lambda obj: f"{fake.first_name()} & {fake.first_name()}'s Wedding")
    slug = LazyAttribute(lambda obj: fake.slug())
    date = LazyAttribute(lambda obj: fake.future_date())
    venue = LazyAttribute(lambda obj: fake.company())
    venue_address = LazyAttribute(lambda obj: fake.address())
    planner_id = LazyFunction(lambda: ObjectId())
    settings = LazyAttribute(lambda obj: {
        "rsvp_enabled": True,
        "gallery_enabled": True,
        "forms_enabled": True,
        "theme": "elegant",
        "color_scheme": {
            "primary": "#4A90E2",
            "secondary": "#F5A623"
        }
    })
    created_at = LazyFunction(datetime.utcnow)
    updated_at = LazyFunction(datetime.utcnow)
    
    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        return kwargs


class GuestFactory(Factory):
    """Factory for creating guest objects"""
    class Meta:
        model = dict
    
    _id = LazyFunction(lambda: ObjectId())
    wedding_id = LazyFunction(lambda: ObjectId())
    first_name = LazyAttribute(lambda obj: fake.first_name())
    last_name = LazyAttribute(lambda obj: fake.last_name())
    email = LazyAttribute(lambda obj: fake.email())
    phone = LazyAttribute(lambda obj: fake.phone_number())
    invitation_code = LazyAttribute(lambda obj: fake.uuid4()[:8].upper())
    table_number = LazyAttribute(lambda obj: fake.random_int(min=1, max=20))
    party_size = LazyAttribute(lambda obj: fake.random_int(min=1, max=4))
    dietary_restrictions = LazyAttribute(lambda obj: fake.random_element([None, "Vegetarian", "Vegan", "Gluten-free"]))
    rsvp_status = "pending"
    checked_in = False
    created_at = LazyFunction(datetime.utcnow)
    updated_at = LazyFunction(datetime.utcnow)
    
    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        return kwargs


class FormFactory(Factory):
    """Factory for creating form objects"""
    class Meta:
        model = dict
    
    _id = LazyFunction(lambda: ObjectId())
    wedding_id = LazyFunction(lambda: ObjectId())
    title = LazyAttribute(lambda obj: fake.sentence(nb_words=3))
    description = LazyAttribute(lambda obj: fake.text(max_nb_chars=200))
    fields = LazyAttribute(lambda obj: [
        {
            "id": fake.uuid4(),
            "type": "text",
            "label": "Full Name",
            "required": True,
            "placeholder": "Enter your full name"
        },
        {
            "id": fake.uuid4(),
            "type": "email",
            "label": "Email Address",
            "required": True,
            "placeholder": "your@email.com"
        },
        {
            "id": fake.uuid4(),
            "type": "select",
            "label": "Meal Choice",
            "required": False,
            "options": ["Chicken", "Fish", "Vegetarian"]
        }
    ])
    is_active = True
    submission_count = 0
    created_at = LazyFunction(datetime.utcnow)
    updated_at = LazyFunction(datetime.utcnow)
    
    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        return kwargs


class FormResponseFactory(Factory):
    """Factory for creating form response objects"""
    class Meta:
        model = dict
    
    _id = LazyFunction(lambda: ObjectId())
    form_id = LazyFunction(lambda: ObjectId())
    wedding_id = LazyFunction(lambda: ObjectId())
    guest_id = LazyFunction(lambda: ObjectId())
    responses = LazyAttribute(lambda obj: {
        fake.uuid4(): fake.name(),
        fake.uuid4(): fake.email(),
        fake.uuid4(): fake.random_element(["Chicken", "Fish", "Vegetarian"])
    })
    submitted_at = LazyFunction(datetime.utcnow)
    ip_address = LazyAttribute(lambda obj: fake.ipv4())
    user_agent = LazyAttribute(lambda obj: fake.user_agent())
    
    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        return kwargs


# Helper functions for creating test data
def create_user_with_subscription(
    subscription_plan: Optional[Dict[str, Any]] = None,
    **user_kwargs
) -> Dict[str, Any]:
    """Create a user with a subscription"""
    if subscription_plan is None:
        subscription_plan = SubscriptionPlanFactory()
    
    subscription = SubscriptionFactory(plan_id=subscription_plan["_id"])
    user = UserFactory(subscription=subscription, **user_kwargs)
    return user


def create_wedding_with_guests(
    num_guests: int = 10,
    planner_id: Optional[ObjectId] = None,
    **wedding_kwargs
) -> tuple[Dict[str, Any], list[Dict[str, Any]]]:
    """Create a wedding with multiple guests"""
    if planner_id is None:
        planner_id = ObjectId()
    
    wedding = WeddingFactory(planner_id=planner_id, **wedding_kwargs)
    guests = [
        GuestFactory(wedding_id=wedding["_id"])
        for _ in range(num_guests)
    ]
    
    return wedding, guests


def create_form_with_responses(
    num_responses: int = 5,
    wedding_id: Optional[ObjectId] = None,
    **form_kwargs
) -> tuple[Dict[str, Any], list[Dict[str, Any]]]:
    """Create a form with multiple responses"""
    if wedding_id is None:
        wedding_id = ObjectId()
    
    form = FormFactory(wedding_id=wedding_id, **form_kwargs)
    responses = [
        FormResponseFactory(form_id=form["_id"], wedding_id=wedding_id)
        for _ in range(num_responses)
    ]
    
    # Update submission count
    form["submission_count"] = num_responses
    
    return form, responses