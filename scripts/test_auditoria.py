#!/usr/bin/env python3
"""
Testes do auditor de higiene.

Rodar:  python3 scripts/test_auditoria.py

O teste que carrega a tese do módulo é `test_corrigir_para_oidc_muda_o_veredito`:
o mesmo repositório, o mesmo código de aplicação, a mesma política — e o
resultado muda de BLOQUEADO para LIBERADO só porque a esteira parou de guardar
credencial de longa duração.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

import auditoria_higiene as aud  # noqa: E402


WORKFLOW_RUIM = """
name: deploy
on: [workflow_dispatch]
jobs:
  publicar:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: sa-east-1
      - run: aws lambda update-function-code --function-name x --zip-file fileb://f.zip
"""

WORKFLOW_BOM = """
name: deploy
on: [workflow_dispatch]
permissions:
  contents: read
jobs:
  publicar:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      id-token: write
    steps:
      - uses: actions/checkout@v4
        with:
          persist-credentials: false
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::000000000000:role/exemplo
          aws-region: sa-east-1
      - run: aws lambda update-function-code --function-name x --zip-file fileb://f.zip
"""

POLITICA = """
bloqueia_a_partir_de:
  CRITICA: 0
  ALTA: 0
  MEDIA: 3
regras_isentas:
  - H4
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / ".github" / "workflows").mkdir(parents=True)
        (self.tmp / "app").mkdir()
        (self.tmp / "config").mkdir()
        (self.tmp / "scripts").mkdir()
        (self.tmp / "scripts" / "politica.yaml").write_text(POLITICA, encoding="utf-8")
        self._raiz_original = aud.RAIZ
        aud.RAIZ = self.tmp

    def tearDown(self):
        aud.RAIZ = self._raiz_original
        shutil.rmtree(self.tmp, ignore_errors=True)

    def workflow(self, nome: str, conteudo: str):
        (self.tmp / ".github" / "workflows" / nome).write_text(conteudo, encoding="utf-8")

    def politica(self):
        import yaml
        return yaml.safe_load(POLITICA)

    def veredito(self):
        achados = aud.coletar()
        bloqueia, razoes = aud.aplicar_politica(achados, self.politica())
        return achados, bloqueia, razoes

    def regras(self, achados):
        return sorted({a.regra for a in achados})


class TestRegras(Base):
    def test_h1_pega_chave_estatica(self):
        self.workflow("deploy.yml", WORKFLOW_RUIM)
        achados, _, _ = self.veredito()
        h1 = [a for a in achados if a.regra == "H1"]
        self.assertEqual(len(h1), 2, "deve pegar a access key e a secret key")
        self.assertTrue(all(a.severidade == "CRITICA" for a in h1))

    def test_h2_pega_deploy_sem_oidc(self):
        self.workflow("deploy.yml", WORKFLOW_RUIM)
        achados, _, _ = self.veredito()
        self.assertTrue(any(a.regra == "H2" for a in achados))

    def test_h2_nao_reclama_quando_ha_oidc(self):
        self.workflow("deploy.yml", WORKFLOW_BOM)
        achados, _, _ = self.veredito()
        self.assertFalse(any(a.regra == "H2" for a in achados))

    def test_h3_pega_workflow_sem_permissions(self):
        self.workflow("deploy.yml", WORKFLOW_RUIM)
        achados, _, _ = self.veredito()
        self.assertTrue(any(a.regra == "H3" for a in achados))

    def test_h4_pesa_menos_para_acao_oficial(self):
        self.workflow("deploy.yml", WORKFLOW_RUIM)
        achados, _, _ = self.veredito()
        h4 = {a.contexto: a.severidade for a in achados if a.regra == "H4"}
        self.assertEqual(h4.get("actions/checkout@v4"), "BAIXA")
        self.assertEqual(h4.get("aws-actions/configure-aws-credentials@v4"), "MEDIA")

    def test_h5_pega_eco_de_segredo(self):
        self.workflow(
            "vaza.yml",
            "name: x\non: [push]\npermissions:\n  contents: read\n"
            "jobs:\n  a:\n    runs-on: ubuntu-latest\n    permissions:\n      contents: read\n"
            "    steps:\n      - run: echo ${{ secrets.DB_PASSWORD }}\n",
        )
        achados, _, _ = self.veredito()
        self.assertTrue(any(a.regra == "H5" for a in achados))

    def test_h6_e_critica_quando_o_app_carrega_o_arquivo(self):
        (self.tmp / "config" / "legacy.js").write_text(
            "module.exports = { db: { senha: 'troque-me' } };", encoding="utf-8"
        )
        (self.tmp / "app" / "credencial.js").write_text(
            "const legado = require('../config/legacy.js');", encoding="utf-8"
        )
        achados, _, _ = self.veredito()
        h6 = [a for a in achados if a.regra == "H6"]
        self.assertEqual(len(h6), 1)
        self.assertEqual(h6[0].severidade, "CRITICA")

    def test_h6_cai_para_media_quando_nao_e_alcancavel(self):
        (self.tmp / "config" / "legacy.js").write_text(
            "module.exports = { db: { senha: 'troque-me' } };", encoding="utf-8"
        )
        (self.tmp / "app" / "index.js").write_text("// nada carrega o legado", encoding="utf-8")
        achados, _, _ = self.veredito()
        h6 = [a for a in achados if a.regra == "H6"]
        self.assertEqual(h6[0].severidade, "MEDIA")

    def test_h7_pega_checkout_com_credencial(self):
        self.workflow("deploy.yml", WORKFLOW_RUIM)
        achados, _, _ = self.veredito()
        self.assertTrue(any(a.regra == "H7" for a in achados))

    def test_h7_aceita_persist_credentials_false(self):
        self.workflow("deploy.yml", WORKFLOW_BOM)
        achados, _, _ = self.veredito()
        self.assertFalse(any(a.regra == "H7" for a in achados))

    def test_h8_pega_segredo_como_variavel_de_ambiente(self):
        self.workflow(
            "deploy.yml",
            WORKFLOW_RUIM
            + '      - run: aws lambda update-function-configuration --environment '
              '"Variables={DB_PASSWORD=${{ secrets.DB_PASSWORD }}}"\n',
        )
        achados, _, _ = self.veredito()
        self.assertTrue(any(a.regra == "H8" for a in achados))

    def test_yaml_invalido_vira_achado_em_vez_de_explodir(self):
        self.workflow("quebrado.yml", "jobs:\n  a:\n   - isto: [nao\n")
        achados, _, _ = self.veredito()
        self.assertTrue(any(a.regra == "H0" for a in achados))


class TestDecisao(Base):
    def test_corrigir_para_oidc_muda_o_veredito(self):
        """A tese do módulo, como teste executável."""
        self.workflow("deploy.yml", WORKFLOW_RUIM)
        _, bloqueia_antes, razoes = self.veredito()
        self.assertTrue(bloqueia_antes, f"deveria bloquear; razões: {razoes}")

        self.workflow("deploy.yml", WORKFLOW_BOM)
        achados, bloqueia_depois, razoes = self.veredito()
        self.assertFalse(
            bloqueia_depois,
            "depois de trocar por OIDC deveria liberar; sobrou: "
            + ", ".join(f"{a.regra}/{a.severidade}" for a in achados),
        )

    def test_isencao_da_politica_nao_bloqueia(self):
        self.workflow("deploy.yml", WORKFLOW_BOM)
        achados, bloqueia, _ = self.veredito()
        self.assertTrue(any(a.regra == "H4" for a in achados), "H4 deve aparecer no relatório")
        self.assertFalse(bloqueia, "mas, isento pela política, não deve bloquear")

    def test_tirar_a_isencao_volta_a_bloquear(self):
        """Isenção é decisão de política, e decisão de política tem consequência."""
        self.workflow("deploy.yml", WORKFLOW_BOM)
        achados = aud.coletar()
        politica = {"bloqueia_a_partir_de": {"MEDIA": 0}, "regras_isentas": []}
        bloqueia, _ = aud.aplicar_politica(achados, politica)
        self.assertTrue(bloqueia)


class TestDeduplicacao(Base):
    def test_gitleaks_e_h6_no_mesmo_ponto_viram_um_achado(self):
        import json
        (self.tmp / "config" / "legacy.js").write_text(
            "module.exports = {\n  db: { senha: 'troque-me' }\n};", encoding="utf-8"
        )
        (self.tmp / "app" / "credencial.js").write_text(
            "require('../config/legacy.js');", encoding="utf-8"
        )
        linha = aud.numero_da_linha(
            (self.tmp / "config" / "legacy.js").read_text(encoding="utf-8"),
            "senha: 'troque-me'",
        )
        relatorio = self.tmp / "gl.json"
        relatorio.write_text(
            json.dumps(
                [{"File": "config/legacy.js", "StartLine": linha, "RuleID": "senha-em-codigo"}]
            ),
            encoding="utf-8",
        )
        achados = aud.coletar(relatorio)
        no_ponto = [a for a in achados if a.arquivo == "config/legacy.js" and a.linha == linha]
        self.assertEqual(len(no_ponto), 1, "duas ferramentas, um problema")
        self.assertEqual(no_ponto[0].regra, "H6")
        self.assertIn("Gitleaks", no_ponto[0].detalhe)

    def test_gitleaks_em_ponto_proprio_continua_aparecendo(self):
        import json
        relatorio = self.tmp / "gl.json"
        relatorio.write_text(
            json.dumps([{"File": "outro/arquivo.js", "StartLine": 7, "RuleID": "aws-key"}]),
            encoding="utf-8",
        )
        achados = aud.coletar(relatorio)
        self.assertTrue(any(a.regra == "H9" for a in achados))


if __name__ == "__main__":
    unittest.main(verbosity=2)
