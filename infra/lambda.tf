###############################################################################
# A função e a role que ela usa em execução.
#
# Duas identidades diferentes, de propósito:
#   - a role de DEPLOY (oidc.tf) publica código e não lê segredo;
#   - a role de EXECUÇÃO (aqui) lê o segredo e não publica código.
#
# Custo: Lambda tem 1 milhão de requisições e 400 mil GB-s por mês na camada
# sempre gratuita. Function URL não cobra à parte. Este exemplo não sai do zero.
###############################################################################

data "aws_iam_policy_document" "confianca_lambda" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "execucao" {
  name               = "${var.nome_projeto}-execucao"
  description        = "Role de execução da função. Lê o parâmetro do SSM em runtime."
  assume_role_policy = data.aws_iam_policy_document.confianca_lambda.json
  tags               = local.tags
}

resource "aws_iam_role_policy_attachment" "logs" {
  role       = aws_iam_role.execucao.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

data "aws_iam_policy_document" "ler_segredo" {
  statement {
    sid       = "LerASenhaDoBanco"
    effect    = "Allow"
    actions   = ["ssm:GetParameter"]
    resources = [aws_ssm_parameter.senha_banco.arn] # um parâmetro, não `/pixbank/*`
  }

  statement {
    sid       = "DecifrarComAChaveGerenciadaDaAWS"
    effect    = "Allow"
    actions   = ["kms:Decrypt"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = ["ssm.${var.regiao}.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy" "ler_segredo" {
  name   = "${var.nome_projeto}-ler-segredo"
  role   = aws_iam_role.execucao.id
  policy = data.aws_iam_policy_document.ler_segredo.json
}

# Pacote inicial. A esteira substitui o código depois; o Terraform ignora
# mudanças de código para não desfazer o deploy a cada `apply`.
data "archive_file" "pacote" {
  type        = "zip"
  source_dir  = "${path.module}/../app"
  excludes    = ["test", "test/smoke.test.js"]
  output_path = "${path.module}/.build/funcao.zip"
}

resource "aws_lambda_function" "api" {
  function_name = var.nome_projeto
  role          = aws_iam_role.execucao.arn
  handler       = "index.handler"
  runtime       = "nodejs22.x"
  timeout       = 10
  memory_size   = 256

  filename         = data.archive_file.pacote.output_path
  source_code_hash = data.archive_file.pacote.output_base64sha256

  environment {
    variables = {
      # Só o NOME do parâmetro. O valor nunca entra aqui — variável de ambiente
      # de função aparece no console, na API de descrição e em dump de processo.
      PIXBANK_PARAM_SENHA = aws_ssm_parameter.senha_banco.name
      PIXBANK_VERSAO      = "terraform"
    }
  }

  lifecycle {
    ignore_changes = [filename, source_code_hash, environment]
  }

  tags = local.tags
}

resource "aws_lambda_function_url" "publica" {
  function_name      = aws_lambda_function.api.function_name
  authorization_type = "NONE" # exemplo de aula; em produção use AWS_IAM
}

# Pegadinha conhecida do Terraform: criar a Function URL com AuthType NONE
# NÃO cria sozinha a permissão de invocação. O console da AWS faz isso por baixo
# dos panos; o Terraform, não. Sem este recurso a URL responde 403 e você
# descobre na frente da turma.
resource "aws_lambda_permission" "invocar_pela_url" {
  statement_id           = "PermitirInvocacaoPelaFunctionURL"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.api.function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}

# Retenção curta de log: log de aplicação também é lugar onde segredo vaza,
# e o padrão da AWS é "nunca expira".
resource "aws_cloudwatch_log_group" "funcao" {
  name              = "/aws/lambda/${aws_lambda_function.api.function_name}"
  retention_in_days = 14
  tags              = local.tags
}

output "url_da_funcao" {
  description = "Abra no navegador para ver a origem da credencial"
  value       = aws_lambda_function_url.publica.function_url
}
