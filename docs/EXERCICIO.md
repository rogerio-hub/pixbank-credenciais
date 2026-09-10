# Exercício — A mesma higiene, aplicada às credenciais da máquina

**Duração:** 50 minutos · **Formato:** 5 salas de breakout · **Pré-requisito:** nenhuma conta em nenhum serviço

---

## Antes de dividir (7 minutos, plenária)

Peça a alguém que rode, compartilhando a tela:

```bash
node app/index.js &
curl -s localhost:3000/
```

A resposta diz `"origem": "codigo"` e `"segura": false`. Pergunte:

> Se esta aplicação estivesse em produção agora, e essa senha vazasse, **quanto
> tempo até ela parar de funcionar?**

A resposta honesta é: até alguém abrir um PR, esperar revisão, publicar e
reiniciar. Guarde isso — no fim do exercício, a mesma pergunta terá como
resposta "um comando".

Depois rode a auditoria:

```bash
pip install pyyaml
python3 scripts/auditoria_higiene.py
```

**16 achados. BLOQUEADO.** Esse é o ponto de partida de todos os grupos.

---

## Divisão por especialidade

A turma tem Qualidade (o maior grupo), Segurança, Operações, Desenvolvimento e
Suporte. A divisão abaixo não é por conveniência: **dois dos cinco grupos não
escrevem YAML nenhum**, e são os que decidem o que os outros três produzem.

| Grupo | Perfil | Entregável | Arquivo |
|---|---|---|---|
| 1 | Segurança | Uma regra de varredura nova, que pegue algo que a ferramenta hoje ignora | `.gitleaks.toml` |
| 2 | Desenvolvimento | A aplicação lendo do cofre, sem nenhum caminho de volta ao código | `app/credencial.js`, `config/legacy.js` |
| 3 | Operações / DevOps | O deploy autenticando por OIDC | `.github/workflows/deploy.yml` |
| 4 | **Qualidade** | **A política de risco**, com limites e isenções justificadas | `scripts/politica.yaml` |
| 5 | **Suporte** | **O plano das duas primeiras horas** depois de um vazamento | `docs/ROTACAO.md` |

Cada grupo tem **25 minutos**. Os 18 restantes são da apresentação cruzada.

---

## Grupo 1 — Segurança: o que a sua ferramenta está deixando passar

**Ponto de partida.** Rode:

```bash
gitleaks detect --source . --config .gitleaks.toml --report-format json \
  --report-path gitleaks-report.json --redact --exit-code 0 --no-git
python3 -c "import json;[print(x['RuleID'],x['File'],x['StartLine']) for x in json.load(open('gitleaks-report.json'))]"
```

Quatro achados, todos em `config/legacy.js`.

**A descoberta.** Um deles só aparece por causa de uma regra escrita à mão:
`pixbank-chave-aws-exemplo`. Comente essa regra no `.gitleaks.toml` e rode de
novo — a chave `AKIAIOSFODNN7EXAMPLE` some do relatório. Ela está no allowlist
embutido do Gitleaks, porque é a chave que aparece na documentação da AWS.

É uma decisão defensável do produto. E é exatamente por isso que ela é
perigosa: um repositório que copiou aquele exemplo e trocou só o segredo passa
limpo pela varredura.

**Tarefa.**

1. Descomente a regra e confirme que a chave volta a aparecer.
2. Escreva **uma regra nova**, para um formato de credencial que exista no
   mundo de vocês (token de API interno, string de conexão de banco, chave PIX
   de homologação — o que fizer sentido). Prove que ela pega o caso e que não
   dispara em `docs/`.
3. Responda em uma frase: **o que mais está no allowlist da ferramenta que
   vocês usam hoje, e quem decidiu isso?**

**Armadilha.** É tentador resolver o falso positivo do teste
(`scripts/test_auditoria.py`) acrescentando o arquivo ao allowlist de caminhos.
Repare no que fizemos em vez disso: trocamos o valor do fixture por
`'troque-me'`, que o allowlist de *conteúdo* já cobre. Silenciar por caminho
silencia também o segredo de verdade que aparecer ali amanhã.

---

## Grupo 2 — Desenvolvimento: tirar a credencial do código de vez

**Ponto de partida.** Leia `app/credencial.js`. Ele já sabe ler das três
origens. O que ele ainda faz de errado é ter um **caminho de volta**: se o
cofre falhar e a variável de ambiente não existir, ele carrega
`config/legacy.js` e segue funcionando.

**Tarefa.**

1. Apague `config/legacy.js`.
2. Remova o fallback de `credencial.js`. Sem credencial, a aplicação deve
   **falhar de forma visível** — não deve "funcionar mal em silêncio".
3. Ajuste os testes em `app/test/smoke.test.js` para refletir a nova regra e
   acrescente um teste que prove que **o segredo nunca aparece na resposta HTTP**
   (já existe um; entenda por que ele passa mesmo sem cofre).
4. Rode `cd app && npm test` e `python3 scripts/auditoria_higiene.py`. Os três
   achados H6 devem sumir.

**A pergunta que fica.** Apagar o arquivo tira a credencial do próximo clone.
E do histórico? Rode:

```bash
git log --all --oneline -- config/legacy.js
```

Discuta com o Grupo 5: **em que ordem** se faz isso — rotacionar, remover,
reescrever histórico — e por que a ordem importa.

---

## Grupo 3 — Operações / DevOps: a esteira sem senha nenhuma

**Ponto de partida.** Abra `.github/workflows/deploy.yml`. Ele funciona. Foi
assim que quase todo mundo começou. E ele guarda um par de chaves da AWS que
não expira, vale de qualquer lugar do mundo e sobrevive à saída de quem a criou.

**Tarefa.** Reescreva o arquivo para autenticar por OIDC:

1. `permissions: { contents: read, id-token: write }` **no job**, não só no topo.
2. Trocar `aws-access-key-id` / `aws-secret-access-key` por
   `role-to-assume: ${{ vars.AWS_ROLE_ARN }}`.
   Repare: **`vars`, não `secrets`** — um ARN de role não é segredo.
3. `persist-credentials: false` no checkout.
4. Passar para a função **o nome** do parâmetro do SSM, não o valor da senha.

Rode `python3 scripts/auditoria_higiene.py` até H1, H2, H3, H7 e H8 sumirem.

**A parte que a esteira não faz por vocês.** Depois que o OIDC funcionar,
faltam duas coisas, e nenhum gate deste repositório verifica nenhuma delas:

- apagar os segredos `AWS_ACCESS_KEY_ID` e `AWS_SECRET_ACCESS_KEY` do repositório;
- **revogar a chave no IAM**.

Trocar o método sem revogar a chave antiga não resolve nada — ela continua
válida para quem já a copiou. Escrevam isso no relatório do grupo.

**Bônus, se sobrar tempo.** Abra `infra/oidc.tf` e leia a condição `sub`.
Explique para a plenária por que `repo:org/*` seria um desastre.

---

## Grupo 4 — Qualidade: quem decide o que reprova

**Ponto de partida.** Abra `scripts/politica.yaml`. Repare no desenho: nenhuma
ferramenta reprova sozinha. O Gitleaks roda com `--exit-code 0`, a auditoria
produz achados, e **este arquivo** decide.

**Tarefa.** Defendam uma política, por escrito, com justificativa para cada
escolha:

1. **Os limites.** Hoje: CRÍTICA 0, ALTA 0, MÉDIA 3. Por que 3 e não 0? O que
   acontece com o time se for 0? E com o risco se for 10?
2. **A isenção do H4.** Está isenta "porque o material da aula usa tags". Isso
   é uma justificativa ou uma desculpa? Escrevam a versão que vocês assinariam.
3. **A data de validade.** `revisar_ate: 2026-12-31`. Quem revisa? O que
   acontece se a data passar e ninguém olhar? Proponham o mecanismo.
4. **O caminho de exceção.** A esteira bloqueia e o time precisa publicar uma
   correção urgente às 23h. Qual é o caminho? *Não existir caminho é tão ruim
   quanto existir um que todo mundo usa todo dia.*

**A pergunta difícil.** H6 é CRÍTICA quando a aplicação carrega o arquivo e
MÉDIA quando não carrega. Mas o segredo está no histórico do Git nos dois
casos. **A distinção faz sentido, ou é conforto?** Não há resposta certa —
queremos o argumento.

Testem a política de vocês:

```bash
python3 scripts/auditoria_higiene.py --politica scripts/politica.yaml
```

---

## Grupo 5 — Suporte: as duas primeiras horas

**Ponto de partida.** Um desenvolvedor manda no chat do time, às 14h de uma
sexta: *"gente, acho que commitei o .env sem querer"*.

Este é o grupo que trabalha no cenário do caso **C&M Software**. Lá, o
funcionário entregou a credencial em março de 2025; o dinheiro saiu em junho.
Houve **três meses** de janela. Ninguém percebeu porque ninguém estava olhando
para credencial como um ativo com ciclo de vida.

**Tarefa.** Preencham `docs/ROTACAO.md`. O esqueleto está lá, com as perguntas.
O entregável é um documento que uma pessoa de plantão consiga seguir às 3h da
manhã, sem contexto:

1. **Conter** — o que se faz nos primeiros 15 minutos? (Dica: não é apagar o
   commit.)
2. **Rotacionar** — a ordem correta e por quê. O que quebra enquanto a rotação
   acontece?
3. **Avaliar o alcance** — a credencial foi usada? Onde se olha isso? Quanto
   tempo de log a instituição guarda?
4. **Comunicar** — quem precisa saber, em quanto tempo, e o que a
   **Res. CMN 5.274/2025** exige em matéria de comunicação de incidente.
5. **Aprender** — que controle teria pego isso mais cedo? Push protection?
   Varredura no pre-commit? Credencial de curta duração desde o início?

**A pergunta que fecha o módulo.** Quantas credenciais de longa duração existem
hoje no ambiente de vocês? Se a resposta não for um número, é essa a primeira
tarefa — não a rotação.

---

## Apresentação cruzada (18 minutos)

Cada grupo tem **3 minutos**. A ordem importa, porque cada um depende do anterior:

1. **Grupo 4 (Qualidade)** abre dizendo o que decidiu bloquear. Sem isso, os
   outros três não sabem contra o que estão trabalhando.
2. **Grupo 1 (Segurança)** mostra o que a varredura pega — e o que ela ignora.
3. **Grupo 2 (Desenvolvimento)** mostra o `curl localhost:3000/` respondendo
   `"origem": "cofre"`.
4. **Grupo 3 (Operações)** mostra a auditoria em LIBERADO.
5. **Grupo 5 (Suporte)** fecha com o plano — e com a lista do que a esteira
   **não** verifica.

Rode, na plenária, o comando final:

```bash
python3 scripts/auditoria_higiene.py --gitleaks gitleaks-report.json
```

```
Total: 7 achado(s)   |   CRITICA: 0  ALTA: 0  MEDIA: 1  BAIXA: 6
RESULTADO: LIBERADO
```

Mesma aplicação. Mesma política. O que mudou foi de onde vem a credencial.

---

## Gabarito

`docs/gabarito/` — depois de tentar. O gabarito do Grupo 3 é o mais direto de
comparar: `docs/gabarito/deploy.yml`, linha a linha contra o original.

## Se o GitHub Actions estiver lento no dia

Tudo neste exercício roda localmente. A esteira é conveniência, não requisito:

```bash
gitleaks detect --source . --config .gitleaks.toml --report-format json \
  --report-path gitleaks-report.json --redact --exit-code 0 --no-git
python3 scripts/auditoria_higiene.py --gitleaks gitleaks-report.json
cd app && npm test
```
