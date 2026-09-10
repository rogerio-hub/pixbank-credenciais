###############################################################################
# Federação de identidade entre o GitHub Actions e a AWS.
#
# É este arquivo que elimina a chave estática. Sem ele, a esteira precisa de um
# par AKIA.../secret guardado em algum lugar. Com ele, o GitHub apresenta um
# token assinado dizendo "sou o workflow tal, do repositório tal, na branch
# tal", e a AWS troca esse token por uma credencial temporária.
#
# Custo: zero. Provider OIDC e role do IAM não são cobrados.
###############################################################################

# O provedor OIDC do GitHub na sua conta. Só precisa existir uma vez por conta.
# Se já existir, importe em vez de criar:
#   terraform import aws_iam_openid_connect_provider.github \
#     arn:aws:iam::<conta>:oidc-provider/token.actions.githubusercontent.com
resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]

  # Desde 2023 a AWS valida a cadeia de certificação por conta própria e a
  # impressão digital deixou de ser o ponto de confiança. O campo continua
  # obrigatório na API; este é o valor historicamente usado.
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

data "aws_iam_policy_document" "confianca_github" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    # Audiência: garante que o token foi emitido PARA a AWS.
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    # A condição que faz o trabalho de verdade.
    #
    # ATENÇÃO — o erro clássico é escrever `repo:${var.github_org}/*`, que
    # libera QUALQUER repositório da organização a assumir esta role. Pior
    # ainda é `repo:*`, que libera o GitHub inteiro. Amarre no repositório E na
    # referência:
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values = [
        "repo:${var.github_org}/${var.github_repo}:ref:refs/heads/${var.branch_permitida}",
        "repo:${var.github_org}/${var.github_repo}:environment:producao",
      ]
    }
  }
}

resource "aws_iam_role" "deploy" {
  name                 = "${var.nome_projeto}-deploy-github"
  description          = "Assumida pelo GitHub Actions via OIDC. Sem chave estática."
  assume_role_policy   = data.aws_iam_policy_document.confianca_github.json
  max_session_duration = 3600 # 1 hora, o mínimo permitido para a role

  tags = local.tags
}

# Permissões da esteira: só o que o deploy precisa, e só nesta função.
data "aws_iam_policy_document" "permissoes_deploy" {
  statement {
    sid    = "PublicarAFuncao"
    effect = "Allow"
    actions = [
      "lambda:UpdateFunctionCode",
      "lambda:UpdateFunctionConfiguration",
      "lambda:GetFunction",
      "lambda:GetFunctionConfiguration",
      "lambda:PublishVersion",
    ]
    resources = [aws_lambda_function.api.arn]
  }

  statement {
    sid       = "SaberQuemSou"
    effect    = "Allow"
    actions   = ["sts:GetCallerIdentity"]
    resources = ["*"]
  }

  # Repare no que NÃO está aqui: a esteira não pode ler o parâmetro do SSM.
  # Ela publica o código; quem lê o segredo é a função, em tempo de execução.
  # Separar essas duas permissões é o que impede um workflow comprometido de
  # simplesmente imprimir a senha.
}

resource "aws_iam_role_policy" "deploy" {
  name   = "${var.nome_projeto}-deploy"
  role   = aws_iam_role.deploy.id
  policy = data.aws_iam_policy_document.permissoes_deploy.json
}

output "role_arn_para_o_github" {
  description = "Cadastre em Settings > Secrets and variables > Actions > Variables como AWS_ROLE_ARN"
  value       = aws_iam_role.deploy.arn
}
