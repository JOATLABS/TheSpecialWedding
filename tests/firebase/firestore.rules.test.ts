import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { after, afterEach, before, beforeEach, describe, it } from 'node:test';

import {
  RulesTestEnvironment,
  assertFails,
  assertSucceeds,
  initializeTestEnvironment,
} from '@firebase/rules-unit-testing';
import {
  addDoc,
  collection,
  doc,
  getDoc,
  getDocs,
  setDoc,
} from 'firebase/firestore';

const rulesPath = new URL('../../firebase/firestore.rules', import.meta.url);
const rules = readFileSync(rulesPath, 'utf8');

const PROJECT_ID = 'demo-wedding-app';
const emulatorHost = process.env.FIRESTORE_EMULATOR_HOST;

if (!emulatorHost) {
  describe.skip('Firestore security rules', () => {
    it('skips when the Firestore emulator is unavailable', () => {
      assert.equal(process.env.FIRESTORE_EMULATOR_HOST, undefined);
    });
  });
} else {
  const [host, portString] = emulatorHost.split(':');
  const port = Number(portString);

  interface AuthClaims {
    userId: string;
    role: string;
    weddingIds: string[];
  }

  describe('Firestore security rules', () => {
    let testEnv: RulesTestEnvironment;

    before(async () => {
      testEnv = await initializeTestEnvironment({
        projectId: PROJECT_ID,
        firestore: { host, port, rules },
      });
    });

    after(async () => {
      await testEnv.cleanup();
    });

    beforeEach(async () => {
      await testEnv.clearFirestore();
    });

    afterEach(async () => {
      await testEnv.clearFirestore();
    });

    async function seedConversation({
      conversationId,
      channel = 'chat',
      participants,
      weddingId,
    }: {
      conversationId: string;
      weddingId: string;
      channel?: 'chat' | 'email';
      participants: Array<{
        userId: string;
        role: 'planner' | 'vendor' | 'couple' | 'wedding_party';
      }>;
    }): Promise<void> {
      await testEnv.withSecurityRulesDisabled(async (context) => {
        const adminDb = context.firestore();
        const conversationRef = doc(adminDb, `conversations/${conversationId}`);
        await setDoc(conversationRef, {
          weddingId,
          channel,
          subject: null,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
          participantCount: participants.length,
          participantIds: participants.map((p) => p.userId).sort(),
        });

        for (const participant of participants) {
          await setDoc(doc(conversationRef, `participants/${participant.userId}`), {
            userId: participant.userId,
            role: participant.role,
            joinedAt: new Date().toISOString(),
            mute: false,
            lastReadAt: null,
          });
        }
      });
    }

    function contextFor(userId: string, claims: Partial<AuthClaims> = {}) {
      const auth: AuthClaims = {
        userId,
        role: claims.role ?? 'planner',
        weddingIds: claims.weddingIds ?? ['wed-1'],
      };

      return testEnv.authenticatedContext(userId, auth).firestore();
    }

    it('allows participants with wedding access to read chat conversations', async () => {
      await seedConversation({
        conversationId: 'convo-1',
        weddingId: 'wed-1',
        participants: [
          { userId: 'planner@example.com', role: 'planner' },
          { userId: 'vendor@example.com', role: 'vendor' },
        ],
      });

      const plannerDb = contextFor('planner@example.com', {
        role: 'planner',
        weddingIds: ['wed-1'],
      });

      const conversation = await assertSucceeds(
        getDoc(doc(plannerDb, 'conversations/convo-1')),
      );

      assert.equal(conversation.id, 'convo-1');
    });

    it('rejects reads for users who are not participants', async () => {
      await seedConversation({
        conversationId: 'convo-2',
        weddingId: 'wed-1',
        participants: [{ userId: 'planner@example.com', role: 'planner' }],
      });

      const outsiderDb = contextFor('intruder@example.com', {
        role: 'vendor',
        weddingIds: ['wed-1'],
      });

      await assertFails(getDoc(doc(outsiderDb, 'conversations/convo-2')));
    });

    it('prevents non-planners from accessing email conversations', async () => {
      await seedConversation({
        conversationId: 'convo-3',
        weddingId: 'wed-1',
        channel: 'email',
        participants: [
          { userId: 'planner@example.com', role: 'planner' },
          { userId: 'vendor@example.com', role: 'vendor' },
        ],
      });

      const vendorDb = contextFor('vendor@example.com', {
        role: 'vendor',
        weddingIds: ['wed-1'],
      });

      await assertFails(getDoc(doc(vendorDb, 'conversations/convo-3')));

      const plannerDb = contextFor('planner@example.com', {
        role: 'planner',
        weddingIds: ['wed-1'],
      });

      const snapshot = await assertSucceeds(
        getDoc(doc(plannerDb, 'conversations/convo-3')),
      );

      assert.equal(snapshot.get('channel'), 'email');
    });

    it('allows participants to read other participant records for authorised weddings', async () => {
      await seedConversation({
        conversationId: 'convo-4',
        weddingId: 'wed-2',
        participants: [
          { userId: 'planner@example.com', role: 'planner' },
          { userId: 'vendor@example.com', role: 'vendor' },
        ],
      });

      const plannerDb = contextFor('planner@example.com', {
        role: 'planner',
        weddingIds: ['wed-2'],
      });

      const participantsSnap = await assertSucceeds(
        getDocs(collection(plannerDb, 'conversations/convo-4/participants')),
      );

      assert.equal(participantsSnap.docs.length, 2);
    });

    it('enforces sender identity when creating chat messages', async () => {
      await seedConversation({
        conversationId: 'convo-5',
        weddingId: 'wed-3',
        participants: [
          { userId: 'vendor@example.com', role: 'vendor' },
        ],
      });

      const vendorDb = contextFor('vendor@example.com', {
        role: 'vendor',
        weddingIds: ['wed-3'],
      });

      await assertSucceeds(
        addDoc(collection(vendorDb, 'conversations/convo-5/messages'), {
          senderId: 'vendor@example.com',
          senderRole: 'vendor',
          body: 'Hello!',
          createdAt: new Date().toISOString(),
        }),
      );

      await assertFails(
        addDoc(collection(vendorDb, 'conversations/convo-5/messages'), {
          senderId: 'planner@example.com',
          senderRole: 'planner',
          body: 'Impersonation attempt',
          createdAt: new Date().toISOString(),
        }),
      );
    });
  });
}
