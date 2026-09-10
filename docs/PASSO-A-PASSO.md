# Passo a passo — do zero até a sala

Roteiro único, na ordem de execução. Os outros documentos (`TRILHA-AWS.md`,
`COMO-PUBLICAR-NO-GITHUB.md`, `EXERCICIO.md`) são referência; **este é o que
você segue**.

**Tempo total antes da aula:** cerca de 2 horas, em duas sentadas. Faça as
partes 0 a 4 num dia e o ensaio (parte 5) noutro — a distância ajuda a
perceber o que ficou confuso.

| Parte | O quê | Tempo | Quando |
|---|---|---|---|
| 0 | Preparar a máquina | 20 min | uma vez |
| 1 | AWS: conta, alerta de orçamento, credencial local | 25 min | uma vez |
| 2 | Publicar no GitHub | 15 min | uma vez |
| 3 | Criar a infraestrutura com Terraform | 15 min | uma vez |
| 4 | Ligar GitHub e AWS por OIDC | 15 min | uma vez |
| 5 | Ensaio completo | 20 min | véspera |
| 6 | O dia da aula | 50 min | — |
| 7 | Desmontar | 10 min | depois |

Cada passo termina com um **conferir:** — se a saída não bater, pare ali. O
anexo no fim tem os erros comuns.

---

# Parte 0 — Preparar a máquina (20 min)

## 0.1 Instalar as ferramentas

```bash
brew install awscli gh gitleaks node
brew tap hashicorp/tap
brew install hashicorp/tap/terraform
```

**Conferir:**

```bash
aws --version && gh --version && gitleaks version && node -v && terraform version
```

Todos devem responder. `node` precisa ser 20 ou mais novo.

## 0.2 Preparar o Python do auditor

O macOS recente recusa `pip install` no Python do sistema. Use um ambiente
virtual dentro do repositório:

```bash
cd "<pasta do repositório>/pixbank-credenciais"
python3 -m venv .venv
source .venv/bin/activate
pip install pyyaml
```

**Conferir:**

```bash
python3 scripts/test_auditoria.py 2>&1 | tail -3
```

Esperado: `Ran 17 tests ... OK`

> Toda vez que abrir um terminal novo, rode `source .venv/bin/activate` antes
> dos comandos de auditoria. O `.venv/` já está no `.gitignore`.

## 0.3 Conferir que o repositório está inteiro

```bash
cd app && npm test 2>&1 | grep -E "^# (tests|pass|fail)" ; cd ..
```

Esperado: `# tests 7`, `# pass 7`, `# fail 0`

---

# Parte 1 — AWS (25 min)

## 1.1 A conta

Se você já tem conta pessoal, pule para 1.2.

Se não: `https://portal.aws.amazon.com/billing/signup`. Precisa de cartão de
crédito (a AWS faz uma cobrança de verificação de cerca de US$ 1, estornada) e
de telefone. Use **e-mail pessoal**, não o corporativo da Caixa — esta é uma
conta de demonstração sua, que você vai destruir depois.

Ative MFA na conta raiz assim que entrar. É literalmente a aula.

## 1.2 O alerta de orçamento — faça ANTES de qualquer outra coisa

Console → **Billing and Cost Management** → **Budgets** → **Create budget** →
modelo **Zero spend budget** → e-mail de destino → criar.

Esse orçamento avisa no primeiro centavo. Tudo neste exercício é camada
gratuita, então **qualquer aviso significa que algo ficou ligado sem querer**.

> Os caminhos do console da AWS mudam de lugar com alguma frequência. Se o menu
> não estiver onde está escrito, procure por "Budgets" na busca do console.

## 1.3 A credencial local — e a ironia declarada

O Terraform precisa autenticar na sua conta. Você vai criar **exatamente aquilo
que o módulo condena**: uma chave estática. Isso é deliberado, e vira material:
no fim da aula você revoga essa chave na frente da turma (passo 7.2).

Console → **IAM** → **Users** → **Create user** → nome `terraform-modulo14` →
**Attach policies directly** → `AdministratorAccess` → criar.

Depois, no usuário criado: **Security credentials** → **Create access key** →
caso de uso *Command Line Interface* → copiar as duas partes.

```bash
aws configure --profile modulo14
# AWS Access Key ID:     AKIA...
# AWS Secret Access Key: ...
# Default region name:   sa-east-1
# Default output format: json

export AWS_PROFILE=modulo14
```

**Conferir:**

```bash
aws sts get-caller-identity
```

Deve devolver `Account`, `UserId` e um `Arn` terminando em
`user/terraform-modulo14`. **Anote o número da conta** — você vai precisar.

> **Alternativa melhor, se tiver 20 minutos sobrando:** habilite o IAM Identity
> Center e use `aws configure sso` + `aws sso login`. As credenciais passam a
> ser temporárias, e aí você não cria nenhuma chave estática. É mais coerente
> com o módulo, mas leva mais tempo e cria uma organização na conta. Para uma
> demonstração descartável, o caminho acima resolve — desde que você revogue no
> fim.

---

# Parte 2 — Publicar no GitHub (15 min)

Faça esta parte **antes** do Terraform: a role OIDC precisa saber o nome da sua
organização e do repositório.

## 2.1 Criar o repositório e empurrar

```bash
cd "<pasta do repositório>/pixbank-credenciais"

git init -b main
git add -A
git commit -m "Módulo 14: exercício de higiene de credenciais"

gh auth login          # se ainda não estiver autenticado
gh repo create pixbank-credenciais --public --source=. --push
```

## 2.2 O push vai ser bloqueado — e isso é a primeira aula

Espere ver algo assim:

```
remote: - GITHUB PUSH PROTECTION
remote:   Push cannot contain secrets
remote:   —— Amazon AWS Access Key ID ——
remote:    locations:
remote:      - commit: 3f2a...
remote:        path: config/legacy.js:24
```

**Não conserte isso.** Um controle que você não configurou acabou de impedir um
vazamento — é a demonstração mais barata de defesa em profundidade que existe, e
vale reproduzir ao vivo na aula.

Para publicar o material, abra o link que o próprio erro traz, escolha o motivo
**"It's used in tests"** (é verdade) e empurre de novo:

```bash
git push -u origin main
```

**Conferir:** o repositório aparece em `github.com/<você>/pixbank-credenciais`
com 26 arquivos, incluindo `.github/workflows/`.

## 2.3 Ver a esteira reprovar

Aba **Actions** → o workflow *Higiene de credenciais* dispara sozinho no push.

**Conferir:** o job *Gate 3 — auditoria* **falha**, e o sumário da execução traz
a tabela de achados terminando em **BLOQUEADO**.

Se a esteira passar verde, algo está errado — provavelmente o `config/legacy.js`
não subiu.

## 2.4 Guardar o plano B

Na execução que falhou, baixe o artefato **relatorio-auditoria**. Se o Actions
estiver lento no dia da aula, você mostra esse relatório salvo.

---

# Parte 3 — Criar a infraestrutura (15 min)

```bash
cd infra
terraform init

terraform apply \
  -var="github_org=SEU-USUARIO-OU-ORG" \
  -var="github_repo=pixbank-credenciais"
```

Leia o plano antes de confirmar. São cerca de 12 recursos: um provedor OIDC,
duas roles, três políticas, uma função Lambda, uma Function URL, uma permissão,
um parâmetro no SSM e um grupo de log.

**Conferir:** três saídas ao fim do `apply`:

```
role_arn_para_o_github = "arn:aws:iam::123456789012:role/pixbank-credenciais-deploy-github"
url_da_funcao          = "https://xxxxxxxx.lambda-url.sa-east-1.on.aws/"
como_rotacionar        = "aws ssm put-parameter --name /pixbank/prod/db/senha ..."
```

**Anote as duas primeiras.**

> Se falhar com `EntityAlreadyExists` no provedor OIDC, ele já existe na conta
> (é um por conta, não um por repositório). Importe e repita o apply:
> ```bash
> terraform import aws_iam_openid_connect_provider.github \
>   arn:aws:iam::<sua-conta>:oidc-provider/token.actions.githubusercontent.com
> ```

## 3.1 Gravar a senha de verdade no cofre

O Terraform criou o parâmetro com um valor de fachada e tem
`ignore_changes = [value]` justamente para nunca mais tocar nele. Grave o valor
real pela CLI — assim ele **não entra no arquivo de estado**, que é texto claro:

```bash
aws ssm put-parameter \
  --name /pixbank/prod/db/senha \
  --type SecureString \
  --value "$(openssl rand -base64 24)" \
  --overwrite
```

**Conferir:**

```bash
curl -s "<url_da_funcao>" | python3 -m json.tool
```

Esperado — e este é o resultado que vale a viagem:

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

Se responder `"origem": "indisponivel"`, veja o anexo.

---

# Parte 4 — Ligar GitHub e AWS por OIDC (15 min)

## 4.1 Cadastrar o ARN da role

No repositório: **Settings** → **Secrets and variables** → **Actions** → aba
**Variables** → **New repository variable**

| Nome | Valor |
|---|---|
| `AWS_ROLE_ARN` | o `role_arn_para_o_github` da parte 3 |

**Variable, não Secret.** Um ARN de role é um identificador público, não um
segredo. Quem tentar assumir a role sem um token OIDC válido, do repositório
certo e da branch certa, é recusado pela condição `sub` da própria role.
Guardar ARN como segredo é hábito sem motivo — e ensina a turma errado.

## 4.2 Criar o ambiente de produção

**Settings** → **Environments** → **New environment** → nome `producao`.

O workflow do gabarito declara `environment: producao`. Se você quiser mostrar
aprovação manual antes de publicar, marque *Required reviewers* e coloque você
mesmo. Se não quiser, o ambiente vazio já basta.

## 4.3 Trocar o workflow pelo gabarito e publicar

```bash
cp docs/gabarito/deploy.yml .github/workflows/deploy.yml
git add -A
git commit -m "publicar por OIDC, sem chave estática"
git push
```

Actions → *Publicar na AWS* → **Run workflow**.

**Conferir:** o passo `Conferir quem eu sou` (`aws sts get-caller-identity`)
mostra um ARN assumido com nome de sessão `gh-<run_id>`. Vale uma pausa em sala:
a identidade é temporária, nomeada e rastreável até a execução exata.

E o passo de auditoria da esteira agora deve passar. Rode local para confirmar:

```bash
cd .. && source .venv/bin/activate
gitleaks detect --source . --config .gitleaks.toml --report-format json \
  --report-path gitleaks-report.json --redact --exit-code 0 --no-git
python3 scripts/auditoria_higiene.py --gitleaks gitleaks-report.json | tail -6
```

> Ainda vai bloquear, porque o `config/legacy.js` continua no repositório — é a
> tarefa do Grupo 2, e é assim que tem de ser no dia da aula. Se quiser ver o
> LIBERADO agora, apague o arquivo numa branch descartável, rode, e volte.

---

# Parte 5 — Ensaio (20 min, na véspera)

Rode o roteiro inteiro uma vez, cronometrado, com a tela compartilhada como se
fosse a aula. É onde você descobre o que não cabe no tempo.

- [ ] `node app/index.js` e `curl localhost:3000/` mostrando `"origem": "codigo"`
- [ ] `python3 scripts/auditoria_higiene.py` → BLOQUEADO, e a saída **cabe numa
      tela compartilhada** (aumente a fonte do terminal antes)
- [ ] O `curl` na URL da AWS mostrando `"origem": "cofre"`
- [ ] A rotação ao vivo: anotar a impressão digital, `put-parameter`, esperar,
      `curl` de novo, impressão digital diferente
- [ ] Abrir a execução do Actions e mostrar o `get-caller-identity`
- [ ] Ler `docs/EXERCICIO.md` do começo ao fim, marcando o que você vai falar

**Sobre a rotação ao vivo — a única parte com risco de tempo.** A Lambda cacheia
a senha por contêiner. Depois do `put-parameter`, a impressão digital só muda
quando um contêiner novo atender. Duas formas de forçar:

```bash
# opção A: mexer numa variável qualquer força contêineres novos
aws lambda update-function-configuration \
  --function-name pixbank-credenciais \
  --environment "Variables={PIXBANK_PARAM_SENHA=/pixbank/prod/db/senha,PIXBANK_VERSAO=demo-$(date +%s)}"

# opção B: esperar alguns minutos sem tráfego
```

Use a opção A em sala. Meça quanto demora no seu ensaio e anote aqui: ______

---

# Parte 6 — O dia da aula (50 min)

## Antes de abrir a sala

- [ ] `export AWS_PROFILE=modulo14` e `source .venv/bin/activate` já rodados
- [ ] `curl` na URL da função respondendo (se a conta hibernou, republique)
- [ ] Fonte do terminal grande
- [ ] `relatorio-auditoria` salvo, como plano B
- [ ] Link do repositório à mão para colar no chat

## 0–7 min · Abertura (plenária)

Compartilhe a tela e rode:

```bash
node app/index.js &
curl -s localhost:3000/
```

Pergunte: **"se esta aplicação estivesse em produção e essa senha vazasse,
quanto tempo até ela parar de funcionar?"**

A resposta honesta é: até alguém abrir um PR, esperar revisão, publicar e
reiniciar. Guarde — no fim a resposta vai ser "um comando".

Depois:

```bash
python3 scripts/auditoria_higiene.py
```

**16 achados. BLOQUEADO.** É o ponto de partida de todos os grupos.

## 7–32 min · Salas de breakout (25 min)

Cinco grupos, conforme `docs/EXERCICIO.md`. Mande o link do repositório e o
número do grupo no chat de cada sala.

| Grupo | Perfil | Entregável |
|---|---|---|
| 1 | Segurança | Uma regra de varredura nova |
| 2 | Desenvolvimento | A aplicação lendo do cofre, sem caminho de volta |
| 3 | Operações/DevOps | O deploy por OIDC |
| 4 | Qualidade | A política de risco |
| 5 | Suporte | O plano das duas primeiras horas |

Passe pelas salas nesta ordem: **4, 5, 1, 2, 3**. Os grupos 4 e 5 travam mais
cedo, porque não têm código para se apoiar — e são os que produzem o conteúdo
mais valioso.

## 32–50 min · Apresentação cruzada (18 min)

Três minutos por grupo, **nesta ordem** — cada um depende do anterior:

1. **Qualidade** abre dizendo o que decidiu bloquear.
2. **Segurança** mostra o que a varredura pega e o que ela ignora.
3. **Desenvolvimento** mostra o `curl` respondendo `"origem": "cofre"`.
4. **Operações** mostra a auditoria em LIBERADO.
5. **Suporte** fecha com o plano — e com a lista do que a esteira **não**
   verifica.

## Fechamento — a demonstração na AWS

Aqui entra o que você preparou:

```bash
curl -s "<url_da_funcao>" | python3 -m json.tool     # anote a impressão digital

aws ssm put-parameter --name /pixbank/prod/db/senha \
  --type SecureString --value "$(openssl rand -base64 24)" --overwrite

# forçar contêiner novo (opção A do ensaio)
aws lambda update-function-configuration --function-name pixbank-credenciais \
  --environment "Variables={PIXBANK_PARAM_SENHA=/pixbank/prod/db/senha,PIXBANK_VERSAO=demo-$(date +%s)}"

curl -s "<url_da_funcao>" | python3 -m json.tool     # impressão digital diferente
```

**Sem commit, sem PR, sem deploy.** E a pergunta da abertura volta:

> Quanto tempo levaria para trocar a senha do banco do sistema de vocês, hoje?

E a que fecha o módulo, do roteiro do Grupo 5:

> Quantas credenciais de longa duração existem hoje no ambiente de vocês?
> Se a resposta não for um número, essa é a primeira tarefa — não a rotação.

---

# Parte 7 — Desmontar (10 min, no mesmo dia)

## 7.1 Destruir a infraestrutura

```bash
cd infra && terraform destroy
```

**Conferir:** o `curl` na URL da função passa a falhar.

## 7.2 Revogar a chave estática — de preferência na frente da turma

```bash
aws iam list-access-keys --user-name terraform-modulo14
aws iam delete-access-key --user-name terraform-modulo14 --access-key-id AKIA...
```

Este é o comando que o Grupo 3 apresentou como "a parte que a esteira não faz
por você". Rodá-lo ao vivo fecha o argumento do módulo: **trocar o método sem
revogar a chave antiga não resolve nada.**

Se quiser, apague também o usuário:

```bash
aws iam detach-user-policy --user-name terraform-modulo14 \
  --policy-arn arn:aws:iam::aws:policy/AdministratorAccess
aws iam delete-user --user-name terraform-modulo14
```

## 7.3 O repositório

Se publicou como público, considere arquivar ou tornar privado. Um repositório
com credenciais de exemplo e o nome de uma instituição financeira no README não
precisa ficar indexado para sempre.

## 7.4 Conferir a fatura

Uma semana depois, olhe o Cost Explorer. Deve estar zerado. Se não estiver, o
alerta de orçamento da parte 1.2 já terá avisado.

---

# Anexo — quando der errado

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| `Not authorized to perform sts:AssumeRoleWithWebIdentity` | a condição `sub` não bate | confira `github_org`, `github_repo` e `branch_permitida`; a branch tem de ser exatamente a que dispara o workflow |
| `Credentials could not be loaded` no Actions | falta `id-token: write` | tem de estar **no job**, não só no topo do arquivo |
| `EntityAlreadyExists` no provedor OIDC | já existe na conta | `terraform import` (parte 3) |
| A URL da função responde **403** | permissão de invocação ausente | o `aws_lambda_permission.invocar_pela_url` cobre isso; se editou o Terraform, confira que ele existe |
| A função responde `"origem": "ambiente"` | sobrou `DB_PASSWORD` na configuração da função | remova — é literalmente o achado H8 |
| A função responde `"origem": "indisponivel"` | a role de execução não lê o parâmetro, ou o nome está errado | confira `PIXBANK_PARAM_SENHA` e o log em CloudWatch; ligue `PIXBANK_DEBUG=1` |
| `externally-managed-environment` no `pip` | Python do sistema no macOS | use o `.venv` da parte 0.2 |
| `python3 scripts/auditoria_higiene.py` diz `Falta o PyYAML` | esqueceu de ativar o ambiente | `source .venv/bin/activate` |
| Push bloqueado pelo GitHub | push protection funcionando | é conteúdo, não erro — parte 2.2 |
| A rotação não muda a impressão digital | contêiner da Lambda ainda cacheado | opção A do ensaio (parte 5) |

**Se nada funcionar no dia:** todo o exercício roda localmente. A AWS é
demonstração, e o Actions é conveniência. Com o repositório clonado, um terminal
e o `.venv` ativo, a aula acontece inteira.
