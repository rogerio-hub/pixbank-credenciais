/**
 * Testes de fumaça. Rodam com o Node puro (`node --test`), sem dependência.
 *
 * O teste que importa é `origem muda conforme a configuração`: ele fixa a tese
 * do módulo como código executável — a mesma aplicação é insegura ou segura
 * dependendo apenas de onde a credencial vem.
 */

'use strict';

const { test } = require('node:test');
const assert = require('node:assert');
const path = require('node:path');

const { rotear } = require('../index');
const credencial = require('../credencial');

function limpar() {
  credencial.limparCache();
  delete process.env.DB_PASSWORD;
  delete process.env.PIXBANK_PARAM_SENHA;
}

test('status responde e declara a origem da credencial', async () => {
  limpar();
  const r = await rotear('/', new URLSearchParams());
  assert.strictEqual(r.status, 200);
  assert.ok(r.corpo.credencialDoBanco.origem);
});

test('sem configuração nenhuma, a origem é o código legado', async () => {
  limpar();
  const r = await rotear('/', new URLSearchParams());
  assert.strictEqual(r.corpo.credencialDoBanco.origem, 'codigo');
  assert.strictEqual(r.corpo.credencialDoBanco.segura, false);
});

test('com variável de ambiente, a origem é ambiente — e ainda é insegura', async () => {
  limpar();
  process.env.DB_PASSWORD = 'senha-de-teste-nao-real';
  credencial.limparCache();
  const r = await rotear('/', new URLSearchParams());
  assert.strictEqual(r.corpo.credencialDoBanco.origem, 'ambiente');
  assert.strictEqual(r.corpo.credencialDoBanco.segura, false);
  limpar();
});

test('o segredo nunca sai na resposta, só a impressão digital', async () => {
  limpar();
  process.env.DB_PASSWORD = 'senha-de-teste-nao-real';
  credencial.limparCache();
  const r = await rotear('/', new URLSearchParams());
  const corpo = JSON.stringify(r.corpo);
  assert.ok(!corpo.includes('senha-de-teste-nao-real'), 'o segredo vazou na resposta');
  assert.strictEqual(r.corpo.credencialDoBanco.impressaoDigital.length, 12);
  limpar();
});

test('saldo devolve a conta pedida', async () => {
  limpar();
  const r = await rotear('/saldo', new URLSearchParams('conta=10021'));
  assert.strictEqual(r.status, 200);
  assert.strictEqual(r.corpo.titular, 'Ana Prado');
});

test('saldo sem conta é 400 e conta inexistente é 404', async () => {
  limpar();
  assert.strictEqual((await rotear('/saldo', new URLSearchParams())).status, 400);
  assert.strictEqual((await rotear('/saldo', new URLSearchParams('conta=999'))).status, 404);
});

test('rota desconhecida é 404', async () => {
  limpar();
  assert.strictEqual((await rotear('/nao-existe', new URLSearchParams())).status, 404);
});
