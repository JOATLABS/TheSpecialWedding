from app.api.email_reminders import build_individual_email_reminder_content


def test_custom_individual_reminder_email_keeps_reception_only_copy_generic():
    subject, html_content = build_individual_email_reminder_content(
        couple_names="Peace & Emmanuel",
        guest_name="Felix",
        rsvp_url="https://example.com/otp/verify?slug=reception&token=abc",
        custom_message="Reception starts at 6 PM. Please use the banquet entrance.",
        custom_subject="   ",
    )

    assert subject == "Reminder"
    assert ">Reminder</h1>" in html_content
    assert "Reception starts at 6 PM" in html_content
    assert "wedding" not in html_content.lower()
    assert "Reminder: Peace &amp; Emmanuel&#x27;s Wedding" not in html_content


def test_default_individual_reminder_email_keeps_wedding_framing():
    subject, html_content = build_individual_email_reminder_content(
        couple_names="Peace & Emmanuel",
        guest_name="Felix",
        rsvp_url="https://example.com/otp/verify?slug=wedding&token=abc",
    )

    assert subject == "Reminder: Peace & Emmanuel's Wedding"
    assert "Wedding Reminder" in html_content
    assert "upcoming wedding" in html_content
    assert "Powered by The Special Wedding" in html_content
