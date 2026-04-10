// SMS Compliance Disclaimer Templates
// All disclaimers comply with toll-free SMS verification requirements

export const SMS_DISCLAIMERS = {
  // Main opt-in disclaimer (required on all opt-in forms)
  mainOptInDisclaimer: (weddingName: string) => `
You are subscribing to wedding reminders from ${weddingName}.
Reply STOP to opt out. Reply HELP for help.
Standard message and data rates may apply. Message frequency may vary.
By providing your phone number, you consent to receive automated text messages from ${weddingName}.
Consent is not a condition of any purchase.
  `.trim(),

  // Short version for space-constrained forms
  shortOptInDisclaimer: (weddingName: string) => `
By subscribing, you agree to receive automated texts from ${weddingName}.
Reply STOP to opt out. Msg&data rates may apply.
  `.trim(),

  // Welcome message (sent after opt-in)
  welcomeMessage: (weddingName: string) => `
Welcome! You're subscribed to reminders for ${weddingName}'s wedding.
Reply STOP to opt out. Reply HELP for help. Msg&data rates may apply.
  `.trim(),

  // Help message response - supportPhone is optional, provided by the assigned planner
  helpMessage: (weddingName: string, supportPhone?: string) => {
    if (supportPhone) {
      return `Wedding reminders from ${weddingName}. Reply STOP to unsubscribe. For support, call ${supportPhone}. Msg&data rates may apply.`.trim();
    }
    return `Wedding reminders from ${weddingName}. Reply STOP to unsubscribe. For support, visit thespecialwedding.io/support. Msg&data rates may apply.`.trim();
  },

  // Stop confirmation message
  stopConfirmation: (weddingName: string) => `
You have been unsubscribed from ${weddingName} SMS notifications.
Reply START to resubscribe.
  `.trim(),

  // Re-subscription message
  resubscribeMessage: (weddingName: string) => `
Welcome back! You're subscribed to reminders for ${weddingName}.
Reply STOP to opt out. Msg&data rates may apply.
  `.trim(),

  // Privacy policy required text
  privacyPolicyRequired: `
We will not share or sell your mobile information with third parties for marketing purposes.
  `.trim(),

  // Terms of service required elements
  termsRequired: [
    "Message frequency may vary",
    "Standard message and data rates may apply",
    "Reply STOP to cancel at any time",
    "Reply HELP for assistance",
    "Consent is not required for any purchase",
    "Messages are automated"
  ],

  // Transactional message footer (include in all messages)
  messageFooter: "Reply STOP to opt out",

  // Marketing message footer (if sending promotional content)
  marketingFooter: "Reply STOP to opt out of marketing messages",

  // Reminder message template
  reminderTemplate: (eventType: string, eventDate: string, weddingName: string) => `
Reminder: ${eventType} for ${weddingName} is on ${eventDate}.
Reply STOP to opt out.
  `.trim(),

  // RSVP invitation template
  rsvpInvitationTemplate: (guestName: string, weddingName: string) => `
Hi ${guestName}! You're invited to ${weddingName}'s wedding.
Please RSVP at [RSVP_LINK].
Reply STOP to opt out.
  `.trim()
};

// Opt-in form configuration
export const OPT_IN_FORM_CONFIG = {
  // Checkbox must be unchecked by default
  defaultChecked: false,

  // Checkboxes must be optional (not required)
  required: false,

  // Must have separate checkboxes for different message types
  messageTypes: {
    transactional: {
      label: "Wedding Reminders & Updates",
      description: "Receive important reminders and updates about wedding events"
    },
    marketing: {
      label: "Special Offers (Optional)",
      description: "Receive special offers and promotional messages from wedding vendors"
    }
  }
};

// Sample HTML for compliant opt-in form
export const SAMPLE_OPT_IN_HTML = `
<form>
  <h3>SMS Notifications</h3>

  <!-- Phone number input -->
  <input type="tel" name="phone" placeholder="(555) 123-4567" required />

  <!-- Transactional messages checkbox (unchecked by default) -->
  <label>
    <input type="checkbox" name="sms_transactional" value="true" />
    <span>Receive wedding reminders and updates from [Wedding Name]</span>
  </label>

  <!-- Marketing messages checkbox (unchecked by default, optional) -->
  <label>
    <input type="checkbox" name="sms_marketing" value="true" />
    <span>Receive special offers and promotional messages (optional)</span>
  </label>

  <!-- Required disclaimer -->
  <div class="disclaimer">
    <p>
      You are subscribing to wedding reminders from [Wedding Name].
      Reply STOP to opt out. Reply HELP for help.
      Standard message and data rates may apply. Message frequency may vary.
    </p>
    <p>
      By checking the box(es) above and submitting this form, you consent to receive
      automated text messages from [Wedding Name] at the phone number provided.
      Consent is not a condition of any purchase.
    </p>
    <p>
      <a href="/terms">Terms & Conditions</a> |
      <a href="/privacy">Privacy Policy</a>
    </p>
  </div>

  <button type="submit">Subscribe to SMS Notifications</button>
</form>
`;

// Webhook response templates
export const WEBHOOK_RESPONSES = {
  STOP: {
    keywords: ["STOP", "UNSUBSCRIBE", "CANCEL", "END", "QUIT"],
    action: "opt_out",
    response: SMS_DISCLAIMERS.stopConfirmation
  },
  HELP: {
    keywords: ["HELP", "INFO"],
    action: "send_help",
    response: SMS_DISCLAIMERS.helpMessage
  },
  START: {
    keywords: ["START", "UNSTOP", "YES", "SUBSCRIBE"],
    action: "opt_in",
    response: SMS_DISCLAIMERS.resubscribeMessage
  }
};

// Validation functions
export function validateOptInForm(formData: any): string[] {
  const errors: string[] = [];

  if (!formData.phone) {
    errors.push("Phone number is required");
  }

  if (!formData.smsTransactional && !formData.smsMarketing) {
    errors.push("At least one message type must be selected");
  }

  if (formData.defaultChecked === true) {
    errors.push("Checkboxes must be unchecked by default");
  }

  return errors;
}

// Format message with compliance footer
export function formatSmsMessage(message: string, isMarketing: boolean = false): string {
  const footer = isMarketing ? SMS_DISCLAIMERS.marketingFooter : SMS_DISCLAIMERS.messageFooter;
  return `${message}\n${footer}`;
}
