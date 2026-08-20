import { test, describe, before, after } from 'node:test';
import assert from 'node:assert/strict';
import request from 'supertest';
import { app } from '../index.js';
import { prisma } from '../config/prisma.js';

describe('Authentication & Session Management Lifecycle', () => {
  const testEmail = `test_user_${Date.now()}@clever-ai.io`;
  const testPassword = 'SecurePassword123!';
  const testName = 'Test Agent User';
  let userToken: string;

  after(async () => {
    // Cleanup test user and sessions
    await prisma.user.deleteMany({
      where: { email: { contains: 'test_user_' } }
    }).catch(() => {});
  });

  test('1. Should register a new user successfully', async () => {
    const res = await request(app)
      .post('/api/v1/auth/signup')
      .send({
        name: testName,
        email: testEmail,
        password: testPassword,
        rememberMe: true
      });

    assert.equal(res.status, 201);
    assert.ok(res.body.token);
    assert.equal(res.body.user.email, testEmail.toLowerCase());
    assert.equal(res.body.user.name, testName);
    userToken = res.body.token;

    // Verify session in database
    const sessionCount = await prisma.session.count({
      where: { user: { email: testEmail.toLowerCase() } }
    });
    assert.equal(sessionCount, 1);
  });

  test('2. Should reject duplicate email registration', async () => {
    const res = await request(app)
      .post('/api/v1/auth/signup')
      .send({
        name: 'Another User',
        email: testEmail,
        password: 'Password999!'
      });

    assert.equal(res.status, 400);
    assert.match(res.body.error, /already exists/i);
  });

  test('3. Should reject login with invalid password', async () => {
    const res = await request(app)
      .post('/api/v1/auth/login')
      .send({
        email: testEmail,
        password: 'WrongPassword!'
      });

    assert.equal(res.status, 401);
    assert.match(res.body.error, /invalid email or password/i);
  });

  test('4. Should authenticate valid credentials and issue new session', async () => {
    const res = await request(app)
      .post('/api/v1/auth/login')
      .send({
        email: testEmail,
        password: testPassword
      });

    assert.equal(res.status, 200);
    assert.ok(res.body.token);
    assert.equal(res.body.user.email, testEmail.toLowerCase());
    userToken = res.body.token;
  });

  test('5. Should retrieve current authenticated user profile (/me)', async () => {
    const res = await request(app)
      .get('/api/v1/auth/me')
      .set('Authorization', `Bearer ${userToken}`);

    assert.equal(res.status, 200);
    assert.equal(res.body.user.email, testEmail.toLowerCase());
    assert.equal(res.body.user.name, testName);
    assert.equal(res.body.session.authenticated, true);
  });

  test('6. Should revoke session on logout and reject subsequent requests', async () => {
    const logoutRes = await request(app)
      .post('/api/v1/auth/logout')
      .set('Authorization', `Bearer ${userToken}`);

    assert.equal(logoutRes.status, 200);
    assert.match(logoutRes.body.message, /session revoked/i);

    // Subsequent request with the same revoked token must fail with 401
    const verifyRes = await request(app)
      .get('/api/v1/auth/me')
      .set('Authorization', `Bearer ${userToken}`);

    assert.equal(verifyRes.status, 401);
    assert.match(verifyRes.body.error, /revoked/i);
  });

  test('7. Should reject unauthenticated requests to protected endpoints', async () => {
    const res = await request(app).get('/api/v1/auth/me');
    assert.equal(res.status, 401);
    assert.match(res.body.error, /token required/i);
  });
});
