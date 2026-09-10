# Gabarito

Leia **depois** de tentar. Cada arquivo aqui é a resposta de um grupo.

| Arquivo | Grupo | O que mostra |
|---|---|---|
| `deploy.yml` | 3 — Operações/DevOps | O workflow autenticando por OIDC, sem segredo nenhum |
| `credencial-sem-fallback.js` | 2 — Desenvolvimento | `app/credencial.js` sem o caminho de volta ao código |

Os grupos 1, 4 e 5 não têm gabarito de propósito: a regra de varredura, a
política de risco e o plano de resposta dependem do ambiente de vocês. Um
gabarito ali seria uma resposta errada com aparência de certa.

---

## Atenção ao aplicar o gabarito do Grupo 2

Trocar `app/credencial.js` pela versão sem fallback e apagar `config/legacy.js`
**quebra dois testes** de `app/test/smoke.test.js`. Isso é esperado e faz parte da
tarefa: um teste que continua verde depois de uma mudança de comportamento não
estava testando o comportamento.

```
not ok 2 - sem configuração nenhuma, a origem é o código legado
not ok 5 - saldo devolve a conta pedida
```

O **2** falha pelo motivo óbvio: não existe mais origem `codigo`.

O **5** é o interessante, e costuma pegar o grupo de surpresa. Sem nenhuma
credencial configurada, `descrever()` devolve `origem: "indisponivel"` — e o
`/saldo` passa a responder **503**, porque a aplicação recusa consultar o banco
sem credencial. É exatamente o comportamento que o gabarito quer: **falhar de
forma visível em vez de funcionar mal em silêncio.** O teste é que precisava
mudar, não o código.

Substituições sugeridas:

```js
test('sem configuração nenhuma, a aplicação recusa em vez de improvisar', async () => {
  limpar();
  const r = await rotear('/', new URLSearchParams());
  assert.strictEqual(r.corpo.credencialDoBanco.origem, 'indisponivel');
  assert.strictEqual(r.corpo.credencialDoBanco.segura, false);
});

test('em produção, variável de ambiente não é aceita', async () => {
  limpar();
  process.env.NODE_ENV = 'production';
  process.env.DB_PASSWORD = 'senha-de-teste';
  credencial.limparCache();
  const r = await rotear('/', new URLSearchParams());
  assert.strictEqual(r.corpo.credencialDoBanco.origem, 'indisponivel');
  delete process.env.NODE_ENV;
  limpar();
});

test('sem credencial, o saldo não é consultado', async () => {
  limpar();
  const r = await rotear('/saldo', new URLSearchParams('conta=10021'));
  assert.strictEqual(r.status, 503);
});

test('com credencial de desenvolvimento, o saldo volta a responder', async () => {
  limpar();
  process.env.DB_PASSWORD = 'senha-de-teste';
  credencial.limparCache();
  const r = await rotear('/saldo', new URLSearchParams('conta=10021'));
  assert.strictEqual(r.status, 200);
  assert.strictEqual(r.corpo.titular, 'Ana Prado');
  limpar();
});
```
