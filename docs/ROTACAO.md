# Plano de resposta a vazamento de credencial

> **Entregável do Grupo 5 (Suporte).** Este arquivo é um esqueleto: as
> perguntas estão prontas, as respostas não. Preencham pensando em quem vai
> ler isto às 3h da manhã, sem contexto e sem vocês por perto.

**Gatilho:** alguém percebeu que uma credencial foi exposta — em commit, em
chat, em ticket, em captura de tela, em log, ou porque uma ferramenta avisou.

---

## Regra zero

Uma credencial exposta é **comprometida a partir do momento em que foi
exposta**, não a partir do momento em que alguém percebeu.

No caso da **C&M Software**, o contato com o funcionário aconteceu em **março de
2025**, num bar na zona oeste de São Paulo. O dinheiro saiu em **30 de junho**.
Foram três meses de janela — e ninguém estava olhando.

A pergunta "será que alguém usou?" não muda o plano. O plano é o mesmo.

---

## Fase 1 — Conter (0 a 15 minutos)

- [ ] **Quem é acionado, e como?** Nome do canal, do grupo de plantão, do
      telefone. _(preencher)_
- [ ] **Qual credencial é, exatamente?** Serviço, identidade, escopo. Se
      ninguém souber responder em 5 minutos, esse é o primeiro problema.
- [ ] **O que ela alcança?** Produção? Dados de cliente? Outra conta?

> **Não comece apagando o commit.** Apagar o arquivo não invalida a credencial,
> destrói evidência de quando ela foi exposta e dá a sensação de que o problema
> foi resolvido. A ordem correta está na Fase 2.

**Pergunta para o grupo:** existe hoje uma lista das credenciais de longa
duração do ambiente de vocês? Se a resposta não for um número, essa é a
primeira tarefa — não a rotação.

---

## Fase 2 — Rotacionar (15 a 60 minutos)

A ordem importa:

1. **Criar a credencial nova** (ainda sem desativar a antiga).
2. **Trocar onde é consumida** — aplicação, esteira, integração.
3. **Confirmar que a nova funciona.**
4. **Só então revogar a antiga.**

- [ ] **O que quebra entre os passos 2 e 4?** Existe janela em que as duas
      valem? Existe janela em que nenhuma vale? _(preencher)_
- [ ] **Quem tem permissão para revogar,** e essa pessoa está disponível de
      madrugada?
- [ ] **Como se confirma que a antiga morreu?** Um comando concreto, não "a
      gente desativa no console".

**Armadilha registrada em aula:** trocar o método sem revogar a chave antiga não
resolve nada. Uma esteira migrada para OIDC continua exposta enquanto o
`AKIA...` velho existir no IAM. A migração é a Fase 4; a revogação é aqui.

---

## Fase 3 — Avaliar o alcance (1 a 2 horas)

- [ ] **A credencial foi usada?** Onde exatamente se olha isso? _(CloudTrail?
      log da aplicação? log do provedor? preencher com o caminho real)_
- [ ] **Quanto tempo de log a instituição guarda,** e isso cobre a janela desde
      a exposição? Se a credencial vazou há 4 meses e o log dura 90 dias, a
      resposta honesta é "não sabemos" — e isso precisa estar no relatório.
- [ ] **Houve acesso de origem, horário ou volume atípicos?**
- [ ] **A credencial estava em algum repositório público, ou só interno?** Se
      público, assuma coleta automatizada em minutos.

---

## Fase 4 — Comunicar

- [ ] **Quem precisa saber, e em quanto tempo?** _(gestão imediata, segurança
      da informação, jurídico, DPO/Encarregado, cliente — preencher com prazos)_
- [ ] **O que a Res. CMN 5.274/2025 e a Res. BCB 538/2025 exigem** em matéria
      de comunicação de incidente relevante? Qual é o prazo, e quem no banco é
      responsável por essa comunicação?
- [ ] **Houve dado pessoal envolvido?** Se sim, a LGPD (art. 48) exige
      comunicação à ANPD e aos titulares em prazo razoável.
- [ ] **O que NÃO se escreve** no ticket, no chat e no post-mortem: o valor da
      credencial, nem parcialmente. Registro de incidente é lido por muita gente
      e vive muito tempo.

---

## Fase 5 — Aprender (na semana seguinte)

Postmortem **sem culpados** — a mesma regra do módulo de cultura. Quem commitou
o `.env` não é o problema; o processo que deixou isso ser possível é.

- [ ] **Que controle teria pego isso mais cedo?** Marque o que já existe:
  - [ ] Push protection no GitHub (bloqueia o push com segredo)
  - [ ] Varredura de segredo no pre-commit, na máquina de quem desenvolve
  - [ ] Varredura no PR, antes do merge
  - [ ] Varredura periódica do histórico inteiro
  - [ ] Credencial de curta duração desde o início (nada a vazar)
- [ ] **Qual desses vocês vão implantar, e até quando?** Com nome e data.
- [ ] **A credencial precisava existir?** A pergunta mais barata de todas: se a
      esteira usasse OIDC, não haveria chave para vazar.

---

## Métrica que vale acompanhar

| Indicador | Como medir | Alvo |
|---|---|---|
| Credenciais de longa duração no ambiente | inventário | tendência de queda |
| Tempo entre exposição e revogação | do commit ao `delete-access-key` | horas, não dias |
| Idade da credencial mais velha em uso | consulta ao IAM | _(definir)_ |
| Cobertura de varredura de segredo nos repositórios | repos com o gate / total | 100% |

> A terceira linha costuma ser a mais desconfortável. Rode, antes da aula, e
> traga o número: `aws iam list-users` cruzado com `list-access-keys` devolve a
> data de criação de cada chave.
