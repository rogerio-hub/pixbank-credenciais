###############################################################################
# O cofre.
#
# SSM Parameter Store, tipo SecureString, camada Standard: **gratuito**.
# (O Secrets Manager cobra por segredo por mês — para esta aula não compensa,
# e a diferença que importa aqui é conceitual, não de produto: em ambos o
# segredo sai do código e passa a ser lido em tempo de execução.)
###############################################################################

resource "aws_ssm_parameter" "senha_banco" {
  name        = "/pixbank/prod/db/senha"
  description = "Senha do banco do PixBank. Lida pela função em tempo de execução."
  type        = "SecureString" # cifrado com a chave gerenciada da AWS para o SSM
  tier        = "Standard"     # camada gratuita

  # Valor inicial só para o exemplo funcionar. Em uso real, o valor NÃO fica no
  # Terraform — ele vazaria no arquivo de estado, que é texto claro. Grave uma
  # vez pela CLI e mantenha o `ignore_changes` abaixo:
  #
  #   aws ssm put-parameter --name /pixbank/prod/db/senha \
  #     --type SecureString --value "$(openssl rand -base64 24)" --overwrite
  #
  value = var.senha_inicial

  lifecycle {
    ignore_changes = [value]
  }

  tags = local.tags
}

output "como_rotacionar" {
  description = "Rotação de senha sem release: um comando, efeito imediato na próxima invocação fria"
  value       = "aws ssm put-parameter --name ${aws_ssm_parameter.senha_banco.name} --type SecureString --overwrite --value \"$(openssl rand -base64 24)\""
}
