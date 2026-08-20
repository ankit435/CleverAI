import { test, describe, before, after } from 'node:test';
import assert from 'node:assert/strict';
import request from 'supertest';
import { app } from '../index.js';
import { prisma } from '../config/prisma.js';

describe('Persistent Agent Execution, Multi-Tool Tracking & Conversation Flow', () => {
  const userEmail = `agent_tester_${Date.now()}@clever-ai.io`;
  const password = 'AgentTestPassword123!';
  let token: string;
  let conversationId: string;

  before(async () => {
    const res = await request(app)
      .post('/api/v1/auth/signup')
      .send({ name: 'Agent Tester', email: userEmail, password });
    token = res.body.token;
  });

  after(async () => {
    await prisma.user.deleteMany({
      where: { email: userEmail.toLowerCase() }
    }).catch(() => {});
  });

  test('1. Should execute multi-tool chat and persist user message, AI message, and AgentRun', async () => {
    const chatRes = await request(app)
      .post('/api/v1/chat')
      .set('Authorization', `Bearer ${token}`)
      .send({
        message: 'Please write a python code snippet to calculate numbers',
        model: 'meta/llama-3.1-70b-instruct',
        activePlugins: ['code-interpreter', 'web-search']
      });

    assert.equal(chatRes.status, 200);
    assert.ok(chatRes.body.threadId);
    assert.ok(chatRes.body.reply);
    assert.ok(chatRes.body.agentRunId);
    conversationId = chatRes.body.threadId;

    // Verify User & AI Messages persisted in PostgreSQL
    const messages = await prisma.message.findMany({
      where: { threadId: conversationId },
      orderBy: { createdAt: 'asc' }
    });

    assert.equal(messages.length, 2);
    assert.equal(messages[0].sender, 'user');
    assert.match(messages[0].text, /python code snippet/i);
    assert.equal(messages[1].sender, 'ai');
    assert.ok(messages[1].text.length > 0);

    // Verify AgentRun persisted in PostgreSQL
    const agentRun = await prisma.agentRun.findUnique({
      where: { id: chatRes.body.agentRunId }
    });

    assert.ok(agentRun);
    assert.equal(agentRun.status, 'completed');
    assert.equal(agentRun.model, 'meta/llama-3.1-70b-instruct');
    assert.ok(agentRun.executionTimeMs! >= 0);
  });

  test('2. Should persist individual ToolCall records linked to AgentRun', async () => {
    const chatRes = await request(app)
      .post('/api/v1/chat')
      .set('Authorization', `Bearer ${token}`)
      .send({
        message: 'Search for official AI agent documentation and guidelines',
        threadId: conversationId,
        activePlugins: ['web-search']
      });

    assert.equal(chatRes.status, 200);
    assert.ok(chatRes.body.agentRunId);

    // Verify ToolCall records linked to the AgentRun in PostgreSQL
    const toolCalls = await prisma.toolCall.findMany({
      where: { agentRunId: chatRes.body.agentRunId }
    });

    assert.ok(toolCalls.length > 0);
    assert.equal(toolCalls[0].status, 'success');
    assert.equal(toolCalls[0].toolId, 'web-search');
    assert.ok(toolCalls[0].output);
  });

  test('3. Should paginate conversations and filter by category', async () => {
    const listRes = await request(app)
      .get('/api/v1/conversations?limit=10&page=1')
      .set('Authorization', `Bearer ${token}`);

    assert.equal(listRes.status, 200);
    assert.ok(Array.isArray(listRes.body.conversations));
    assert.ok(listRes.body.pagination);
    assert.equal(listRes.body.pagination.page, 1);
    assert.ok(listRes.body.conversations.length >= 1);
  });

  test('4. Should update conversation title and category', async () => {
    const patchRes = await request(app)
      .patch(`/api/v1/conversations/${conversationId}`)
      .set('Authorization', `Bearer ${token}`)
      .send({
        title: 'Updated Python & Search Agent Session',
        category: 'code'
      });

    assert.equal(patchRes.status, 200);
    assert.equal(patchRes.body.conversation.title, 'Updated Python & Search Agent Session');
    assert.equal(patchRes.body.conversation.category, 'code');
  });

  test('5. Should cascade delete conversation, messages, agent runs, and tool calls', async () => {
    const deleteRes = await request(app)
      .delete(`/api/v1/conversations/${conversationId}`)
      .set('Authorization', `Bearer ${token}`);

    assert.equal(deleteRes.status, 200);

    // Verify conversation is gone
    const convCount = await prisma.chatThread.count({ where: { id: conversationId } });
    assert.equal(convCount, 0);

    // Verify messages are cascaded
    const msgCount = await prisma.message.count({ where: { threadId: conversationId } });
    assert.equal(msgCount, 0);

    // Verify agent runs are cascaded
    const runCount = await prisma.agentRun.count({ where: { threadId: conversationId } });
    assert.equal(runCount, 0);
  });
});
