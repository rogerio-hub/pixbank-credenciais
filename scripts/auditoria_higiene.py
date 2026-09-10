#!/usr/bin/env python3
"""
Auditoria de higiene de credenciais — PixBank / Módulo 14 (DevSecOps).

A ideia deste script é simples e um pouco desconfortável: **a esteira audita a
própria esteira**. As mesmas perguntas que o módulo faz sobre a senha de uma
pessoa — ela é longa? é única? é rotacionada? está anotada em algum lugar? —
valem para as credenciais que a automação usa, e essas ninguém olha.

Sete regras, todas verificáveis sem conta em serviço nenhum:

  H1  Chave estática da AWS nos segredos do workflow          CRITICA
  H2  Deploy sem OIDC (sem id-token/role-to-assume)           ALTA
  H3  Workflow sem `permissions` declarado                    ALTA
  H4  Ação de terceiro presa a tag móvel em vez de SHA        MEDIA
  H5  Comando que ecoa segredo no log                         ALTA
  H6  Credencial versionada no código da aplicação            CRITICA
  H7  checkout mantendo credencial no disco do executor       MEDIA
  H8  Segredo injetado como variável de ambiente na função    ALTA

Uso:
    python3 scripts/auditoria_higiene.py                  # texto no terminal
    python3 scripts/auditoria_higiene.py --json saida.json
    python3 scripts/auditoria_higiene.py --politica scripts/politica.yaml

Saída: 0 se a política permitir a release, 1 se bloquear.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, asdict, field
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("Falta o PyYAML. Instale com:  pip install pyyaml")


RAIZ = Path(__file__).resolve().parent.parent

SEVERIDADES = {"CRITICA": 4, "ALTA": 3, "MEDIA": 2, "BAIXA": 1}

# Ações mantidas pelo próprio GitHub. Presas a tag, o risco é bem menor do que
# numa ação de terceiro — a regra H4 pesa isso.
ACOES_OFICIAIS = ("actions/", "github/")


@dataclass
class Achado:
    regra: str
    severidade: str
    titulo: str
    arquivo: str
    linha: int = 0
    detalhe: str = ""
    correcao: str = ""
    contexto: str = ""

    def chave(self) -> tuple:
        return (self.regra, self.arquivo, self.linha, self.contexto)


# --------------------------------------------------------------------------- utilidades

def arquivos_de_workflow() -> list[Path]:
    base = RAIZ / ".github" / "workflows"
    if not base.is_dir():
        return []
    return sorted(p for p in base.iterdir() if p.suffix in (".yml", ".yaml"))


def numero_da_linha(texto: str, agulha: str) -> int:
    for i, linha in enumerate(texto.splitlines(), 1):
        if agulha in linha:
            return i
    return 0


def carregar_yaml(caminho: Path):
    try:
        return yaml.safe_load(caminho.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as erro:
        return {"__erro__": str(erro)}


def jobs_de(doc: dict) -> dict:
    jobs = doc.get("jobs")
    return jobs if isinstance(jobs, dict) else {}


def passos_de(job: dict) -> list:
    passos = job.get("steps")
    return passos if isinstance(passos, list) else []


def tem_permissions(escopo) -> bool:
    return isinstance(escopo, (dict, str))


# --------------------------------------------------------------------------- regras

def h1_chave_estatica(caminho: Path, texto: str) -> list[Achado]:
    """Chave de longa duração da AWS entregue ao workflow por `secrets.*`."""
    achados = []
    padrao = re.compile(
        r"secrets\.\s*(AWS_ACCESS_KEY_ID|AWS_SECRET_ACCESS_KEY|AWS_SESSION_TOKEN)\b"
    )
    for i, linha in enumerate(texto.splitlines(), 1):
        for m in padrao.finditer(linha):
            achados.append(
                Achado(
                    regra="H1",
                    severidade="CRITICA",
                    titulo="Chave estática da AWS usada pela esteira",
                    arquivo=str(caminho.relative_to(RAIZ)),
                    linha=i,
                    contexto=m.group(1),
                    detalhe=(
                        "A esteira autentica na AWS com um par de chaves de longa duração "
                        "guardado nos segredos do repositório. Essa credencial não expira "
                        "sozinha, vale de qualquer lugar do mundo e sobrevive à saída de "
                        "quem a criou. É a versão-máquina da senha reutilizada."
                    ),
                    correcao=(
                        "Trocar por OIDC: declarar `permissions: id-token: write` e usar "
                        "`aws-actions/configure-aws-credentials` com `role-to-assume`. "
                        "Depois, APAGAR os segredos do repositório e revogar a chave no IAM — "
                        "trocar o método sem revogar a chave antiga não resolve nada."
                    ),
                )
            )
    return achados


def h2_deploy_sem_oidc(caminho: Path, texto: str, doc: dict) -> list[Achado]:
    """Workflow que faz deploy na AWS sem federação de identidade."""
    achados = []
    menciona_aws = bool(
        re.search(r"aws-actions/|aws\s+(lambda|s3|ssm|sts)\b|role-to-assume", texto)
    )
    if not menciona_aws:
        return achados

    usa_oidc = "role-to-assume" in texto
    if usa_oidc:
        return achados

    for nome_job, job in jobs_de(doc).items():
        if not isinstance(job, dict):
            continue
        corpo = yaml.safe_dump(job, allow_unicode=True)
        if not re.search(r"aws-actions/|aws\s+(lambda|s3|ssm|sts)\b", corpo):
            continue
        achados.append(
            Achado(
                regra="H2",
                severidade="ALTA",
                titulo="Deploy na AWS sem federação de identidade (OIDC)",
                arquivo=str(caminho.relative_to(RAIZ)),
                linha=numero_da_linha(texto, f"{nome_job}:"),
                contexto=nome_job,
                detalhe=(
                    "O job fala com a AWS mas não assume uma role por OIDC. Sem isso, "
                    "a única forma de autenticar é um segredo guardado — que é justamente "
                    "o que o módulo quer eliminar."
                ),
                correcao=(
                    "No job: `permissions: { id-token: write, contents: read }` e "
                    "`uses: aws-actions/configure-aws-credentials` com `role-to-assume: "
                    "arn:aws:iam::<conta>:role/<role>` e `aws-region`. Ver infra/oidc.tf."
                ),
            )
        )
    return achados


def h3_sem_permissions(caminho: Path, texto: str, doc: dict) -> list[Achado]:
    """`permissions` não declarado: o GITHUB_TOKEN entra com o escopo padrão."""
    achados = []
    if tem_permissions(doc.get("permissions")):
        return achados
    faltantes = [
        nome
        for nome, job in jobs_de(doc).items()
        if isinstance(job, dict) and not tem_permissions(job.get("permissions"))
    ]
    if not faltantes:
        return achados
    return [
        Achado(
            regra="H3",
            severidade="ALTA",
            titulo="Workflow sem `permissions` declarado",
            arquivo=str(caminho.relative_to(RAIZ)),
            linha=1,
            contexto=", ".join(faltantes),
            detalhe=(
                "Sem `permissions`, o GITHUB_TOKEN do job recebe o escopo padrão da "
                "organização — que em muitos repositórios ainda é escrita. Esse token é "
                "uma credencial: vive 1h, mas nesse tempo faz o que o escopo permitir."
            ),
            correcao=(
                "Declarar `permissions: { contents: read }` no topo do workflow e abrir "
                "apenas o que cada job precisar (`id-token: write` só no job de deploy)."
            ),
        )
    ]


def h4_acao_sem_sha(caminho: Path, texto: str) -> list[Achado]:
    """Ação de terceiro presa a tag móvel: a tag pode ser reapontada."""
    achados = []
    padrao = re.compile(r"^\s*-?\s*uses:\s*([^\s#]+)", re.M)
    for m in padrao.finditer(texto):
        ref = m.group(1).strip().strip("'\"")
        if ref.startswith(("./", "docker://")):
            continue
        if "@" not in ref:
            continue
        nome, versao = ref.rsplit("@", 1)
        if re.fullmatch(r"[0-9a-f]{40}", versao):
            continue
        oficial = nome.startswith(ACOES_OFICIAIS)
        achados.append(
            Achado(
                regra="H4",
                severidade="BAIXA" if oficial else "MEDIA",
                titulo="Ação referenciada por tag móvel, não por SHA",
                arquivo=str(caminho.relative_to(RAIZ)),
                linha=numero_da_linha(texto, ref),
                contexto=ref,
                detalhe=(
                    f"`{nome}` está preso à tag `{versao}`. Tag em Git é um ponteiro móvel: "
                    "quem controla o repositório da ação pode reapontá-la para outro commit, "
                    "e a sua esteira passa a executar código que você nunca revisou — com "
                    "acesso a todos os segredos daquele job."
                    + ("" if oficial else " Ação de terceiro: o risco é maior.")
                ),
                correcao=(
                    f"Prender ao SHA:  `uses: {nome}@<sha-de-40-caracteres>  # {versao}`. "
                    "Para descobrir o SHA:  git ls-remote https://github.com/"
                    f"{nome.split('/')[0]}/{nome.split('/')[1] if '/' in nome else ''} "
                    f"refs/tags/{versao}"
                ),
            )
        )
    return achados


def h5_eco_de_segredo(caminho: Path, texto: str) -> list[Achado]:
    """Comando que joga segredo no log do job."""
    achados = []
    padrao = re.compile(r"^\s*.*\b(echo|printf|cat|print)\b.*secrets\.", re.I)
    for i, linha in enumerate(texto.splitlines(), 1):
        if padrao.match(linha):
            achados.append(
                Achado(
                    regra="H5",
                    severidade="ALTA",
                    titulo="Segredo impresso no log do job",
                    arquivo=str(caminho.relative_to(RAIZ)),
                    linha=i,
                    contexto=linha.strip()[:80],
                    detalhe=(
                        "O GitHub mascara segredos no log, mas o mascaramento é textual: "
                        "quebra com base64, com o valor partido em pedaços ou dentro de JSON. "
                        "Log de esteira costuma ser retido por meses e lido por muito mais "
                        "gente do que o cofre."
                    ),
                    correcao="Remover. Para depurar, imprima só o comprimento ou um hash curto.",
                )
            )
    return achados


def h6_credencial_no_codigo() -> list[Achado]:
    """Credencial versionada e alcançável a partir do código da aplicação."""
    achados = []
    legado = RAIZ / "config" / "legacy.js"
    if not legado.exists():
        return achados

    texto = legado.read_text(encoding="utf-8")
    alcancavel = False
    origem = ""
    app = RAIZ / "app"
    if app.is_dir():
        for arquivo in app.rglob("*.js"):
            conteudo = arquivo.read_text(encoding="utf-8")
            if re.search(r"require\(\s*['\"][^'\"]*legacy(\.js)?['\"]\s*\)", conteudo):
                alcancavel = True
                origem = str(arquivo.relative_to(RAIZ))
                break

    for rotulo, padrao in (
        ("senha de banco", r"senha:\s*'([^']+)'"),
        ("chave de acesso AWS", r"accessKeyId:\s*'([^']+)'"),
        ("segredo de token", r"jwtSecret:\s*'([^']+)'"),
    ):
        m = re.search(padrao, texto)
        if not m:
            continue
        achados.append(
            Achado(
                regra="H6",
                severidade="CRITICA" if alcancavel else "MEDIA",
                titulo=f"Credencial versionada no código ({rotulo})",
                arquivo="config/legacy.js",
                linha=numero_da_linha(texto, m.group(0)),
                contexto=rotulo,
                detalhe=(
                    "Credencial em arquivo versionado. "
                    + (
                        f"E alcançável em produção: {origem} carrega este módulo. "
                        if alcancavel
                        else "Nenhum arquivo de app carrega este módulo — o risco é menor, "
                        "mas o segredo continua no histórico do Git. "
                    )
                    + "Apagar o arquivo não apaga o histórico: quem clonou uma vez, tem."
                ),
                correcao=(
                    "1) Rotacionar a credencial — ela deve ser considerada comprometida. "
                    "2) Remover o arquivo e ler o valor de um cofre em tempo de execução. "
                    "3) Só então limpar o histórico, se valer o custo."
                ),
            )
        )
    return achados


def h7_checkout_com_credencial(caminho: Path, texto: str, doc: dict) -> list[Achado]:
    """`actions/checkout` deixa o token no .git/config do executor por padrão."""
    achados = []
    for nome_job, job in jobs_de(doc).items():
        if not isinstance(job, dict):
            continue
        for passo in passos_de(job):
            if not isinstance(passo, dict):
                continue
            usa = str(passo.get("uses") or "")
            if not usa.startswith("actions/checkout"):
                continue
            com = passo.get("with") or {}
            if isinstance(com, dict) and com.get("persist-credentials") in (False, "false"):
                continue
            achados.append(
                Achado(
                    regra="H7",
                    severidade="MEDIA",
                    titulo="checkout mantém a credencial no disco do executor",
                    arquivo=str(caminho.relative_to(RAIZ)),
                    linha=numero_da_linha(texto, "actions/checkout"),
                    contexto=nome_job,
                    detalhe=(
                        "Por padrão o checkout grava o token em .git/config do executor. "
                        "Qualquer passo seguinte — inclusive um script de dependência — "
                        "consegue lê-lo e empurrar commit em nome da esteira."
                    ),
                    correcao="Acrescentar `with: { persist-credentials: false }` ao passo.",
                )
            )
    return achados


def h8_segredo_como_variavel(caminho: Path, texto: str) -> list[Achado]:
    """Segredo injetado como variável de ambiente da função implantada."""
    achados = []
    padrao = re.compile(r"(DB_PASSWORD|DB_SENHA|SENHA_BANCO)\s*[:=]", re.I)
    for i, linha in enumerate(texto.splitlines(), 1):
        if not padrao.search(linha):
            continue
        if "secrets." not in linha and "var." not in linha and "${" not in linha:
            continue
        achados.append(
            Achado(
                regra="H8",
                severidade="ALTA",
                titulo="Segredo entregue à aplicação como variável de ambiente",
                arquivo=str(caminho.relative_to(RAIZ)),
                linha=i,
                contexto=linha.strip()[:80],
                detalhe=(
                    "Variável de ambiente de função aparece no console, na API de "
                    "descrição da função, em dump de processo e em qualquer erro que "
                    "serialize o ambiente. E o valor só muda com um novo deploy — "
                    "rotação vira release."
                ),
                correcao=(
                    "Passar apenas o NOME do parâmetro (PIXBANK_PARAM_SENHA) e ler o "
                    "valor do SSM Parameter Store em tempo de execução, com a role de "
                    "execução da função. Ver app/credencial.js."
                ),
            )
        )
    return achados


# --------------------------------------------------------------------------- execução

def h9_ingerir_gitleaks(caminho_relatorio: Path) -> list[Achado]:
    """Traz os achados do Gitleaks para a mesma fila de decisão.

    O Gitleaks roda com `--exit-code 0` de propósito: ele produz evidência, não
    veredito. Quem decide é a política — um lugar só. Ter seis ferramentas
    capazes de reprovar a release é ter seis donas de política e nenhuma
    priorização.
    """
    if not caminho_relatorio.exists():
        return []
    try:
        dados = json.loads(caminho_relatorio.read_text(encoding="utf-8") or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(dados, list):
        return []

    achados = []
    for item in dados:
        arquivo = item.get("File", "?")
        regra_id = item.get("RuleID", "?")
        achados.append(
            Achado(
                regra="H9",
                severidade="CRITICA",
                titulo=f"Segredo encontrado pelo Gitleaks ({regra_id})",
                arquivo=arquivo,
                linha=int(item.get("StartLine") or 0),
                contexto=regra_id,
                detalhe=(
                    f"Regra `{regra_id}` casou em `{arquivo}`. "
                    f"Commit {(str(item['Commit'])[:8] if item.get('Commit') else 'árvore de trabalho')}, "
                    f"autor {item.get('Author') or 'n/d'}. "
                    "Segredo em repositório deve ser tratado como comprometido a partir "
                    "do momento em que foi empurrado, não a partir de agora."
                ),
                correcao=(
                    "Rotacionar primeiro, remover depois. A ordem importa: remover o "
                    "arquivo sem rotacionar deixa a credencial válida no histórico."
                ),
            )
        )
    return achados


def coletar(relatorio_gitleaks: Path | None = None) -> list[Achado]:
    achados: list[Achado] = []
    if relatorio_gitleaks:
        achados += h9_ingerir_gitleaks(relatorio_gitleaks)
    for caminho in arquivos_de_workflow():
        texto = caminho.read_text(encoding="utf-8")
        doc = carregar_yaml(caminho)
        if "__erro__" in doc:
            achados.append(
                Achado(
                    regra="H0",
                    severidade="ALTA",
                    titulo="Workflow com YAML inválido",
                    arquivo=str(caminho.relative_to(RAIZ)),
                    detalhe=doc["__erro__"],
                    correcao="Corrigir a sintaxe do arquivo.",
                )
            )
            continue
        achados += h1_chave_estatica(caminho, texto)
        achados += h2_deploy_sem_oidc(caminho, texto, doc)
        achados += h3_sem_permissions(caminho, texto, doc)
        achados += h4_acao_sem_sha(caminho, texto)
        achados += h5_eco_de_segredo(caminho, texto)
        achados += h7_checkout_com_credencial(caminho, texto, doc)
        achados += h8_segredo_como_variavel(caminho, texto)

    for tf in sorted((RAIZ / "infra").glob("*.tf")) if (RAIZ / "infra").is_dir() else []:
        achados += h8_segredo_como_variavel(tf, tf.read_text(encoding="utf-8"))

    achados += h6_credencial_no_codigo()

    vistos, unicos = set(), []
    for a in achados:
        if a.chave() in vistos:
            continue
        vistos.add(a.chave())
        unicos.append(a)

    unicos = deduplicar_entre_ferramentas(unicos)
    unicos.sort(key=lambda a: (-SEVERIDADES.get(a.severidade, 0), a.regra, a.arquivo, a.linha))
    return unicos


def deduplicar_entre_ferramentas(achados: list[Achado]) -> list[Achado]:
    """Funde o achado do Gitleaks (H9) com o desta auditoria (H6) no mesmo ponto.

    Duas ferramentas apontando a mesma linha é UM problema, não dois. Contá-lo
    duas vezes infla o painel, empurra a política para bloquear pelo motivo
    errado e treina o time a ignorar o número. Reconciliar achados de
    ferramentas diferentes é o trabalho chato que separa uma esteira de uma
    planilha de findings.
    """
    por_ponto: dict[tuple, Achado] = {}
    for a in achados:
        if a.regra == "H6":
            por_ponto[(a.arquivo, a.linha)] = a

    resultado = []
    for a in achados:
        if a.regra == "H9":
            base = por_ponto.get((a.arquivo, a.linha))
            if base is not None:
                # Duas regras do Gitleaks podem casar na MESMA linha. Nesse caso
                # acumulamos os nomes numa frase só, em vez de repetir a frase
                # inteira — senão o relatório fica dizendo "confirmado também
                # pelo Gitleaks" duas vezes seguidas no mesmo achado.
                marca = " Confirmado também pelo Gitleaks (regra"
                if marca in base.detalhe:
                    base.detalhe = base.detalhe.rstrip().rstrip(").")
                    base.detalhe += f", `{a.contexto}`)."
                else:
                    base.detalhe += f"{marca} `{a.contexto}`)."
                continue
        resultado.append(a)
    return resultado


def aplicar_politica(achados: list[Achado], politica: dict) -> tuple[bool, list[str]]:
    """Devolve (bloqueia, razões)."""
    limites = politica.get("bloqueia_a_partir_de", {})
    isentas = set(politica.get("regras_isentas", []) or [])
    razoes = []

    contagem: dict[str, int] = {}
    for a in achados:
        if a.regra in isentas:
            continue
        contagem[a.severidade] = contagem.get(a.severidade, 0) + 1

    for severidade, maximo in limites.items():
        atual = contagem.get(severidade, 0)
        if atual > maximo:
            razoes.append(
                f"{atual} achado(s) de severidade {severidade}; a política tolera no máximo {maximo}"
            )
    return bool(razoes), razoes


def imprimir(achados: list[Achado], bloqueia: bool, razoes: list[str], isentas: set) -> None:
    largura = 78
    print("=" * largura)
    print("AUDITORIA DE HIGIENE DE CREDENCIAIS — PixBank / Módulo 14")
    print("=" * largura)
    if not achados:
        print("\nNenhum achado. A esteira não guarda credencial de longa duração.\n")
    for i, a in enumerate(achados, 1):
        marca = "  (isenta pela política)" if a.regra in isentas else ""
        local = f"{a.arquivo}:{a.linha}" if a.linha else a.arquivo
        print(f"\n#{i:<3} [{a.severidade:<7}] {a.regra}  {a.titulo}{marca}")
        print(f"     {local}" + (f"   ·  {a.contexto}" if a.contexto else ""))
        print(f"     {a.detalhe}")
        print(f"     Correção: {a.correcao}")
    print("\n" + "-" * largura)
    resumo: dict[str, int] = {}
    for a in achados:
        resumo[a.severidade] = resumo.get(a.severidade, 0) + 1
    linha = "  ".join(f"{s}: {resumo.get(s, 0)}" for s in ("CRITICA", "ALTA", "MEDIA", "BAIXA"))
    print(f"Total: {len(achados)} achado(s)   |   {linha}")
    if bloqueia:
        print("\nRESULTADO: BLOQUEADO")
        for r in razoes:
            print(f"  - {r}")
    else:
        print("\nRESULTADO: LIBERADO")
    print("-" * largura)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--politica", default=str(RAIZ / "scripts" / "politica.yaml"))
    p.add_argument(
        "--gitleaks",
        help="relatório JSON do Gitleaks, para entrar na mesma fila de decisão",
    )
    p.add_argument("--json", help="grava o relatório em JSON no caminho indicado")
    p.add_argument("--md", help="grava um resumo em Markdown (para o sumário do job)")
    args = p.parse_args()

    politica = {}
    caminho_politica = Path(args.politica)
    if caminho_politica.exists():
        politica = yaml.safe_load(caminho_politica.read_text(encoding="utf-8")) or {}

    achados = coletar(Path(args.gitleaks) if args.gitleaks else None)
    bloqueia, razoes = aplicar_politica(achados, politica)
    isentas = set(politica.get("regras_isentas", []) or [])
    imprimir(achados, bloqueia, razoes, isentas)

    if args.json:
        Path(args.json).write_text(
            json.dumps(
                {
                    "achados": [asdict(a) for a in achados],
                    "bloqueia": bloqueia,
                    "razoes": razoes,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    if args.md:
        linhas = ["## Auditoria de higiene de credenciais", ""]
        if not achados:
            linhas.append("Nenhum achado.")
        else:
            linhas += ["| Sev. | Regra | Onde | Achado |", "|---|---|---|---|"]
            for a in achados:
                local = f"`{a.arquivo}:{a.linha}`" if a.linha else f"`{a.arquivo}`"
                linhas.append(f"| {a.severidade} | {a.regra} | {local} | {a.titulo} |")
        linhas += ["", f"**Resultado: {'BLOQUEADO' if bloqueia else 'LIBERADO'}**"]
        for r in razoes:
            linhas.append(f"- {r}")
        Path(args.md).write_text("\n".join(linhas) + "\n", encoding="utf-8")

    return 1 if bloqueia else 0


if __name__ == "__main__":
    sys.exit(main())
