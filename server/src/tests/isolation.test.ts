import { test, describe, before, after } from 'node:test';
import assert from 'node:assert/strict';
import request from 'supertest';
import { app } from '../index.js';
import { prisma } from '../config/prisma.js';

describe('Multi-User Authorization & Cross-User Data Isolation', () => {
  const userAEmail = `alice_${Date.now()}@clever-ai.io`;
  const userBEmail = `bob_${Date.now()}@clever-ai.io`;
  const password = 'SharedPassword123!';

  let tokenA: string;
  let tokenB: string;
  let conversationAId: string;

  before(async () => {
    // 1. Create User A (Alice)
    const resA = await request(app)
      .post('/api/v1/auth/signup')
      .send({ name: 'Alice Agent', email: userAEmail, password });
    tokenA = resA.body.token;

    // 2. Create User B (Bob)
    const resB = await request(app)
      .post('/api/v1/auth/signup')
      .send({ name: 'Bob Agent', email: userBEmail, password });
    tokenB = resB.body.token;

    // 3. Alice creates a conversation
    const convRes = await request(app)
      .post('/api/v1/conversations')
      .set('Authorization', `Bearer ${tokenA}`)
      .send({ title: "Alice's Secret Project AI Chat", category: 'code' });
    conversationAId = convRes.body.conversation.id;

    // 4. Alice sends a message in her conversation
    await request(app)
      .post('/api/v1/chat')
      .set('Authorization', `Bearer ${tokenA}`)
      .send({
        message: 'Alice confidential financial report',
        threadId: conversationAId
      });
  });

  after(async () => {
    await prisma.user.deleteMany({
      where: { email: { in: [userAEmail.toLowerCase(), userBEmail.toLowerCase()] } }
    }).catch(() => {});
  });

  test('1. Alice can view and retrieve her conversation', async () => {
    const res = await request(app)
      .get(`/api/v1/conversations/${conversationAId}`)
      .set('Authorization', `Bearer ${tokenA}`);

    assert.equal(res.status, 200);
    assert.equal(res.body.conversation.id, conversationAId);
    assert.equal(res.body.conversation.title, "Alice's Secret Project AI Chat");
  });

  test("2. Bob CANNOT access Alice's conversation (404/Access Denied)", async () => {
    const res = await request(app)
      .get(`/api/v1/conversations/${conversationAId}`)
      .set('Authorization', `Bearer ${tokenB}`);

    assert.equal(res.status, 404);
    assert.match(res.body.error, /access denied|not found/i);
  });

  test("3. Bob CANNOT read messages from Alice's conversation", async () => {
    const res = await request(app)
      .get(`/api/v1/conversations/${conversationAId}/messages`)
      .set('Authorization', `Bearer ${tokenB}`);

    assert.equal(res.status, 404);
    assert.match(res.body.error, /access denied|not found/i);
  });

  test("4. Bob CANNOT modify or rename Alice's conversation", async () => {
    const res = await request(app)
      .patch(`/api/v1/conversations/${conversationAId}`)
      .set('Authorization', `Bearer ${tokenB}`)
      .send({ title: "Bob Hijacked Title" });

    assert.equal(res.status, 404);
    assert.match(res.body.error, /access denied|not found/i);
  });

  test("5. Bob CANNOT delete Alice's conversation", async () => {
    const res = await request(app)
      .delete(`/api/v1/conversations/${conversationAId}`)
      .set('Authorization', `Bearer ${tokenB}`);

    assert.equal(res.status, 404);
    assert.match(res.body.error, /access denied|not found/i);
  });

  test("6. Bob CANNOT access Alice's agent execution runs", async () => {
    const res = await request(app)
      .get(`/api/v1/conversations/${conversationAId}/runs`)
      .set('Authorization', `Bearer ${tokenB}`);

    assert.equal(res.status, 404);
    assert.match(res.body.error, /access denied|not found/i);
  });

  test("7. Bob submitting chat with Alice's threadId does not contaminate Alice's thread", async () => {
    const res = await request(app)
      .post('/api/v1/chat')
      .set('Authorization', `Bearer ${tokenB}`)
      .send({
        message: "Bob's message trying to write into Alice's thread",
        threadId: conversationAId
      });

    assert.equal(res.status, 200);
    // Backend creates an isolated thread for Bob rather than polluting Alice's thread
    assert.notEqual(res.body.threadId, conversationAId);

    // Verify Alice's messages still contain only Alice's messages
    const aliceCheck = await request(app)
      .get(`/api/v1/conversations/${conversationAId}/messages`)
      .set('Authorization', `Bearer ${tokenA}`);

    const texts = aliceCheck.body.messages.map((m: any) => m.text);
    assert.ok(texts.some((t: string) => t.includes('Alice confidential')));
    assert.ok(!texts.some((t: string) => t.includes("Bob's message")));
  });
});
