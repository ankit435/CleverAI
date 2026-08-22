import { test, describe, before, after } from 'node:test';
import assert from 'node:assert/strict';
import request from 'supertest';
import { app } from '../index.js';
import { prisma } from '../config/prisma.js';

describe('Browser AI Agent Control & Multi-User Isolation Tests', () => {
  const userAEmail = `browser_alice_${Date.now()}@clever-ai.io`;
  const userBEmail = `browser_bob_${Date.now()}@clever-ai.io`;
  const password = 'BrowserTestPassword123!';

  let tokenA: string;
  let tokenB: string;

  before(async () => {
    // 1. Create Alice
    const resA = await request(app)
      .post('/api/v1/auth/signup')
      .send({ name: 'Alice Browser', email: userAEmail, password });
    tokenA = resA.body.token;

    // 2. Create Bob
    const resB = await request(app)
      .post('/api/v1/auth/signup')
      .send({ name: 'Bob Browser', email: userBEmail, password });
    tokenB = resB.body.token;
  });

  after(async () => {
    await prisma.user.deleteMany({
      where: { email: { in: [userAEmail.toLowerCase(), userBEmail.toLowerCase()] } }
    }).catch(() => {});
  });

  test('1. Reject unauthenticated access to browser endpoints', async () => {
    const res = await request(app).get('/api/v1/browser/status');
    assert.equal(res.status, 401);
  });

  test('2. Authenticated user can query browser status', async () => {
    const res = await request(app)
      .get('/api/v1/browser/status')
      .set('Authorization', `Bearer ${tokenA}`);

    assert.equal(res.status, 200);
    assert.equal(typeof res.body.connected, 'boolean');
    assert.equal(res.body.mode, 'existing_cdp');
  });

  test('3. Should validate connect payload schema', async () => {
    const res = await request(app)
      .post('/api/v1/browser/connect')
      .set('Authorization', `Bearer ${tokenA}`)
      .send({ mode: 'invalid_mode', cdpUrl: 'not-a-url' });

    assert.equal(res.status, 400);
    assert.match(res.body.error, /invalid|validation/i);
  });

  test('4. Should validate action payload schema', async () => {
    const res = await request(app)
      .post('/api/v1/browser/action')
      .set('Authorization', `Bearer ${tokenA}`)
      .send({ action: 'invalid_action' });

    assert.equal(res.status, 400);
    assert.match(res.body.error, /invalid|validation/i);
  });

  test('5. Multi-User Isolation: User B cannot access User A browser sessions', async () => {
    const resA = await request(app)
      .get('/api/v1/browser/status')
      .set('Authorization', `Bearer ${tokenA}`);

    const resB = await request(app)
      .get('/api/v1/browser/status')
      .set('Authorization', `Bearer ${tokenB}`);

    assert.equal(resA.status, 200);
    assert.equal(resB.status, 200);
    assert.notEqual(resA.body.user_id, resB.body.user_id);
  });
});
