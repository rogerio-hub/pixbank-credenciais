# Como publicar este repositório no GitHub

---

## 1. Criar o repositório e empurrar

```bash
cd pixbank-credenciais

git init -b main
git add -A
git commit -m "Módulo 14: exercício de higiene de credenciais"

gh repo create pixbank-credenciais --public --source=. --push
# ou, sem o gh:
#   git remote add origin git@github.com:SEU-USUARIO/pixbank-credenciais.git
#   git push -u origin main
```

---

## 2. O push vai ser bloqueado — e isso é a primeira aula

O GitHub tem **push protection** ligado por padrão em repositório público. Ele
vai barrar o push por causa do `config/legacy.js`:

```
remote: - GITHUB PUSH PROTECTION
remote:   Push cannot contain secrets
remote:   —— Amazon AWS Access Key ID ————————————————
remote:    locations:
remote:      - commit: 3f2a...
remote:        path: config/legacy.js:24
```

**Isso é o comportamento correto.** Um controle que você não configurou, e no
qual talvez nem tenha reparado, acabou de impedir um vazamento.

Para publicar o material didático, o próprio erro traz um link para liberar
aquele achado específico. Escolha o motivo **"It's used in tests"** — é
verdade — e empurre de novo.

**Vale reproduzir isso ao vivo na aula**, antes do exercício: é a demonstração
mais barata de defesa em profundidade que existe. E leva à pergunta certa:

> Push protection está ligado nos repositórios de vocês?
> Alguém sabe quantas liberações já foram concedidas, e por quem?

---

## 3. Conferir que a esteira roda

Vá em **Actions**. O workflow *Higiene de credenciais* dispara sozinho no push.

O esperado no estado inicial é **falha** — no job de auditoria, com o resumo no
sumário da execução:

| Sev. | Regra | Onde | Achado |
|---|---|---|---|
| CRITICA | H1 | `.github/workflows/deploy.yml:36` | Chave estática da AWS usada pela esteira |
| CRITICA | H6 | `config/legacy.js:18` | Credencial versionada no código (senha de banco) |
| … | | | |

**Resultado: BLOQUEADO**

Se a esteira passar verde, algo está errado — provavelmente o `config/legacy.js`
não foi para o repositório.

---

## 4. Como a turma trabalha: fork, não branch

**Fork por grupo.** É mais simples que dar permissão de escrita a 21 pessoas, e
cada grupo tem a própria esteira rodando na própria conta, sem fila.

Na plenária, peça a cada grupo o link do fork. Comparar cinco execuções do
mesmo workflow com resultados diferentes é um bom fechamento.

> **Atenção com fork e OIDC.** Um workflow que roda a partir de um fork **não
> recebe** os segredos nem as variáveis do repositório original, e a condição
> `sub` da role só autoriza o repositório declarado no Terraform. Isso é
> proteção, não defeito: é exatamente o que impede um PR de fora de assumir a
> sua role. Por isso a trilha da AWS é demonstração do instrutor.

---

## 5. Antes da aula — a lista de conferência

- [ ] Repositório publicado e Actions habilitado.
- [ ] Uma execução da esteira já rodada, com o artefato `relatorio-auditoria`
      baixado e guardado. **Plano B**: se o Actions estiver lento no dia, você
      mostra o relatório salvo.
- [ ] `python3 scripts/auditoria_higiene.py` rodado na sua máquina — a saída
      cabe numa tela compartilhada.
- [ ] `node app/index.js` e `curl localhost:3000/` testados.
- [ ] Se for fazer a trilha da AWS: `docs/TRILHA-AWS.md` executada uma vez, com
      a URL da função anotada e o alerta de orçamento configurado.
- [ ] Link do repositório inserido nos slides do exercício.

---

## 6. Depois da aula

- [ ] Se você publicou como público, considere arquivar ou tornar privado — um
      repositório com credenciais de exemplo e o nome de uma instituição
      financeira no README não precisa ficar indexado para sempre.
- [ ] `terraform destroy`, se aplicou a infraestrutura.
- [ ] Revogar qualquer chave estática criada para a demonstração.
