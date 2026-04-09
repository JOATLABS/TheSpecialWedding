import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';

const ROOT = '/Users/emmanuelakinwale/Desktop/WeddingWebApp';
const PYTHON = `${ROOT}/.venv/bin/python`;

const FIXTURE = {
  weddingId: 'wedding_1775700014748',
  plannerEmail: 'test_planner2@thespecialwedding.io',
  plannerPassword: 'testPass123!',
  plannerId: '69d705077174afc30187a408',
  coupleEmail: 'qa_pr2_frontend@thespecialwedding.io',
  couplePassword: 'QaCouplePass123!!',
  eventLabel: 'PR2 Timeline Event',
  formTitle: 'PR2 Archived QA Form',
  meetingTitle: 'PR2 Planning Session',
} as const;

type CoupleState = 'active' | 'archived' | 'owner_cancelled';

function runPythonJson(code: string) {
  const raw = execFileSync(PYTHON, ['-c', code], {
    cwd: ROOT,
    encoding: 'utf8',
  });
  return JSON.parse(raw.trim() || '{}');
}

function seedFixture(state: CoupleState) {
  const payload = JSON.stringify({ ...FIXTURE, state });
  const code = `
import json
from datetime import datetime, timedelta, timezone
from bson import ObjectId
from pymongo import MongoClient
from app.utils.auth_utils import get_password_hash

fixture = json.loads(${JSON.stringify(payload)})
client = MongoClient("mongodb://localhost:27017")
db = client["wedding"]
now = datetime.now(timezone.utc)

db["couple_users"].delete_many({
    "email": {"$in": [fixture["coupleEmail"], "qa_pr2_couple@thespecialwedding.io"]},
    "wedding_id": fixture["weddingId"],
})
db["forms"].delete_many({"title": fixture["formTitle"], "wedding_id": fixture["weddingId"]})
db["form_submissions"].delete_many({"submitted_by": fixture["coupleEmail"], "wedding_id": fixture["weddingId"]})
db["planner_tasks"].delete_many({"title": fixture["meetingTitle"], "wedding_id": fixture["weddingId"]})

form_id = ObjectId()
meeting_id = ObjectId()

events = list(db["weddings"].find_one({"_id": fixture["weddingId"]}, {"events": 1}).get("events", []))
events = [event for event in events if event.get("custom_type_label") != fixture["eventLabel"]]
events.append({
    "type": "custom",
    "custom_type_label": fixture["eventLabel"],
    "date": (now + timedelta(days=1)).date().isoformat(),
    "details": {
        "time": "4:00 PM",
        "venue_name": "QA Ballroom",
        "location": "QA Suite",
        "attire": "Formal"
    },
    "event_notes": [
        {
            "id": "pr2-event-note",
            "author_role": "couple",
            "author_name": "QA & Couple",
            "text": "Existing archived event note",
            "status": "pending",
            "created_at": now.isoformat(),
        }
    ],
    "order_of_events": [
        {
            "id": "pr2-item-1",
            "title": "Grand entrance",
            "description": "Couple entrance for verification",
            "time": "4:30 PM",
            "order": 0,
            "duration_minutes": 10,
            "notes": [
                {
                    "id": "pr2-item-note",
                    "author_role": "couple",
                    "author_name": "QA & Couple",
                    "text": "Archived item note",
                    "status": "pending",
                    "created_at": now.isoformat(),
                }
            ],
        }
    ],
})
db["weddings"].update_one({"_id": fixture["weddingId"]}, {"$set": {"events": events}})

db["forms"].insert_one({
    "_id": form_id,
    "title": fixture["formTitle"],
    "description": "Temporary QA form for PR2 lifecycle verification.",
    "wedding_id": fixture["weddingId"],
    "created_by": fixture["plannerEmail"],
    "shared_with_couple": True,
    "fields": [
        {"id": "song", "label": "Entrance song", "type": "text", "required": False},
        {"id": "notes", "label": "Planner notes", "type": "textarea", "required": False},
    ],
    "created_at": now,
    "updated_at": now,
})

db["form_submissions"].insert_one({
    "form_id": str(form_id),
    "wedding_id": fixture["weddingId"],
    "submitted_by": fixture["coupleEmail"],
    "submitted_by_name": "QA & Couple",
    "submitted_by_type": "couple",
    "responses": {
        "song": "Best Day Ever",
        "notes": "Ready for archived verification",
    },
    "submitted_at": now,
    "updated_at": now,
})

db["planner_tasks"].insert_one({
    "_id": meeting_id,
    "wedding_id": fixture["weddingId"],
    "owner_planner_id": fixture["plannerId"],
    "owner_planner_email": fixture["plannerEmail"],
    "planner_email": fixture["plannerEmail"],
    "title": fixture["meetingTitle"],
    "description": "Temporary PR2 meeting for browser verification.",
    "category": "meeting",
    "status": "scheduled",
    "start_date": now + timedelta(days=1),
    "end_date": now + timedelta(days=1, hours=1),
    "conference_url": "https://meet.example.com/pr2-playwright",
    "couple_attendee_emails": [fixture["coupleEmail"]],
    "is_recurring": False,
    "created_at": now,
    "updated_at": now,
})

couple_update = {
    "email": fixture["coupleEmail"],
    "wedding_id": fixture["weddingId"],
    "partner1_name": "QA",
    "partner2_name": "Couple",
    "password_hash": get_password_hash(fixture["couplePassword"]),
    "setup_completed": True,
    "onboarding_completed": True,
    "onboarding_completed_at": now,
    "onboarding_steps_completed": ["welcome", "overview", "guest_tracker", "messages"],
    "invite_token": None,
    "invite_token_expires": None,
    "updated_at": now,
}

if fixture["state"] == "archived":
    couple_update.update({
        "access_state": "active",
        "is_active": True,
        "wedding_archived": True,
        "archived_at": now,
        "owner_cancelled_at": None,
        "owner_cancelled_by_planner_id": None,
        "owner_cancelled_by_planner_email": None,
        "revoked_at": None,
        "revoked_by": None,
    })
elif fixture["state"] == "owner_cancelled":
    couple_update.update({
        "access_state": "owner_cancelled",
        "is_active": False,
        "wedding_archived": False,
        "archived_at": None,
        "owner_cancelled_at": now,
        "owner_cancelled_by_planner_id": fixture["plannerId"],
        "owner_cancelled_by_planner_email": fixture["plannerEmail"],
        "revoked_at": None,
        "revoked_by": None,
    })
else:
    couple_update.update({
        "access_state": "active",
        "is_active": True,
        "wedding_archived": False,
        "archived_at": None,
        "owner_cancelled_at": None,
        "owner_cancelled_by_planner_id": None,
        "owner_cancelled_by_planner_email": None,
        "revoked_at": None,
        "revoked_by": None,
    })

db["couple_users"].update_one(
    {"email": fixture["coupleEmail"], "wedding_id": fixture["weddingId"]},
    {"$set": couple_update},
    upsert=True,
)

print(json.dumps({
    "formId": str(form_id),
    "meetingId": str(meeting_id),
}))
`;
  return runPythonJson(code) as { formId: string; meetingId: string };
}

function cleanupFixture() {
  const payload = JSON.stringify(FIXTURE);
  const code = `
import json
from pymongo import MongoClient

fixture = json.loads(${JSON.stringify(payload)})
client = MongoClient("mongodb://localhost:27017")
db = client["wedding"]

db["couple_users"].delete_many({
    "email": {"$in": [fixture["coupleEmail"], "qa_pr2_couple@thespecialwedding.io"]},
    "wedding_id": fixture["weddingId"],
})
db["forms"].delete_many({"title": fixture["formTitle"], "wedding_id": fixture["weddingId"]})
db["form_submissions"].delete_many({"submitted_by": fixture["coupleEmail"], "wedding_id": fixture["weddingId"]})
db["planner_tasks"].delete_many({"title": fixture["meetingTitle"], "wedding_id": fixture["weddingId"]})

wedding = db["weddings"].find_one({"_id": fixture["weddingId"]}, {"events": 1})
events = list((wedding or {}).get("events", []))
events = [event for event in events if event.get("custom_type_label") != fixture["eventLabel"]]
db["weddings"].update_one({"_id": fixture["weddingId"]}, {"$set": {"events": events}})

print(json.dumps({"ok": True}))
`;
  return runPythonJson(code);
}

async function loginAdmin(page: import('@playwright/test').Page) {
  await page.goto('/admin/login');
  await page.getByLabel('Work email').fill(FIXTURE.plannerEmail);
  await page.getByLabel('Password').fill(FIXTURE.plannerPassword);
  await page.getByRole('button', { name: /log in|sign in/i }).click();
  await page.waitForURL((url) => url.pathname.startsWith('/admin') && url.pathname !== '/admin/login');
}

async function loginCouple(page: import('@playwright/test').Page) {
  await page.goto('/couple/login');
  await page.getByLabel('Email').fill(FIXTURE.coupleEmail);
  await page.getByLabel('Password').fill(FIXTURE.couplePassword);
  await page.getByRole('button', { name: /sign in/i }).click();
  await page.waitForURL(/\/couple\/dashboard/);
}

function coupleRow(page: import('@playwright/test').Page, email: string) {
  return page
    .locator(`p:text-is("${email}")`)
    .locator('xpath=ancestor::div[contains(@class, "rounded-xl")][1]');
}

test.describe('PR2 couple portal lifecycle alignment', () => {
  test.describe.configure({ mode: 'serial' });

  test.afterAll(() => {
    cleanupFixture();
  });

  test('archived couples get read-only dashboard, timeline, and forms UX', async ({ page, browserName }) => {
    test.skip(browserName !== 'chromium', 'Runs once with DB-backed fixture state.');

    const fixture = seedFixture('archived');
    await loginCouple(page);

    await expect(page.getByText('Your archived wedding portal is available in read-only mode.')).toBeVisible();
    await expect(page.getByText('Read-only wedding portal')).toBeVisible();

    await page.getByRole('button', { name: 'Timeline' }).click();
    await expect(page).toHaveURL(/section=timeline/);
    await page.getByRole('button', { name: /View run of show/i }).click();
    await expect(page.getByText('Timeline notes are read-only because this wedding has been archived.')).toBeVisible();
    await expect(page.getByText('Notes are view-only for archived weddings.')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Add a note' })).toHaveCount(0);
    await expect(page.getByTitle('Leave a note for your planner')).toHaveCount(0);

    await page.getByRole('button', { name: 'Forms' }).click();
    await expect(page).toHaveURL(/section=forms/);
    await expect(page.getByText('Forms are view-only because this wedding has been archived.')).toBeVisible();
    await expect(page.getByRole('button', { name: 'View Response' })).toBeVisible();

    await page.goto(`/couple/forms/${fixture.formId}`);
    await expect(page.getByText('This wedding has been archived. Forms are view-only.')).toBeVisible();
    await expect(page.getByText('This form is view-only. New submissions and edits are disabled for archived weddings.')).toBeVisible();
    await expect(page.getByRole('button', { name: /submit/i })).toHaveCount(0);
  });

  test('meeting destination and admin lifecycle badges match the backend state', async ({ page, browserName }) => {
    test.skip(browserName !== 'chromium', 'Runs once with DB-backed fixture state.');

    seedFixture('active');
    await loginCouple(page);
    await page.goto('/couple/dashboard?section=meetings');
    await expect(page.getByRole('heading', { name: 'Meetings' })).toBeVisible();
    await expect(page.getByText(FIXTURE.meetingTitle)).toBeVisible();
    await expect(page.locator('a[href="https://meet.example.com/pr2-playwright"]')).toBeVisible();

    await loginAdmin(page);
    await page.goto(`/admin/weddings/${FIXTURE.weddingId}`);
    await page.getByRole('button', { name: 'Couple' }).click();
    const activeRow = coupleRow(page, FIXTURE.coupleEmail);
    await expect(activeRow).toContainText(FIXTURE.coupleEmail);
    await expect(activeRow).toContainText('Active');
    await expect(activeRow).toContainText('Revoke Access');

    seedFixture('owner_cancelled');
    await page.reload();
    await page.getByRole('button', { name: 'Couple' }).click();
    const ownerCancelledRow = coupleRow(page, FIXTURE.coupleEmail);
    await expect(ownerCancelledRow).toContainText('Planner Inactive');
    await expect(ownerCancelledRow).toContainText('Planner subscription inactive');
    await expect(ownerCancelledRow.getByRole('button', { name: /Revoke Access/i })).toHaveCount(0);
    await expect(ownerCancelledRow.getByRole('button', { name: /Restore Access/i })).toHaveCount(0);

    seedFixture('archived');
    await page.reload();
    await page.getByRole('button', { name: 'Couple' }).click();
    const archivedRow = coupleRow(page, FIXTURE.coupleEmail);
    await expect(archivedRow).toContainText('Archived Read-Only');
    await expect(archivedRow).toContainText('Archived portal');
    await expect(archivedRow.getByRole('button', { name: /Revoke Access/i })).toHaveCount(0);
    await expect(archivedRow.getByRole('button', { name: /Restore Access/i })).toHaveCount(0);
  });
});
