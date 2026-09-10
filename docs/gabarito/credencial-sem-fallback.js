/**
 * GABARITO do Grupo 2. Substitui app/credencial.js — e vem junto com
 * `rm config/legacy.js`.
 *
 * A mudança em uma frase: **sumiu o caminho de volta**.
 *
 * A versão do exercício tentava o cofre, depois a variável de ambiente, depois
 * o arquivo versionado. Um fallback assim é confortável e traiçoeiro: no dia em
 * que a permissão do SSM quebrar, a aplicação continua respondendo — usando a
 * senha antiga, do código, que ninguém rotaciona há dois anos. E ninguém fica
 * sabendo, porque não houve erro.
 *
 * Aqui a aplicação falha alto. Sem credencial de origem aceitável, ela recusa
 * a requisição com 503 e diz o motivo. Falhar de forma visível é um requisito
 * de segurança, não um detalhe de robustez.
 *
 * A variável de ambiente continua existindo, mas só para desenvolvimento local,
 * e a origem é marcada como insegura — o endpoint `/` denuncia.
 */

'use strict';

const crypto = require('crypto');

const ORIGENS = {
  AMBIENTE: 'ambiente',
  COFRE: 'cofre',
};

let cache = null;

async function lerDoCofre(nomeParametro) {
  const { SSMClient, GetParameterCommand } = require('@aws-sdk/client-ssm');
  const ssm = new SSMClient({});
  const resposta = await ssm.send(
    new GetParameterCommand({ Name: nomeParametro, WithDecryption: true })
  );
  return resposta.Parameter && resposta.Parameter.Value;
}

async function resolver() {
  if (cache) return cache;

  const nomeParametro = process.env.PIXBANK_PARAM_SENHA;
  if (nomeParametro) {
    // Sem try/catch engolindo o erro: se o cofre está configurado e não
    // responde, isso é um incidente, não um detalhe a contornar em silêncio.
    const valor = await lerDoCofre(nomeParametro);
    if (!valor) {
      throw new Error(`Parâmetro ${nomeParametro} existe mas veio vazio do cofre`);
    }
    cache = { valor, origem: ORIGENS.COFRE, detalhe: nomeParametro };
    return cache;
  }

  if (process.env.DB_PASSWORD) {
    if (process.env.NODE_ENV === 'production') {
      throw new Error(
        'DB_PASSWORD como variável de ambiente não é aceito em produção. ' +
          'Configure PIXBANK_PARAM_SENHA apontando para o parâmetro no cofre.'
      );
    }
    cache = {
      valor: process.env.DB_PASSWORD,
      origem: ORIGENS.AMBIENTE,
      detalhe: 'variável de ambiente (aceito apenas fora de produção)',
    };
    return cache;
  }

  // Sem terceira opção. É este o ponto do gabarito.
  throw new Error(
    'Nenhuma credencial disponível. Defina PIXBANK_PARAM_SENHA (cofre) ou, ' +
      'apenas em desenvolvimento, DB_PASSWORD.'
  );
}

async function descrever() {
  try {
    const { valor, origem, detalhe } = await resolver();
    return {
      origem,
      detalhe,
      segura: origem === ORIGENS.COFRE,
      impressaoDigital: crypto.createHash('sha256').update(valor).digest('hex').slice(0, 12),
    };
  } catch (erro) {
    // A mensagem de erro é segura: ela nomeia a configuração que falta, nunca
    // o valor que se procurava.
    return { origem: 'indisponivel', detalhe: erro.message, segura: false, impressaoDigital: null };
  }
}

function limparCache() {
  cache = null;
}

module.exports = { ORIGENS, resolver, descrever, limparCache };
