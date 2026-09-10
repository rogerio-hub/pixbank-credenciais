# Trilha AWS — como o instrutor sobe a demonstração

Esta trilha é **só para quem apresenta**. A turma não precisa de conta AWS: o
exercício de `EXERCICIO.md` roda inteiro no GitHub Actions e na máquina local.

O objetivo aqui é ter, na aula, uma URL de verdade que responda:

```json
{ "credencialDoBanco": { "origem": "cofre", "segura": true } }
```

E poder **rotacionar a senha ao vivo com um comando**, mostrando que a
aplicação pega o valor novo sem release nenhum. Esse é o momento que faz o
módulo virar a chave.

---

## Custo

**Zero**, dentro da camada gratuita:

| Recurso | Cobrança |
|---|---|
| Lambda | 1 milhão de requisições e 400 mil GB-s por mês — camada **sempre gratuita** |
| Function URL | sem cobrança à parte |
| SSM Parameter Store, camada Standard | gratuito (até 10 mil parâmetros) |
| IAM, provedor OIDC, roles | gratuito |
| CloudWatch Logs | 5 GB de ingestão por mês grátis; retenção fixada em 14 dias |

Não há EC2, NAT Gateway nem balanceador — os três suspeitos de fatura surpresa.
Ainda assim: **configure um alerta de orçamento** antes de começar (Billing →
Budgets → Zero spend budget). Leva dois minutos e é o conselho que você daria
para a turma.

---

## Pré-requisitos

- Conta AWS com permissão para criar IAM role, Lambda e parâmetro no SSM.
- AWS CLI v2 autenticada (`aws sts get-caller-identity` responde).
- Terraform ≥ 1.6.
- O repositório já publicado no GitHub (veja `COMO-PUBLICAR-NO-GITHUB.md`).

> **Nota de honestidade.** O Terraform deste repositório teve a sintaxe HCL
> validada, mas **não foi aplicado numa conta real** durante a preparação do
> material — o ambiente de preparo não tinha nem rede para a AWS nem o binário
> do Terraform. Rode esta trilha uma vez, com calma, **antes** da aula. Se algo
> divergir, anote e corrija: é material de curso, não de produção.

---

## 1. Aplicar a infraestrutura

```bash
cd infra

terraform init

terraform apply \
  -var="github_org=SEU-USUARIO-OU-ORG" \
  -var="github_repo=pixbank-credenciais"
```

Três saídas importam:

```
role_arn_para_o_github = "arn:aws:iam::123456789012:role/pixbank-credenciais-deploy-github"
url_da_funcao          = "https://xxxxxxxx.lambda-url.sa-east-1.on.aws/"
como_rotacionar        = "aws ssm put-parameter --name /pixbank/prod/db/senha ..."
```

**Se o provedor OIDC já existir na conta** (é comum — ele é um por conta, não um
por repositório), o `apply` falha com `EntityAlreadyExists`. Importe em vez de
criar:

```bash
terraform import aws_iam_openid_connect_provider.github \
  arn:aws:iam::<sua-conta>:oidc-provider/token.actions.githubusercontent.com
```

---

## 2. Gravar a senha de verdade no cofre

O Terraform criou o parâmetro com um valor de fachada, e tem
`ignore_changes = [value]` justamente para não mexer nele depois. Grave o valor
real pela CLI — assim ele **nunca entra no arquivo de estado**, que é texto
claro:

```bash
aws ssm put-parameter \
  --name /pixbank/prod/db/senha \
  --type SecureString \
  --value "$(openssl rand -base64 24)" \
  --overwrite
```

---

## 3. Ligar o GitHub à role

No repositório: **Settings → Secrets and variables → Actions → Variables → New
repository variable**

| Nome | Valor |
|---|---|
| `AWS_ROLE_ARN` | o `role_arn_para_o_github` do passo 1 |

**Variable, não Secret.** Um ARN de role não é segredo — é um identificador
público. Quem tenta assumir a role sem um token OIDC válido do repositório
certo, na branch certa, é recusado pela própria condição `sub`. Guardar ARN
como segredo é cargo cult, e ensina a turma a errado.

Se você configurou o `environment: producao` no workflow do gabarito, crie o
ambiente em **Settings → Environments** e, se quiser, exija aprovação manual.

---

## 4. Publicar

```bash
cp docs/gabarito/deploy.yml .github/workflows/deploy.yml
git add -A && git commit -m "publicar por OIDC" && git push
```

Rode o workflow. O passo `aws sts get-caller-identity` está lá de propósito:
ele mostra na tela uma identidade com nome de sessão `gh-<run_id>`, temporária,
rastreável até a execução exata. Vale pausar nesse ponto em sala.

---

## 5. O momento da aula

```bash
curl -s https://xxxxxxxx.lambda-url.sa-east-1.on.aws/ | python3 -m json.tool
```

```json
{
  "credencialDoBanco": {
    "origem": "cofre",
    "detalhe": "/pixbank/prod/db/senha",
    "segura": true,
    "impressaoDigital": "a1b2c3d4e5f6"
  },
  "recado": "A senha veio do cofre, em tempo de execução. Não há segredo guardado nesta aplicação."
}
```

Anote a `impressaoDigital`. Agora rotacione:

```bash
aws ssm put-parameter --name /pixbank/prod/db/senha \
  --type SecureString --value "$(openssl rand -base64 24)" --overwrite
```

Espere alguns minutos (o contêiner da Lambda cacheia o valor até reciclar) ou
force um contêiner novo publicando uma configuração qualquer, e rode o `curl`
de novo. **A impressão digital mudou. Não houve commit, não houve PR, não houve
deploy.**

A pergunta para a turma, na sequência:

> Quanto tempo levaria para trocar a senha do banco do sistema de vocês, hoje?

---

## 6. Depois da aula — desmontar

```bash
cd infra && terraform destroy
```

E, se você tinha uma chave estática criada para a demonstração:

```bash
aws iam list-access-keys --user-name <usuario>
aws iam delete-access-key --user-name <usuario> --access-key-id AKIA...
```

Esse último comando é o que o Grupo 3 vai apresentar como "a parte que a esteira
não faz por você". Fazer isso na frente da turma fecha o argumento.

---

## Se algo der errado

| Sintoma | Causa provável |
|---|---|
| `Not authorized to perform sts:AssumeRoleWithWebIdentity` | a condição `sub` não bate. Confira org, repo e branch em `infra/variables.tf`; a branch precisa ser exatamente a que dispara o workflow |
| `Credentials could not be loaded` | falta `id-token: write` **no job** (não basta no topo do arquivo) |
| `EntityAlreadyExists` no provedor OIDC | provedor já existe na conta — importe (passo 1) |
| A função responde `"origem": "ambiente"` | sobrou uma variável `DB_PASSWORD` na configuração da função. Remova: é exatamente o achado H8 |
| A função responde `"origem": "indisponivel"` | a role de execução não tem `ssm:GetParameter`, ou o nome do parâmetro está errado. Veja o log em CloudWatch com `PIXBANK_DEBUG=1` |
