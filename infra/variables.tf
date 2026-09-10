variable "regiao" {
  description = "Região da AWS"
  type        = string
  default     = "sa-east-1"
}

variable "nome_projeto" {
  description = "Prefixo dos recursos"
  type        = string
  default     = "pixbank-credenciais"
}

variable "github_org" {
  description = "Organização ou usuário dono do repositório no GitHub"
  type        = string
}

variable "github_repo" {
  description = "Nome do repositório no GitHub"
  type        = string
  default     = "pixbank-credenciais"
}

variable "branch_permitida" {
  description = <<-TXT
    Única branch autorizada a assumir a role de deploy.

    Não troque por "*". A condição `sub` é o que impede que um pull request
    vindo de um fork qualquer assuma a sua role e publique na sua conta.
  TXT
  type        = string
  default     = "main"
}

variable "senha_inicial" {
  description = <<-TXT
    Valor inicial do parâmetro, só para o exemplo subir.

    Em uso real, NÃO passe segredo por variável do Terraform: ele vai parar no
    arquivo de estado, que é texto claro. Grave o valor uma vez pela CLI
    (`aws ssm put-parameter --overwrite`) — o `ignore_changes` no recurso
    garante que o Terraform não vai sobrescrever depois.
  TXT
  type        = string
  sensitive   = true
  default     = "troque-me-na-primeira-rotacao"
}
