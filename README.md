# PixBank — Higiene de Credenciais

Repositório de exercício do **Módulo 14 — Boas Práticas de Higiene Digital e Senhas**
(DevSecOps · FIAP / Caixa).

O módulo passa três horas falando de senha de gente: comprimento, reutilização,
MFA, phishing. Este repositório faz a pergunta que fecha o assunto:

> **E as senhas que a automação usa? Quem cuida delas?**

Ninguém tenta ler o e-mail de um desenvolvedor quando existe um `AKIA...` num
arquivo `.env` que dá acesso direto à conta de produção. No caso da **C&M
Software** — a prestadora de tecnologia que conecta instituições ao Pix,
atacada em 30/06/2025 — o vetor não foi um zero-day nem uma falha de software:
foi **uma credencial, vendida por R$ 15 mil**, e R$ 541 milhões saíram do
sistema financeiro brasileiro em três horas. Na **Sinqia** (set/2025), o acesso
foi feito com **credenciais legítimas de fornecedores de TI**.

Este repositório **não simula esses ataques**. Ele torna verificável por máquina
a condição que os tornou possíveis: existir credencial de longa duração,
alcançável, que vale de qualquer lugar e não expira sozinha. A turma vê essa
condição ser detectada numa esteira de verdade — e a conserta.

---

## O que tem dentro

```
app/                aplicação de exemplo (Node.js, sem dependência externa)
  credencial.js     ← o coração: resolve a senha em 3 origens e DECLARA qual usou
  index.js          servidor local e handler de Lambda
config/legacy.js    ← 3 credenciais versionadas de propósito (o "antes")
.gitleaks.toml      regras de varredura, com uma regra própria e um allowlist explicado
scripts/
  auditoria_higiene.py   ← a esteira auditando a própria esteira (9 regras)
  politica.yaml          ← quem decide o que reprova (entregável do Grupo 4)
  test_auditoria.py      17 testes
.github/workflows/
  higiene.yml       a esteira: 4 gates
  deploy.yml        ← ERRADO DE PROPÓSITO: publica com chave estática
infra/              Terraform: OIDC + Lambda + SSM (camada gratuita)
docs/
  PASSO-A-PASSO.md  ← COMECE AQUI: do zero até a sala, na ordem de execução
  EXERCICIO.md      roteiro de 50 minutos, 5 grupos por especialidade
  TRILHA-AWS.md     referência da parte AWS (o passo a passo já a resume)
  ROTACAO.md        esqueleto do plano de resposta (entregável do Grupo 5)
  gabarito/         as respostas — só depois de tentar
```

**Se você é quem vai dar a aula:** vá direto para `docs/PASSO-A-PASSO.md`. São
cerca de 2 horas de preparo, em duas sentadas, com um "conferir:" ao fim de cada
passo.

---

## Comece por aqui (2 minutos, sem conta em nada)

```bash
git clone <url-do-fork>
cd pixbank-credenciais

# 1) Suba a aplicação e pergunte de onde vem a senha
node app/index.js &
curl -s localhost:3000/ | head -20
```

```json
{
  "credencialDoBanco": {
    "origem": "codigo",
    "detalhe": "config/legacy.js (versionado no repositório)",
    "segura": false
  },
  "recado": "A senha é um segredo de longa duração. Alguém precisa rotacionar isto na mão — e vai esquecer."
}
```

```bash
# 2) Rode a auditoria da esteira
python3 -m venv .venv && source .venv/bin/activate && pip install pyyaml
python3 scripts/auditoria_higiene.py
```

> O ambiente virtual não é frescura: o Python do macOS recusa `pip install`
> direto, com `externally-managed-environment`.

Saída resumida no estado inicial:

```
Total: 16 achado(s)   |   CRITICA: 5  ALTA: 3  MEDIA: 2  BAIXA: 6
RESULTADO: BLOQUEADO
  - 5 achado(s) de severidade CRITICA; a política tolera no máximo 0
  - 3 achado(s) de severidade ALTA; a política tolera no máximo 0
```

Depois do exercício, o mesmo comando devolve:

```
Total: 7 achado(s)   |   CRITICA: 0  ALTA: 0  MEDIA: 1  BAIXA: 6
RESULTADO: LIBERADO
```

Mesma aplicação. Mesma política. O que mudou foi **de onde vem a credencial**.

---

## As 9 regras da auditoria

| Regra | O que procura | Severidade |
|---|---|---|
| H1 | Chave estática da AWS nos segredos do workflow | CRÍTICA |
| H2 | Deploy na AWS sem federação de identidade (OIDC) | ALTA |
| H3 | Workflow sem `permissions` declarado | ALTA |
| H4 | Ação de terceiro presa a tag móvel em vez de SHA | MÉDIA / BAIXA |
| H5 | Comando que ecoa segredo no log do job | ALTA |
| H6 | Credencial versionada no código da aplicação | CRÍTICA / MÉDIA |
| H7 | `checkout` mantendo a credencial no disco do executor | MÉDIA |
| H8 | Segredo injetado como variável de ambiente da função | ALTA |
| H9 | Achados do Gitleaks, trazidos para a mesma fila | CRÍTICA |

**H6 muda de severidade conforme o contexto.** Credencial versionada é CRÍTICA
quando algum arquivo de `app/` carrega o módulo — ou seja, quando ela é
alcançável em produção — e MÉDIA quando não é. É a mesma ideia de
alcançabilidade do Módulo 12 (ASPM), na menor escala possível.

**Os gates não reprovam sozinhos.** O Gitleaks roda com `--exit-code 0` de
propósito: ele produz evidência. Quem decide é `scripts/politica.yaml`, num
lugar só. Se cada ferramenta puder barrar a release, você tem várias donas de
política e nenhuma priorização.

**H9 e H6 são reconciliados.** Quando as duas ferramentas apontam a mesma linha,
vira **um** achado, com nota de que foi confirmado pelas duas. Contar duas vezes
infla o painel e treina o time a ignorar o número.

---

## As três origens da credencial

`app/credencial.js` resolve a senha em três lugares, da pior para a melhor, e o
endpoint `/` mostra qual foi usada:

| Origem | Onde a senha está | Rotacionar exige | Aparece em |
|---|---|---|---|
| `codigo` | `config/legacy.js`, versionado | mudar código, revisar, publicar | histórico do Git, para sempre |
| `ambiente` | variável de ambiente da função | **um novo deploy** | console, API de descrição, dump de processo |
| `cofre` | SSM Parameter Store (SecureString) | **um comando, efeito imediato** | em lugar nenhum |

A linha que mais dói é a do meio. Quase todo time que "tirou o segredo do
código" parou aí — e não percebeu que transformou rotação de senha em release.

---

## Custo

**Zero**, nas duas trilhas.

- A trilha do GitHub Actions roda inteira no plano gratuito. Nenhuma ferramenta
  usada (Gitleaks, Python, Node) exige cadastro, token ou licença.
- A trilha da AWS usa **Lambda** (1 milhão de requisições/mês na camada sempre
  gratuita), **Function URL** (sem cobrança à parte), **SSM Parameter Store
  camada Standard** (gratuito) e **IAM/OIDC** (gratuito). Sem EC2, sem NAT
  Gateway, sem balanceador — os três suspeitos de fatura surpresa.

O Secrets Manager cobra por segredo por mês e ficou de fora de propósito. A
diferença que importa aqui é conceitual, não de produto.

---

## Honestidade sobre o que este repositório NÃO faz

Vale dizer em voz alta, para a turma não superestimar o que viu:

- **A auditoria é textual e estrutural**, não semântica. Ela lê o YAML dos
  workflows e o texto dos arquivos. Um workflow que monte o nome do segredo em
  tempo de execução passa despercebido.
- **H6 detecta o padrão `chave: 'valor'` em `config/legacy.js`**, não qualquer
  credencial em qualquer arquivo. É um exercício, não um scanner.
- **Não há verificação de que a chave antiga foi revogada.** Nenhuma ferramenta
  neste repositório sabe se o `AKIA...` ainda funciona na AWS. Isso é
  deliberado, e é o assunto do Grupo 5: a esteira não fecha a porta, ela só
  avisa que está aberta.
- **O Terraform não foi aplicado numa conta real durante a preparação deste
  material** — a sintaxe HCL foi validada, mas `terraform validate` e
  `terraform plan` precisam de rede e de credencial. Antes da aula, siga
  `docs/PASSO-A-PASSO.md` uma vez, com calma.

---

## Estado dos testes

| O quê | Como rodar | Resultado |
|---|---|---|
| Aplicação | `cd app && npm test` | 7 testes, todos passando |
| Auditor | `python3 scripts/test_auditoria.py` | 17 testes, todos passando |
| Esteira, estado inicial | `python3 scripts/auditoria_higiene.py` | BLOQUEADO (sai com 1) |
| Esteira, estado corrigido | idem, após o exercício | LIBERADO (sai com 0) |

O teste que vale ler é `test_corrigir_para_oidc_muda_o_veredito`: é a tese do
módulo fixada como código executável.

---

## Próximo passo

- **Vai dar a aula?** `docs/PASSO-A-PASSO.md`
- **Vai fazer o exercício?** `docs/EXERCICIO.md`
