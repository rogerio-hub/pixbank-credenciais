/**
 * PixBank — consulta de saldo (aplicação de exemplo do Módulo 14).
 *
 * Dois modos de execução, mesmo código:
 *   - `node app/index.js`  → sobe um servidor HTTP local na porta 3000
 *   - Lambda               → exporta `handler` para uma Function URL
 *
 * O que interessa aqui não é o saldo. É o endpoint `/`, que declara DE ONDE a
 * aplicação tirou a senha do banco.
 */

'use strict';

const http = require('http');
const { descrever } = require('./credencial');

// "Banco de dados". Fictício, evidentemente.
const CONTAS = {
  '10021': { titular: 'Ana Prado', saldo: 4210.55 },
  '10022': { titular: 'Bruno Lima', saldo: 187.9 },
  '10023': { titular: 'Carla Souza', saldo: 92310.0 },
};

async function rotear(caminho, parametros) {
  if (caminho === '/' || caminho === '/status') {
    const credencial = await descrever();
    return {
      status: 200,
      corpo: {
        aplicacao: 'pixbank-credenciais',
        versao: process.env.PIXBANK_VERSAO || 'local',
        credencialDoBanco: credencial,
        recado: credencial.segura
          ? 'A senha veio do cofre, em tempo de execução. Não há segredo guardado nesta aplicação.'
          : 'A senha é um segredo de longa duração. Alguém precisa rotacionar isto na mão — e vai esquecer.',
      },
    };
  }

  if (caminho === '/saldo') {
    const conta = parametros.get('conta');
    if (!conta) return { status: 400, corpo: { erro: 'informe ?conta=' } };
    const registro = CONTAS[conta];
    if (!registro) return { status: 404, corpo: { erro: 'conta não encontrada' } };
    // A consulta só "acontece" se houver credencial resolvida.
    const credencial = await descrever();
    if (credencial.origem === 'indisponivel') {
      return { status: 503, corpo: { erro: 'sem credencial para consultar o banco' } };
    }
    return { status: 200, corpo: { conta, ...registro, origemDaCredencial: credencial.origem } };
  }

  return { status: 404, corpo: { erro: 'rota não encontrada' } };
}

/** Handler da Lambda (Function URL, formato payload 2.0). */
async function handler(evento) {
  const bruto = (evento && evento.rawPath) || '/';
  const consulta = new URLSearchParams((evento && evento.rawQueryString) || '');
  const { status, corpo } = await rotear(bruto, consulta);
  return {
    statusCode: status,
    headers: { 'content-type': 'application/json; charset=utf-8' },
    body: JSON.stringify(corpo, null, 2),
  };
}

/** Servidor local, para rodar sem AWS. */
function servidor(porta) {
  return http.createServer(async (req, res) => {
    const url = new URL(req.url, `http://localhost:${porta}`);
    const { status, corpo } = await rotear(url.pathname, url.searchParams);
    res.writeHead(status, { 'content-type': 'application/json; charset=utf-8' });
    res.end(JSON.stringify(corpo, null, 2));
  });
}

if (require.main === module) {
  const porta = Number(process.env.PORT || 3000);
  servidor(porta).listen(porta, () => {
    console.log(`PixBank ouvindo em http://localhost:${porta}`);
    console.log('Experimente:  curl localhost:%d/  e  curl "localhost:%d/saldo?conta=10021"', porta, porta);
  });
}

module.exports = { handler, servidor, rotear };
