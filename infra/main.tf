terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }
}

provider "aws" {
  region = var.regiao
}

locals {
  tags = {
    Projeto   = var.nome_projeto
    Curso     = "DevSecOps - Modulo 14"
    Ambiente  = "demonstracao"
    Terraform = "true"
  }
}
