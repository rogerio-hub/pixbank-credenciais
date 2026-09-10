/**
 * ATENÇÃO — ARQUIVO DELIBERADAMENTE INSEGURO.
 *
 * Este é o "antes" do exercício: credenciais escritas no código e versionadas
 * no repositório. Nenhum destes valores é real; todos foram inventados para a
 * aula. Ainda assim, é exatamente assim que a maioria dos vazamentos começa.
 *
 * O Gate 1 da esteira (Gitleaks) existe para reprovar este arquivo.
 * Ao final do exercício ele deve ter sido apagado.
 */

module.exports = {
  // 1) Senha de banco de produção em texto claro.
  db: {
    host: 'pixbank-prod.cluster-abc123.sa-east-1.rds.amazonaws.com',
    porta: 5432,
    usuario: 'pixbank_app',
    senha: 'Pixb@nk#Prod2023!',
  },

  // 2) Par de chaves estáticas da AWS. Repare no formato: uma chave assim,
  //    uma vez publicada, vale até alguém revogar — não expira sozinha.
  aws: {
    accessKeyId: 'AKIAIOSFODNN7EXAMPLE',
    secretAccessKey: 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
    regiao: 'sa-east-1',
  },

  // 3) Segredo de assinatura de token. Quem tem isto emite token de qualquer
  //    usuário, inclusive administrador.
  jwtSecret: 'pixbank-jwt-2021-nao-mudar',
};
