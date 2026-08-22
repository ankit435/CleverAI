import { test, describe, after } from 'node:test';
import assert from 'node:assert/strict';
import request from 'supertest';
import { app } from '../index.js';
import { prisma } from '../config/prisma.js';

describe('Dynamic Plugins, Live Availability & PostgreSQL Persistence', () => {
  const userAEmail = `plug_user_a_${Date.now()}@clever-ai.io`;
  const userBEmail = `plug_user_b_${Date.now()}@clever-ai.io`;
  let tokenA: string;
  let tokenB: string;
  let customToolId: string;

  after(async () => {
    await prisma.user.deleteMany({
      where: {
        email: { in: [userAEmail.toLowerCase(), userBEmail.toLowerCase()] }
      }
    }).catch(() => {});
  });

  test('1. Setup users for plugin testing', async () => {
    const resA = await request(app)
      .post('/api/v1/auth/signup')
      .send({ name: 'Plugin User A', email: userAEmail, password: 'Password123!' });
    tokenA = resA.body.token;

    const resB = await request(app)
      .post('/api/v1/auth/signup')
      .send({ name: 'Plugin User B', email: userBEmail, password: 'Password123!' });
    tokenB = resB.body.token;

    assert.ok(tokenA);
    assert.ok(tokenB);
  });

  test('2. Should fetch dynamic plugins list with live availability and categories', async () => {
    const res = await request(app)
      .get('/api/v1/plugins')
      .set('Authorization', `Bearer ${tokenA}`);

    assert.equal(res.status, 200);
    assert.ok(Array.isArray(res.body.plugins));
    assert.ok(Array.isArray(res.body.categories));
    assert.ok(res.body.plugins.length >= 8);

    // Verify dynamic properties
    const searchPlugin = res.body.plugins.find((p: any) => p.id === 'web-search');
    assert.ok(searchPlugin);
    assert.equal(typeof searchPlugin.isAvailable, 'boolean');
    assert.ok(searchPlugin.statusMessage);
    assert.equal(searchPlugin.category, 'search');
  });

  test('3. Should persist plugin toggle preference in PostgreSQL', async () => {
    // Toggle web-search to disabled
    const toggleRes = await request(app)
      .patch('/api/v1/plugins/toggle/web-search')
      .set('Authorization', `Bearer ${tokenA}`)
      .send({ enabled: false });

    assert.equal(toggleRes.status, 200);

    // Verify fetching plugins reflects the persisted toggle
    const fetchRes = await request(app)
      .get('/api/v1/plugins')
      .set('Authorization', `Bearer ${tokenA}`);

    const searchPlugin = fetchRes.body.plugins.find((p: any) => p.id === 'web-search');
    assert.equal(searchPlugin.enabled, false);

    // User B should still have web-search enabled by default
    const fetchResB = await request(app)
      .get('/api/v1/plugins')
      .set('Authorization', `Bearer ${tokenB}`);

    const searchPluginB = fetchResB.body.plugins.find((p: any) => p.id === 'web-search');
    assert.equal(searchPluginB.enabled, true);
  });

  test('4. Should create and persist custom user plugin in PostgreSQL', async () => {
    const customToolData = {
      name: 'Crypto Price Tracker',
      description: 'Fetches live cryptocurrency prices from CoinGecko API',
      icon: '🪙',
      category: 'finance',
      endpointUrl: 'https://api.coingecko.com/api/v3/simple/price',
      method: 'GET'
    };

    const res = await request(app)
      .post('/api/v1/plugins/custom')
      .set('Authorization', `Bearer ${tokenA}`)
      .send(customToolData);

    assert.equal(res.status, 201);
    assert.ok(res.body.plugin.id);
    assert.equal(res.body.plugin.name, customToolData.name);
    assert.equal(res.body.plugin.isCustom, true);
    assert.equal(res.body.plugin.isAvailable, true);
    customToolId = res.body.plugin.id;

    // Verify it appears in user A's plugin list
    const fetchRes = await request(app)
      .get('/api/v1/plugins')
      .set('Authorization', `Bearer ${tokenA}`);

    const found = fetchRes.body.plugins.find((p: any) => p.id === customToolId);
    assert.ok(found);
    assert.equal(found.name, customToolData.name);
  });

  test('5. User B CANNOT view or delete User A custom plugin', async () => {
    // User B fetches plugins; User A's custom plugin should NOT be present
    const fetchResB = await request(app)
      .get('/api/v1/plugins')
      .set('Authorization', `Bearer ${tokenB}`);

    const foundInB = fetchResB.body.plugins.find((p: any) => p.id === customToolId);
    assert.equal(foundInB, undefined);

    // User B attempts to delete User A's custom plugin
    const deleteResB = await request(app)
      .delete(`/api/v1/plugins/custom/${customToolId}`)
      .set('Authorization', `Bearer ${tokenB}`);

    assert.equal(deleteResB.status, 404);
  });

  test('6. User A should delete custom plugin successfully', async () => {
    const deleteRes = await request(app)
      .delete(`/api/v1/plugins/custom/${customToolId}`)
      .set('Authorization', `Bearer ${tokenA}`);

    assert.equal(deleteRes.status, 200);

    // Verify it is gone
    const fetchRes = await request(app)
      .get('/api/v1/plugins')
      .set('Authorization', `Bearer ${tokenA}`);

    const found = fetchRes.body.plugins.find((p: any) => p.id === customToolId);
    assert.equal(found, undefined);
  });
});
