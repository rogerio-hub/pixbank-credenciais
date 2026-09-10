/**
 * De onde vem a senha do banco.
 *
 * Este arquivo é o coração do módulo. Ele resolve a credencial em três origens,
 * da pior para a melhor, e — o que importa em sala — **declara qual delas usou**.
 * O endpoint `/` da aplicação mostra essa origem, então dá para ver a mudança
 * acontecendo ao vivo, sem ler log nenhum.
 *
 *   1. codigo    — credencial escrita em config/legacy.js. Versionada. Péssima.
 *   2. ambiente  — credencial em variável de ambiente estática (.env, secret do
 *                  Actions colado na Lambda). Melhor que o código, mas continua
 *                  sendo um segredo de longa duração que alguém precisa rotacionar
 *                  na mão e que aparece em `env`, em dump de processo e em log.
 *   3. cofre     — credencial buscada no AWS SSM Parameter Store (SecureString)
 *                  em tempo de execução, com a Lambda autenticando pela própria
 *                  role de execução. Não existe segredo guardado na aplicação.
 *
 * O Gate 3 da esteira reprova enquanto a origem alcançável em produção for
 * `codigo` ou `ambiente`.
 */

'use strict';

const ORIGENS = {
  CODIGO: 'codigo',
  AMBIENTE: 'ambiente',
  COFRE: 'cofre',
};

// Cache de processo: em Lambda, o contêiner é reaproveitado entre invocações,
// então buscar o parâmetro uma vez por contêiner evita chamada e custo à toa.
let cache = null;

/**
 * Busca o parâmetro no SSM Parameter Store.
 * O SDK v3 já vem no runtime Node da Lambda — não precisa entrar no pacote.
 */
async function lerDoCofre(nomeParametro) {
  let ssm;
  try {
    // require dinâmico: se o SDK não estiver presente (execução local sem
    // dependências), caímos para a próxima origem em vez de quebrar.
    // eslint-disable-next-line global-require
    const { SSMClient, GetParameterCommand } = require('@aws-sdk/client-ssm');
    ssm = new SSMClient({});
    const resposta = await ssm.send(
      new GetParameterCommand({ Name: nomeParametro, WithDecryption: true })
    );
    return resposta.Parameter && resposta.Parameter.Value;
  } catch (erro) {
    if (process.env.PIXBANK_DEBUG) {
      console.error('[credencial] cofre indisponível:', erro.message);
    }
    return null;
  }
}

/**
 * Resolve a credencial do banco e devolve { valor, origem }.
 * NUNCA devolve o valor para fora da aplicação — veja `descrever()`.
 */
async function resolver() {
  if (cache) return cache;

  const nomeParametro = process.env.PIXBANK_PARAM_SENHA;
  if (nomeParametro) {
    const valor = await lerDoCofre(nomeParametro);
    if (valor) {
      cache = { valor, origem: ORIGENS.COFRE, detalhe: nomeParametro };
      return cache;
    }
  }

  if (process.env.DB_PASSWORD) {
    cache = {
      valor: process.env.DB_PASSWORD,
      origem: ORIGENS.AMBIENTE,
      detalhe: 'variável de ambiente DB_PASSWORD',
    };
    return cache;
  }

  // Último recurso: o arquivo legado. Existe só para o exercício ter um "antes".
  try {
    // eslint-disable-next-line global-require
    const legado = require('../config/legacy.js');
    cache = {
      valor: legado.db.senha,
      origem: ORIGENS.CODIGO,
      detalhe: 'config/legacy.js (versionado no repositório)',
    };
    return cache;
  } catch (erro) {
    cache = { valor: null, origem: null, detalhe: 'nenhuma credencial disponível' };
    return cache;
  }
}

/**
 * Descrição segura da credencial, para o endpoint de status.
 * Devolve a origem e uma impressão digital curta — nunca o segredo.
 */
async function descrever() {
  const { valor, origem, detalhe } = await resolver();
  const crypto = require('crypto');
  return {
    origem: origem || 'indisponivel',
    detalhe,
    segura: origem === ORIGENS.COFRE,
    impressaoDigital: valor
      ? crypto.createHash('sha256').update(valor).digest('hex').slice(0, 12)
      : null,
  };
}

function limparCache() {
  cache = null;
}

module.exports = { ORIGENS, resolver, descrever, limparCache };
