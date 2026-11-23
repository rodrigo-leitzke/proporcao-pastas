# Cache Persistente Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tornar o cache de tamanhos/metadados persistente entre execuções, com indicador de data/hora do cache na tela e atualização seletiva por pasta.

**Architecture:** Um banco SQLite local (`sqlite3` da biblioteca padrão) guarda uma linha por pasta já varrida e os arquivos diretos de cada pasta. `FileSystemScanner` passa a consultar esse banco antes de tocar o disco e grava o resultado de cada varredura. O cache é preenchido **sob demanda** (a pasta que o usuário abre), não por varredura total dos discos no primeiro uso; varredura total existe como ação opcional. "Atualizar cache" revarre só a subárvore selecionada e propaga a diferença para os ancestrais.

**Tech Stack:** Python 3.8+, biblioteca padrão apenas (`sqlite3`, `tkinter`, `os`, `stat`, `threading`, `unittest`).

**Spec:** `/mnt/c/Users/cesoler/Downloads/PLANO_CACHE_PERSISTENTE.md` (plano original) + seção "Divergências em relação à spec" abaixo, que registra o que foi alterado e por quê.

## Global Constraints

- Python 3.8 ou superior. Proibido: `os.listdrives()` (3.12+), `dict | None` (3.10+), `list[str]` em anotação de runtime (usar `typing.List`).
- Zero dependência externa. Só biblioteca padrão (`README.md:26`).
- Windows 10/11 e macOS, ambos suportados (`README.md:25`). Nada específico de um SO fora de `system_roots.py`, `windows_context_menu.py`, `macos_context_menu.py`.
- Camadas: `domain` não importa `infrastructure` nem `presentation`; `application` não importa `presentation`.
- Identificadores e mensagens em português, seguindo o código atual (`tamanho`, `arquivos`, `subpastas`, `eh_pasta`). Comentários e docstrings **sem acento** (padrão do repositório); strings de interface **com** acento.
- Testes com `unittest` da biblioteca padrão, em `tests/`. Comando: `python -m unittest discover -s tests -t . -v`.
- Commits: prefixo `feat:`, `test:`, `fix:` ou `docs:` + descrição em português. Nunca adicionar trailer de co-autoria.

## Divergências em relação à spec

Registradas aqui porque mudam a arquitetura proposta no plano original:

1. **SQLite em vez de um JSON monolítico.** Medição com a estrutura exata do plano original: 100.000 pastas = 157 MB de JSON, 11,2s de `json.load`, 504 MB de RAM; extrapolando para 400-800 mil pastas (um C:\ real) dá 0,6-1,2 GB de arquivo, 45-90s de carregamento e 2-4 GB de RAM. A promessa de "carrega em menos de 1 segundo" não se sustenta, e cada clique em "Atualizar cache" reescreveria o arquivo inteiro. SQLite lê/escreve só as linhas necessárias. Se o formato JSON for exigido, a troca fica contida em `cache_storage.py` (mesma API pública).
2. **Sem varredura automática de todos os discos na primeira abertura.** O tamanho de uma pasta exige recursão completa da subárvore, então "mapear todos os discos" é inerentemente caro (minutos a dezenas de minutos) e deixaria a primeira abertura inutilizável. O cache passa a ser preenchido conforme o usuário navega, e a varredura total fica num botão opcional com progresso (Task 10).
3. **`maior_arquivo` não é propagado por delta.** `FolderStats.maior_arquivo_tam` é um **máximo recursivo** (`file_system.py:42-44`); máximo não se reconstrói somando diferenças. Guardamos também o maior arquivo **direto** de cada pasta e recalculamos o máximo dos ancestrais a partir dos filhos diretos em cache (Task 5).
4. **Delta de `arquivos` e `subpastas` fica como no plano original.** São contagens recursivas (`file_system.py:40-41`), então a soma de diferenças nos ancestrais é correta.
5. **Regra de desatualizado sem "24h".** O prazo fixo marcaria tudo como desatualizado depois de um dia e viraria ruído. Usamos comparação de `st_mtime` da pasta e das subpastas diretas em cache, mais um prazo configurável de 7 dias (`IDADE_MAXIMA_CACHE_SEG`).
6. **`FolderStats`/`ItemPasta` são `frozen=True`** (`models.py:6,15`): atualizar campo exige `dataclasses.replace()`, não atribuição.
7. **Escrita atômica continua garantida, por outro mecanismo.** O plano original usava `.tmp` + `os.replace()`. Com SQLite, cada gravação é uma transação com `journal_mode=WAL`: fechar o programa no meio de uma escrita não corrompe o banco, e não há arquivo temporário para gerenciar.
8. **`has_valid_cache()` deixa de existir.** Não há mais um arquivo único que está "válido" ou "inválido": a validade é por pasta (`get_folder()` devolve `None` quando aquela pasta nunca foi medida) e a versão do esquema fica em `meta.versao`, para migração futura.
9. **Árvore multi-raiz entra no escopo** (Task 9). O plano original promete "Árvore de Discos" no fluxograma mas não planeja a mudança; `definir_raiz()` (`tk_app.py:275`) assume um caminho único.

## Limitações aceitas (documentar no README, Task 11)

- Mudança profunda (arquivo alterado dentro de uma subpasta não listada) não é detectada pela checagem de `st_mtime`; a pasta pode aparecer como atualizada estando defasada. O prazo de 7 dias e o botão "Atualizar cache" são as saídas.
- Após "Atualizar cache" numa subpasta, os ancestrais ficam com tamanho correto para aquela mudança, mas não detectam alterações em pastas irmãs.
- O banco guarda caminhos e nomes de arquivos em texto plano no diretório de cache do usuário.

## File Structure

| Arquivo | Responsabilidade |
|---|---|
| `tests/__init__.py` (criar) | Marca `tests` como pacote para `python -m unittest tests.x` |
| `proporcao_pastas/domain/formatting.py` (modificar) | `formatar_data` com segundos opcionais, `formatar_status_cache` |
| `proporcao_pastas/domain/models.py` (modificar) | Campos `cache_updated_at` e `cache_desatualizado` |
| `proporcao_pastas/infrastructure/system_roots.py` (criar) | Raízes do SO e caminhos a ignorar na varredura |
| `proporcao_pastas/infrastructure/cache_storage.py` (criar) | `CachedFolder`, `SqliteCacheStorage` (esquema, leitura, escrita, delta) |
| `proporcao_pastas/infrastructure/file_system.py` (modificar) | `FileSystemScanner` usando o storage; `refresh_folder`, `is_folder_outdated` |
| `proporcao_pastas/application/analyze_folder.py` (modificar) | Campos de cache em `FolderAnalysis`; `AnalyzeFolder.refresh` |
| `proporcao_pastas/presentation/tk_app.py` (modificar) | Rótulo de status do cache, botão "Atualizar cache", coluna, árvore multi-raiz, varredura total |
| `proporcao_pastas/main.py` (modificar) | Abrir sem diálogo, em modo multi-raiz |
| `README.md` (modificar) | Documentar cache, local do banco e limitações |

---

### Task 1: Formatação de data/hora e status do cache

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/test_formatting_cache.py`
- Modify: `proporcao_pastas/domain/formatting.py:21-28`

**Interfaces:**
- Consumes: nada.
- Produces: `formatar_data(timestamp: Optional[float], segundos: bool = False) -> str`; `formatar_status_cache(cache_updated_at: Optional[float], global_updated_at: Optional[float], desatualizado: bool) -> str`.

- [ ] **Step 1: Write the failing test**

Criar `tests/__init__.py` vazio e `tests/test_formatting_cache.py`:

```python
"""Testes da formatacao de data e status do cache."""
import unittest
from datetime import datetime

from proporcao_pastas.domain.formatting import formatar_data, formatar_status_cache


def ts(texto):
    return datetime.strptime(texto, "%d/%m/%Y %H:%M:%S").timestamp()


class TestFormatarData(unittest.TestCase):
    def test_sem_segundos_por_padrao(self):
        self.assertEqual(formatar_data(ts("05/03/2026 14:07:09")), "05/03/2026 14:07")

    def test_com_segundos(self):
        self.assertEqual(
            formatar_data(ts("05/03/2026 14:07:09"), segundos=True),
            "05/03/2026 14:07:09",
        )

    def test_sem_timestamp(self):
        self.assertEqual(formatar_data(None), "—")
        self.assertEqual(formatar_data(0), "—")


class TestFormatarStatusCache(unittest.TestCase):
    def test_atualizado(self):
        texto = formatar_status_cache(ts("05/03/2026 14:07:09"), ts("05/03/2026 09:00:00"), False)
        self.assertEqual(
            texto,
            "✅ Cache atualizado, última vez atualizado: 05/03/2026 14:07:09 "
            "(Memória geral: 05/03/2026 09:00:00)",
        )

    def test_desatualizado(self):
        texto = formatar_status_cache(ts("05/03/2026 14:07:09"), ts("05/03/2026 09:00:00"), True)
        self.assertTrue(texto.startswith("⚠️ Cache desatualizado, última vez atualizado: "))

    def test_sem_cache(self):
        self.assertEqual(formatar_status_cache(None, None, False), "Pasta ainda não está em cache")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_formatting_cache -v`
Expected: FAIL — `ImportError: cannot import name 'formatar_status_cache'`.

- [ ] **Step 3: Write minimal implementation**

Em `formatting.py`, substituir `formatar_data` e acrescentar a nova função:

```python
def formatar_data(timestamp: Optional[float], segundos: bool = False) -> str:
    """Formata um timestamp POSIX em dd/mm/aaaa HH:MM (ou HH:MM:SS)."""
    if not timestamp:
        return "—"
    formato = "%d/%m/%Y %H:%M:%S" if segundos else "%d/%m/%Y %H:%M"
    try:
        return datetime.fromtimestamp(timestamp).strftime(formato)
    except (OSError, OverflowError, ValueError):
        return "—"


def formatar_status_cache(
    cache_updated_at: Optional[float],
    global_updated_at: Optional[float],
    desatualizado: bool,
) -> str:
    """Monta o texto do rotulo de status do cache."""
    if not cache_updated_at:
        return "Pasta ainda não está em cache"
    marca = "⚠️ Cache desatualizado" if desatualizado else "✅ Cache atualizado"
    texto = f"{marca}, última vez atualizado: {formatar_data(cache_updated_at, segundos=True)}"
    if global_updated_at:
        texto += f" (Memória geral: {formatar_data(global_updated_at, segundos=True)})"
    return texto
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest discover -s tests -t . -v`
Expected: PASS (6 testes).

- [ ] **Step 5: Commit**

```bash
git add tests/__init__.py tests/test_formatting_cache.py proporcao_pastas/domain/formatting.py
git commit -m "feat: formata data com segundos e texto de status do cache"
```

---

### Task 2: Campos de cache no domínio

**Files:**
- Create: `tests/test_models_cache.py`
- Modify: `proporcao_pastas/domain/models.py:6-26`

**Interfaces:**
- Consumes: nada.
- Produces: `FolderStats(..., cache_updated_at: Optional[float] = None, cache_desatualizado: bool = False)`; `ItemPasta(..., cache_updated_at: Optional[float] = None, cache_desatualizado: bool = False)`. Ambos continuam `frozen=True`: atualizar exige `dataclasses.replace`.

- [ ] **Step 1: Write the failing test**

```python
"""Testes dos campos de cache nos modelos."""
import dataclasses
import unittest

from proporcao_pastas.domain.models import FolderStats, ItemPasta


class TestCamposDeCache(unittest.TestCase):
    def test_folder_stats_tem_padroes(self):
        stats = FolderStats(tamanho=10)
        self.assertIsNone(stats.cache_updated_at)
        self.assertFalse(stats.cache_desatualizado)

    def test_item_pasta_tem_padroes(self):
        item = ItemPasta(nome="a", tamanho=1, eh_pasta=False)
        self.assertIsNone(item.cache_updated_at)
        self.assertFalse(item.cache_desatualizado)

    def test_replace_atualiza_sem_quebrar_frozen(self):
        stats = FolderStats(tamanho=10)
        novo = dataclasses.replace(stats, cache_updated_at=123.0, cache_desatualizado=True)
        self.assertEqual(novo.cache_updated_at, 123.0)
        self.assertTrue(novo.cache_desatualizado)
        self.assertIsNone(stats.cache_updated_at)

    def test_tupla_legada_continua_com_tres_itens(self):
        item = ItemPasta(nome="a", tamanho=1, eh_pasta=True, cache_updated_at=5.0)
        self.assertEqual(tuple(item), ("a", 1, True))
        self.assertEqual(item[1], 1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_models_cache -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'cache_updated_at'`.

- [ ] **Step 3: Write minimal implementation**

Em `models.py`, acrescentar os dois campos no fim de cada dataclass (depois dos campos com default, para não quebrar a ordem):

```python
@dataclass(frozen=True)
class FolderStats:
    tamanho: int = 0
    arquivos: int = 0
    subpastas: int = 0
    maior_arquivo_nome: str = ""
    maior_arquivo_tam: int = 0
    cache_updated_at: Optional[float] = None
    cache_desatualizado: bool = False
```

E em `ItemPasta`, após `maior_arquivo: str = "—"`:

```python
    cache_updated_at: Optional[float] = None
    cache_desatualizado: bool = False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest discover -s tests -t . -v`
Expected: PASS (10 testes).

- [ ] **Step 5: Commit**

```bash
git add tests/test_models_cache.py proporcao_pastas/domain/models.py
git commit -m "feat: adiciona campos de cache em FolderStats e ItemPasta"
```

---

### Task 3: Raízes do sistema e caminhos ignorados

**Files:**
- Create: `proporcao_pastas/infrastructure/system_roots.py`
- Create: `tests/test_system_roots.py`

**Interfaces:**
- Consumes: nada.
- Produces: `list_system_roots() -> List[str]`; `caminho_ignorado(path: str) -> bool`; constantes `IGNORADOS_MAC`, `IGNORADOS_WINDOWS`.

- [ ] **Step 1: Write the failing test**

```python
"""Testes da deteccao de raizes do sistema."""
import unittest
from unittest import mock

from proporcao_pastas.infrastructure import system_roots


class TestListSystemRoots(unittest.TestCase):
    def test_windows_lista_unidades_existentes(self):
        existentes = {"C:\\", "D:\\"}
        with mock.patch.object(system_roots, "IS_WINDOWS", True), \
             mock.patch.object(system_roots.os.path, "exists", lambda p: p in existentes):
            self.assertEqual(system_roots.list_system_roots(), ["C:\\", "D:\\"])

    def test_nao_windows_retorna_barra(self):
        with mock.patch.object(system_roots, "IS_WINDOWS", False):
            self.assertEqual(system_roots.list_system_roots(), ["/"])


class TestCaminhoIgnorado(unittest.TestCase):
    def test_ignora_firmlink_do_mac(self):
        with mock.patch.object(system_roots, "IS_WINDOWS", False), \
             mock.patch.object(system_roots, "IS_MAC", True):
            self.assertTrue(system_roots.caminho_ignorado("/System/Volumes/Data"))
            self.assertTrue(system_roots.caminho_ignorado("/dev"))
            self.assertFalse(system_roots.caminho_ignorado("/Users/maria"))

    def test_ignora_winsxs_e_system_volume_information(self):
        with mock.patch.object(system_roots, "IS_WINDOWS", True), \
             mock.patch.object(system_roots, "IS_MAC", False):
            self.assertTrue(system_roots.caminho_ignorado("C:\\Windows\\WinSxS"))
            self.assertTrue(system_roots.caminho_ignorado("D:\\System Volume Information"))
            self.assertFalse(system_roots.caminho_ignorado("C:\\Users\\cesoler"))

    def test_comparacao_ignora_caixa(self):
        with mock.patch.object(system_roots, "IS_WINDOWS", True), \
             mock.patch.object(system_roots, "IS_MAC", False):
            self.assertTrue(system_roots.caminho_ignorado("c:\\windows\\winsxs"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_system_roots -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'proporcao_pastas.infrastructure.system_roots'`.

- [ ] **Step 3: Write minimal implementation**

```python
"""Raizes de disco e caminhos que a varredura deve ignorar."""
import os
import platform
import string
import sys
from typing import List

IS_WINDOWS = platform.system() == "Windows" or os.name == "nt"
IS_MAC = platform.system() == "Darwin" or sys.platform == "darwin"

# Firmlinks do APFS espelham /Users e /Applications; contar duas vezes inflaria o total.
IGNORADOS_MAC = ("/System/Volumes/Data", "/dev", "/proc", "/net", "/Volumes/Recovery")
# WinSxS e cheio de hardlinks (conta duas vezes); as outras travam ou negam leitura.
IGNORADOS_WINDOWS = (
    "\\windows\\winsxs",
    "\\system volume information",
    "\\$recycle.bin",
    "\\pagefile.sys",
    "\\hiberfil.sys",
    "\\swapfile.sys",
)


def list_system_roots() -> List[str]:
    """Raizes para montar a arvore: unidades no Windows, '/' nos demais."""
    if not IS_WINDOWS:
        return ["/"]
    # os.listdrives() existe so no Python 3.12+; o projeto suporta 3.8.
    return [f"{letra}:\\" for letra in string.ascii_uppercase if os.path.exists(f"{letra}:\\")]


def caminho_ignorado(path: str) -> bool:
    """Diz se o caminho deve ficar fora da varredura."""
    if IS_WINDOWS:
        baixo = path.lower().rstrip("\\")
        return any(baixo.endswith(sufixo) for sufixo in IGNORADOS_WINDOWS)
    if IS_MAC:
        return path.rstrip("/") in [i.rstrip("/") for i in IGNORADOS_MAC]
    return path.rstrip("/") in ("/dev", "/proc", "/sys", "/run")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest discover -s tests -t . -v`
Expected: PASS (15 testes).

- [ ] **Step 5: Commit**

```bash
git add proporcao_pastas/infrastructure/system_roots.py tests/test_system_roots.py
git commit -m "feat: detecta raizes do sistema e caminhos ignorados na varredura"
```

---

### Task 4: Banco de cache — esquema, leitura e escrita

**Files:**
- Create: `proporcao_pastas/infrastructure/cache_storage.py`
- Create: `tests/test_cache_storage.py`

**Interfaces:**
- Consumes: nada.
- Produces:
  - `caminho_padrao_cache() -> str`
  - `@dataclass CachedFolder` com campos: `path, parent, tamanho, arquivos, subpastas, maior_nome, maior_tam, maior_direct_nome, maior_direct_tam, modificado_em, criado_em, permissoes, cache_updated_at, arquivos_truncados, soma_truncados`
  - `@dataclass CachedFile` com campos: `nome, tamanho, modificado_em, criado_em, permissoes`
  - `class SqliteCacheStorage`: `__init__(db_path: str)`, `close()`, `put_folder(folder: CachedFolder, arquivos: List[CachedFile]) -> None`, `get_folder(path: str) -> Optional[CachedFolder]`, `get_files(path: str) -> List[CachedFile]`, `get_subfolders(path: str) -> List[CachedFolder]`, `delete_subtree(path: str) -> None`, `set_meta(chave: str, valor: str) -> None`, `get_meta(chave: str) -> Optional[str]`, `ultima_atualizacao_global() -> Optional[float]`
  - Constante `MAX_ARQUIVOS_CACHE = 50`

- [ ] **Step 1: Write the failing test**

```python
"""Testes do armazenamento do cache em SQLite."""
import os
import tempfile
import unittest

from proporcao_pastas.infrastructure.cache_storage import (
    CachedFile,
    CachedFolder,
    SqliteCacheStorage,
)


def pasta(path, parent=None, tamanho=100, **extra):
    base = dict(
        path=path,
        parent=parent,
        tamanho=tamanho,
        arquivos=2,
        subpastas=0,
        maior_nome="a.bin",
        maior_tam=90,
        maior_direct_nome="a.bin",
        maior_direct_tam=90,
        modificado_em=1000.0,
        criado_em=900.0,
        permissoes="drwxr-xr-x",
        cache_updated_at=5000.0,
        arquivos_truncados=0,
        soma_truncados=0,
    )
    base.update(extra)
    return CachedFolder(**base)


class TestSqliteCacheStorage(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.storage = SqliteCacheStorage(os.path.join(self.dir.name, "cache.db"))

    def tearDown(self):
        self.storage.close()
        self.dir.cleanup()

    def test_ida_e_volta_de_pasta(self):
        self.storage.put_folder(pasta("/a"), [])
        lido = self.storage.get_folder("/a")
        self.assertEqual(lido.tamanho, 100)
        self.assertEqual(lido.maior_nome, "a.bin")
        self.assertEqual(lido.cache_updated_at, 5000.0)

    def test_pasta_inexistente_retorna_none(self):
        self.assertIsNone(self.storage.get_folder("/nao/existe"))

    def test_put_folder_substitui(self):
        self.storage.put_folder(pasta("/a"), [])
        self.storage.put_folder(pasta("/a", tamanho=777), [])
        self.assertEqual(self.storage.get_folder("/a").tamanho, 777)

    def test_arquivos_sao_gravados_e_substituidos(self):
        arquivos = [CachedFile("x.pdf", 10, 1.0, 2.0, "-rw-r--r--")]
        self.storage.put_folder(pasta("/a"), arquivos)
        self.assertEqual([f.nome for f in self.storage.get_files("/a")], ["x.pdf"])
        self.storage.put_folder(pasta("/a"), [CachedFile("y.pdf", 20, 1.0, 2.0, "-rw-r--r--")])
        self.assertEqual([f.nome for f in self.storage.get_files("/a")], ["y.pdf"])

    def test_get_subfolders_usa_parent(self):
        self.storage.put_folder(pasta("/a"), [])
        self.storage.put_folder(pasta("/a/b", parent="/a", tamanho=10), [])
        self.storage.put_folder(pasta("/a/c", parent="/a", tamanho=20), [])
        self.storage.put_folder(pasta("/outro", parent=None), [])
        nomes = sorted(s.path for s in self.storage.get_subfolders("/a"))
        self.assertEqual(nomes, ["/a/b", "/a/c"])

    def test_delete_subtree_remove_descendentes_e_arquivos(self):
        self.storage.put_folder(pasta("/a"), [CachedFile("raiz.txt", 1, 1.0, 1.0, "-rw-")])
        self.storage.put_folder(pasta("/a/b", parent="/a"), [CachedFile("f.txt", 1, 1.0, 1.0, "-rw-")])
        self.storage.put_folder(pasta("/a/b/c", parent="/a/b"), [])
        self.storage.put_folder(pasta("/z", parent=None), [])
        self.storage.delete_subtree("/a")
        self.assertIsNone(self.storage.get_folder("/a"))
        self.assertIsNone(self.storage.get_folder("/a/b"))
        self.assertIsNone(self.storage.get_folder("/a/b/c"))
        self.assertEqual(self.storage.get_files("/a/b"), [])
        self.assertIsNotNone(self.storage.get_folder("/z"))

    def test_nome_com_curinga_de_like_nao_afeta_vizinhos(self):
        self.storage.put_folder(pasta("/a%b", parent=None), [])
        self.storage.put_folder(pasta("/a_c", parent=None), [])
        self.storage.delete_subtree("/a%b")
        self.assertIsNone(self.storage.get_folder("/a%b"))
        self.assertIsNotNone(self.storage.get_folder("/a_c"))

    def test_meta_ida_e_volta(self):
        self.assertIsNone(self.storage.get_meta("roots"))
        self.storage.set_meta("roots", "C:\\")
        self.assertEqual(self.storage.get_meta("roots"), "C:\\")
        self.storage.set_meta("roots", "D:\\")
        self.assertEqual(self.storage.get_meta("roots"), "D:\\")

    def test_ultima_atualizacao_global_e_o_maior_cache_updated_at(self):
        self.assertIsNone(self.storage.ultima_atualizacao_global())
        self.storage.put_folder(pasta("/a", cache_updated_at=10.0), [])
        self.storage.put_folder(pasta("/b", cache_updated_at=99.0), [])
        self.assertEqual(self.storage.ultima_atualizacao_global(), 99.0)

    def test_reabrir_banco_preserva_dados(self):
        self.storage.put_folder(pasta("/a"), [])
        caminho = self.storage.db_path
        self.storage.close()
        self.storage = SqliteCacheStorage(caminho)
        self.assertEqual(self.storage.get_folder("/a").tamanho, 100)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_cache_storage -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'proporcao_pastas.infrastructure.cache_storage'`.

- [ ] **Step 3: Write minimal implementation**

```python
"""Cache persistente das estatisticas de pastas, em SQLite."""
import os
import platform
import sqlite3
import sys
import threading
from dataclasses import dataclass
from typing import List, Optional

MAX_ARQUIVOS_CACHE = 50
VERSAO_ESQUEMA = "1"

IS_WINDOWS = platform.system() == "Windows" or os.name == "nt"
IS_MAC = platform.system() == "Darwin" or sys.platform == "darwin"

ESQUEMA = """
CREATE TABLE IF NOT EXISTS folders (
    path TEXT PRIMARY KEY,
    parent TEXT,
    tamanho INTEGER NOT NULL,
    arquivos INTEGER NOT NULL,
    subpastas INTEGER NOT NULL,
    maior_nome TEXT NOT NULL DEFAULT '',
    maior_tam INTEGER NOT NULL DEFAULT 0,
    maior_direct_nome TEXT NOT NULL DEFAULT '',
    maior_direct_tam INTEGER NOT NULL DEFAULT 0,
    modificado_em REAL,
    criado_em REAL,
    permissoes TEXT NOT NULL DEFAULT '-',
    cache_updated_at REAL NOT NULL,
    arquivos_truncados INTEGER NOT NULL DEFAULT 0,
    soma_truncados INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_folders_parent ON folders(parent);
CREATE TABLE IF NOT EXISTS files (
    parent TEXT NOT NULL,
    nome TEXT NOT NULL,
    tamanho INTEGER NOT NULL,
    modificado_em REAL,
    criado_em REAL,
    permissoes TEXT,
    PRIMARY KEY (parent, nome)
);
CREATE TABLE IF NOT EXISTS meta (
    chave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);
"""

CAMPOS_FOLDER = (
    "path, parent, tamanho, arquivos, subpastas, maior_nome, maior_tam, "
    "maior_direct_nome, maior_direct_tam, modificado_em, criado_em, permissoes, "
    "cache_updated_at, arquivos_truncados, soma_truncados"
)


@dataclass
class CachedFolder:
    path: str
    parent: Optional[str]
    tamanho: int
    arquivos: int
    subpastas: int
    maior_nome: str
    maior_tam: int
    maior_direct_nome: str
    maior_direct_tam: int
    modificado_em: Optional[float]
    criado_em: Optional[float]
    permissoes: str
    cache_updated_at: float
    arquivos_truncados: int = 0
    soma_truncados: int = 0


@dataclass
class CachedFile:
    nome: str
    tamanho: int
    modificado_em: Optional[float]
    criado_em: Optional[float]
    permissoes: Optional[str]


def caminho_padrao_cache() -> str:
    """Caminho do banco de cache conforme o SO."""
    if IS_WINDOWS:
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        pasta = os.path.join(base, "ProporcaoPastas")
    elif IS_MAC:
        pasta = os.path.expanduser("~/Library/Caches/ProporcaoPastas")
    else:
        pasta = os.path.join(
            os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"),
            "proporcao-pastas",
        )
    return os.path.join(pasta, "cache.db")


class SqliteCacheStorage:
    """Le e grava o cache de pastas. Seguro para uso de varias threads."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        pasta = os.path.dirname(db_path)
        if pasta:
            os.makedirs(pasta, exist_ok=True)
        self._lock = threading.RLock()
        self._con = sqlite3.connect(db_path, check_same_thread=False)
        self._con.row_factory = sqlite3.Row
        with self._lock:
            self._con.execute("PRAGMA journal_mode=WAL")
            self._con.execute("PRAGMA synchronous=NORMAL")
            self._con.executescript(ESQUEMA)
            self._con.execute(
                "INSERT OR IGNORE INTO meta (chave, valor) VALUES ('versao', ?)",
                (VERSAO_ESQUEMA,),
            )
            self._con.commit()

    def close(self) -> None:
        with self._lock:
            self._con.close()

    # ---------- escrita ----------
    def put_folder(self, folder: CachedFolder, arquivos: List[CachedFile]) -> None:
        with self._lock:
            self._con.execute(
                "INSERT OR REPLACE INTO folders ({}) VALUES ({})".format(
                    CAMPOS_FOLDER, ", ".join("?" * 15)
                ),
                (
                    folder.path, folder.parent, folder.tamanho, folder.arquivos,
                    folder.subpastas, folder.maior_nome, folder.maior_tam,
                    folder.maior_direct_nome, folder.maior_direct_tam,
                    folder.modificado_em, folder.criado_em, folder.permissoes,
                    folder.cache_updated_at, folder.arquivos_truncados,
                    folder.soma_truncados,
                ),
            )
            self._con.execute("DELETE FROM files WHERE parent = ?", (folder.path,))
            self._con.executemany(
                "INSERT OR REPLACE INTO files "
                "(parent, nome, tamanho, modificado_em, criado_em, permissoes) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (folder.path, a.nome, a.tamanho, a.modificado_em, a.criado_em, a.permissoes)
                    for a in arquivos
                ],
            )
            self._con.commit()

    def delete_subtree(self, path: str) -> None:
        """Remove a pasta e todos os descendentes, descendo pela coluna parent.

        Nao usa LIKE de proposito: nome de pasta com % ou _ seria curinga."""
        with self._lock:
            alvos = [path]
            fila = [path]
            while fila:
                atual = fila.pop()
                filhos = [
                    linha["path"] for linha in self._con.execute(
                        "SELECT path FROM folders WHERE parent = ?", (atual,)
                    )
                ]
                alvos.extend(filhos)
                fila.extend(filhos)
            for inicio in range(0, len(alvos), 500):
                lote = alvos[inicio:inicio + 500]
                marcas = ", ".join("?" * len(lote))
                self._con.execute(
                    "DELETE FROM folders WHERE path IN ({})".format(marcas), lote
                )
                self._con.execute(
                    "DELETE FROM files WHERE parent IN ({})".format(marcas), lote
                )
            self._con.commit()

    def set_meta(self, chave: str, valor: str) -> None:
        with self._lock:
            self._con.execute(
                "INSERT OR REPLACE INTO meta (chave, valor) VALUES (?, ?)", (chave, valor)
            )
            self._con.commit()

    # ---------- leitura ----------
    def get_folder(self, path: str) -> Optional[CachedFolder]:
        with self._lock:
            linha = self._con.execute(
                "SELECT {} FROM folders WHERE path = ?".format(CAMPOS_FOLDER), (path,)
            ).fetchone()
        return CachedFolder(**dict(linha)) if linha else None

    def get_files(self, path: str) -> List[CachedFile]:
        with self._lock:
            linhas = self._con.execute(
                "SELECT nome, tamanho, modificado_em, criado_em, permissoes "
                "FROM files WHERE parent = ?",
                (path,),
            ).fetchall()
        return [CachedFile(**dict(linha)) for linha in linhas]

    def get_subfolders(self, path: str) -> List[CachedFolder]:
        with self._lock:
            linhas = self._con.execute(
                "SELECT {} FROM folders WHERE parent = ?".format(CAMPOS_FOLDER), (path,)
            ).fetchall()
        return [CachedFolder(**dict(linha)) for linha in linhas]

    def get_meta(self, chave: str) -> Optional[str]:
        with self._lock:
            linha = self._con.execute(
                "SELECT valor FROM meta WHERE chave = ?", (chave,)
            ).fetchone()
        return linha["valor"] if linha else None

    def ultima_atualizacao_global(self) -> Optional[float]:
        with self._lock:
            linha = self._con.execute("SELECT MAX(cache_updated_at) AS m FROM folders").fetchone()
        return linha["m"] if linha and linha["m"] is not None else None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest discover -s tests -t . -v`
Expected: PASS (25 testes).

- [ ] **Step 5: Commit**

```bash
git add proporcao_pastas/infrastructure/cache_storage.py tests/test_cache_storage.py
git commit -m "feat: cria cache persistente de pastas em SQLite"
```

---

### Task 5: Propagação de delta e recálculo do maior arquivo

**Files:**
- Modify: `proporcao_pastas/infrastructure/cache_storage.py` (acrescentar métodos à classe)
- Create: `tests/test_cache_delta.py`

**Interfaces:**
- Consumes: `SqliteCacheStorage`, `CachedFolder` da Task 4.
- Produces: `SqliteCacheStorage.ancestrais(path: str) -> List[str]`; `SqliteCacheStorage.aplicar_delta(path: str, d_tamanho: int, d_arquivos: int, d_subpastas: int) -> List[str]` (retorna os ancestrais alterados, do mais próximo ao mais distante); `SqliteCacheStorage.recalcular_maior(path: str) -> None`.

**Regra:** `arquivos` e `subpastas` são contagens recursivas, então somar diferenças nos ancestrais é correto. `maior_nome`/`maior_tam` é um máximo recursivo: não se reconstrói por soma, então cada ancestral recalcula `max(maior_direct do próprio, maior_tam de cada subpasta direta em cache)`. `cache_updated_at` do ancestral **não** é tocado: ele não foi revarrido, só corrigido.

- [ ] **Step 1: Write the failing test**

```python
"""Testes da propagacao de delta e do recalculo do maior arquivo."""
import os
import tempfile
import unittest

from proporcao_pastas.infrastructure.cache_storage import (
    CachedFile,
    CachedFolder,
    SqliteCacheStorage,
)


def pasta(path, parent, tamanho, arquivos=1, subpastas=0,
          maior=("", 0), maior_direto=("", 0), quando=100.0):
    return CachedFolder(
        path=path, parent=parent, tamanho=tamanho, arquivos=arquivos, subpastas=subpastas,
        maior_nome=maior[0], maior_tam=maior[1],
        maior_direct_nome=maior_direto[0], maior_direct_tam=maior_direto[1],
        modificado_em=1.0, criado_em=1.0, permissoes="drwxr-xr-x",
        cache_updated_at=quando, arquivos_truncados=0, soma_truncados=0,
    )


class TestDelta(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.storage = SqliteCacheStorage(os.path.join(self.dir.name, "cache.db"))
        # /raiz (300) -> /raiz/docs (200) -> /raiz/docs/fac (50)
        self.storage.put_folder(pasta("/raiz", None, 300, arquivos=6, subpastas=2,
                                      maior=("filme.mp4", 180), maior_direto=("leia.txt", 10)), [])
        self.storage.put_folder(pasta("/raiz/docs", "/raiz", 200, arquivos=4, subpastas=1,
                                      maior=("filme.mp4", 180), maior_direto=("nota.pdf", 20)), [])
        self.storage.put_folder(pasta("/raiz/docs/fac", "/raiz/docs", 50, arquivos=2,
                                      maior=("filme.mp4", 180), maior_direto=("filme.mp4", 180)), [])

    def tearDown(self):
        self.storage.close()
        self.dir.cleanup()

    def test_ancestrais_do_mais_proximo_ao_mais_distante(self):
        self.assertEqual(
            self.storage.ancestrais("/raiz/docs/fac"), ["/raiz/docs", "/raiz"]
        )

    def test_ancestrais_para_quem_nao_tem_pai_em_cache(self):
        self.assertEqual(self.storage.ancestrais("/raiz"), [])

    def test_aplicar_delta_soma_nos_ancestrais(self):
        alterados = self.storage.aplicar_delta("/raiz/docs/fac", 25, 2, 1)
        self.assertEqual(alterados, ["/raiz/docs", "/raiz"])
        self.assertEqual(self.storage.get_folder("/raiz/docs").tamanho, 225)
        self.assertEqual(self.storage.get_folder("/raiz").tamanho, 325)
        self.assertEqual(self.storage.get_folder("/raiz/docs").arquivos, 6)
        self.assertEqual(self.storage.get_folder("/raiz").subpastas, 3)

    def test_aplicar_delta_nao_mexe_no_cache_updated_at_do_ancestral(self):
        self.storage.aplicar_delta("/raiz/docs/fac", 25, 0, 0)
        self.assertEqual(self.storage.get_folder("/raiz").cache_updated_at, 100.0)

    def test_aplicar_delta_nao_deixa_valor_negativo(self):
        self.storage.aplicar_delta("/raiz/docs/fac", -10_000, -100, -100)
        pai = self.storage.get_folder("/raiz/docs")
        self.assertEqual((pai.tamanho, pai.arquivos, pai.subpastas), (0, 0, 0))

    def test_recalcular_maior_quando_o_maior_desaparece(self):
        # o maior arquivo (filme.mp4, 180) sai de /raiz/docs/fac
        self.storage.put_folder(
            pasta("/raiz/docs/fac", "/raiz/docs", 5, maior=("resto.txt", 5),
                  maior_direto=("resto.txt", 5), quando=500.0),
            [],
        )
        self.storage.recalcular_maior("/raiz/docs")
        docs = self.storage.get_folder("/raiz/docs")
        self.assertEqual((docs.maior_nome, docs.maior_tam), ("nota.pdf", 20))
        self.storage.recalcular_maior("/raiz")
        raiz = self.storage.get_folder("/raiz")
        self.assertEqual((raiz.maior_nome, raiz.maior_tam), ("nota.pdf", 20))

    def test_recalcular_maior_prefere_subpasta_quando_ela_e_maior(self):
        self.storage.recalcular_maior("/raiz/docs")
        docs = self.storage.get_folder("/raiz/docs")
        self.assertEqual((docs.maior_nome, docs.maior_tam), ("filme.mp4", 180))

    def test_recalcular_maior_em_pasta_fora_do_cache_nao_quebra(self):
        self.storage.recalcular_maior("/nao/existe")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_cache_delta -v`
Expected: FAIL — `AttributeError: 'SqliteCacheStorage' object has no attribute 'ancestrais'`.

- [ ] **Step 3: Write minimal implementation**

Acrescentar em `SqliteCacheStorage` (em `cache_storage.py`), depois de `get_subfolders`:

```python
    # ---------- atualizacao parcial ----------
    def ancestrais(self, path: str) -> List[str]:
        """Ancestrais em cache, do pai ate a raiz."""
        caminhos = []
        with self._lock:
            atual = path
            while True:
                linha = self._con.execute(
                    "SELECT parent FROM folders WHERE path = ?", (atual,)
                ).fetchone()
                pai = linha["parent"] if linha else None
                if not pai:
                    break
                caminhos.append(pai)
                atual = pai
        return caminhos

    def aplicar_delta(
        self,
        path: str,
        d_tamanho: int,
        d_arquivos: int,
        d_subpastas: int,
    ) -> List[str]:
        """Soma as diferencas nos ancestrais e recalcula o maior arquivo deles.

        cache_updated_at do ancestral nao muda: ele foi corrigido, nao revarrido."""
        alterados = self.ancestrais(path)
        with self._lock:
            for ancestral in alterados:
                self._con.execute(
                    "UPDATE folders SET "
                    "tamanho = MAX(0, tamanho + ?), "
                    "arquivos = MAX(0, arquivos + ?), "
                    "subpastas = MAX(0, subpastas + ?) "
                    "WHERE path = ?",
                    (d_tamanho, d_arquivos, d_subpastas, ancestral),
                )
            self._con.commit()
        for ancestral in alterados:
            self.recalcular_maior(ancestral)
        return alterados

    def recalcular_maior(self, path: str) -> None:
        """Maior arquivo de uma pasta = maior entre os arquivos diretos dela
        e o maior de cada subpasta direta que esta em cache."""
        atual = self.get_folder(path)
        if atual is None:
            return
        melhor_nome, melhor_tam = atual.maior_direct_nome, atual.maior_direct_tam
        for sub in self.get_subfolders(path):
            if sub.maior_tam > melhor_tam:
                melhor_nome, melhor_tam = sub.maior_nome, sub.maior_tam
        with self._lock:
            self._con.execute(
                "UPDATE folders SET maior_nome = ?, maior_tam = ? WHERE path = ?",
                (melhor_nome, melhor_tam, path),
            )
            self._con.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest discover -s tests -t . -v`
Expected: PASS (33 testes).

- [ ] **Step 5: Commit**

```bash
git add proporcao_pastas/infrastructure/cache_storage.py tests/test_cache_delta.py
git commit -m "feat: propaga delta e recalcula maior arquivo nos ancestrais"
```

---

### Task 6: Scanner lendo e gravando no cache persistente

**Files:**
- Modify: `proporcao_pastas/infrastructure/file_system.py:10-158`
- Create: `tests/test_scanner_cache.py`

**Interfaces:**
- Consumes: `SqliteCacheStorage`, `CachedFolder`, `CachedFile`, `MAX_ARQUIVOS_CACHE` (Task 4-5); `caminho_ignorado` (Task 3); campos de cache dos modelos (Task 2).
- Produces:
  - `IDADE_MAXIMA_CACHE_SEG = 7 * 24 * 3600`
  - `FileSystemScanner(storage: Optional[SqliteCacheStorage] = None, idade_maxima: float = IDADE_MAXIMA_CACHE_SEG)`
  - `FileSystemScanner.stats(path, usar_cache=True) -> FolderStats` (agora com `cache_updated_at` e `cache_desatualizado` preenchidos)
  - `FileSystemScanner.children(path, keep=(), max_items=8) -> List[ItemPasta]` (lê do cache quando disponível)
  - `FileSystemScanner.is_folder_outdated(path) -> bool`
  - `FileSystemScanner.refresh_folder(path, progresso=None) -> FolderStats`
  - `FileSystemScanner.ultima_atualizacao_global() -> Optional[float]`

**Nota de implementação:** `stats()` é recursivo e roda na thread de trabalho; o `RLock` do storage protege o banco, e `self._lock` protege os dicionários em memória.

- [ ] **Step 1: Write the failing test**

```python
"""Testes da integracao entre o scanner e o cache persistente."""
import os
import tempfile
import time
import unittest

from proporcao_pastas.infrastructure.cache_storage import SqliteCacheStorage
from proporcao_pastas.infrastructure.file_system import FileSystemScanner


def escrever(caminho, conteudo):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "wb") as f:
        f.write(conteudo)


class TestScannerComCache(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.raiz = os.path.join(self.dir.name, "raiz")
        escrever(os.path.join(self.raiz, "a.bin"), b"x" * 100)
        escrever(os.path.join(self.raiz, "sub", "b.bin"), b"y" * 50)
        self.storage = SqliteCacheStorage(os.path.join(self.dir.name, "cache.db"))
        self.scanner = FileSystemScanner(storage=self.storage)

    def tearDown(self):
        self.storage.close()
        self.dir.cleanup()

    def test_stats_grava_no_banco(self):
        stats = self.scanner.stats(self.raiz)
        self.assertEqual(stats.tamanho, 150)
        gravado = self.storage.get_folder(self.raiz)
        self.assertIsNotNone(gravado)
        self.assertEqual(gravado.tamanho, 150)
        self.assertEqual(gravado.maior_nome, "a.bin")
        self.assertEqual(gravado.maior_direct_nome, "a.bin")

    def test_stats_grava_subpastas_com_parent(self):
        self.scanner.stats(self.raiz)
        sub = self.storage.get_folder(os.path.join(self.raiz, "sub"))
        self.assertEqual(sub.parent, self.raiz)
        self.assertEqual(sub.tamanho, 50)

    def test_segundo_scanner_le_do_banco_sem_tocar_o_disco(self):
        self.scanner.stats(self.raiz)
        outro = FileSystemScanner(storage=self.storage)
        # apaga o conteudo: se ler o disco, o tamanho cai
        os.remove(os.path.join(self.raiz, "a.bin"))
        self.assertEqual(outro.stats(self.raiz).tamanho, 150)
        self.assertIsNotNone(outro.stats(self.raiz).cache_updated_at)

    def test_children_vem_do_cache_e_mantem_metadados(self):
        self.scanner.stats(self.raiz)
        outro = FileSystemScanner(storage=self.storage)
        nomes = {i.nome: i for i in outro.children(self.raiz)}
        self.assertEqual(set(nomes), {"a.bin", "sub"})
        self.assertEqual(nomes["sub"].tamanho, 50)
        self.assertTrue(nomes["sub"].eh_pasta)
        self.assertEqual(nomes["a.bin"].tipo_detalhado, "Arq (.bin)")
        self.assertIsNotNone(nomes["sub"].cache_updated_at)

    def test_children_agrupa_arquivos_truncados_em_outros(self):
        for i in range(60):
            escrever(os.path.join(self.raiz, "muitos", "f%02d.bin" % i), b"z" * (i + 1))
        self.scanner.stats(os.path.join(self.raiz, "muitos"))
        outro = FileSystemScanner(storage=self.storage)
        itens = outro.children(os.path.join(self.raiz, "muitos"), max_items=8)
        self.assertEqual(len(itens), 8)
        outros = itens[-1]
        self.assertIsNone(outros.eh_pasta)
        total_disco = sum(range(1, 61))
        self.assertEqual(sum(i.tamanho for i in itens), total_disco)

    def test_sem_storage_funciona_como_antes(self):
        simples = FileSystemScanner()
        self.assertEqual(simples.stats(self.raiz).tamanho, 150)
        self.assertEqual(len(simples.children(self.raiz)), 2)

    def test_is_folder_outdated_quando_a_pasta_muda(self):
        self.scanner.stats(self.raiz)
        self.assertFalse(self.scanner.is_folder_outdated(self.raiz))
        time.sleep(0.01)
        escrever(os.path.join(self.raiz, "novo.bin"), b"n")
        os.utime(self.raiz, (time.time() + 10, time.time() + 10))
        self.assertTrue(self.scanner.is_folder_outdated(self.raiz))

    def test_is_folder_outdated_quando_subpasta_muda(self):
        self.scanner.stats(self.raiz)
        futuro = time.time() + 10
        os.utime(os.path.join(self.raiz, "sub"), (futuro, futuro))
        self.assertTrue(self.scanner.is_folder_outdated(self.raiz))

    def test_is_folder_outdated_por_idade(self):
        self.scanner.stats(self.raiz)
        velho = FileSystemScanner(storage=self.storage, idade_maxima=-1)
        self.assertTrue(velho.is_folder_outdated(self.raiz))

    def test_is_folder_outdated_para_pasta_fora_do_cache(self):
        self.assertTrue(self.scanner.is_folder_outdated(os.path.join(self.raiz, "sub")))

    def test_refresh_folder_atualiza_a_pasta_e_os_ancestrais(self):
        self.scanner.stats(self.raiz)
        sub = os.path.join(self.raiz, "sub")
        escrever(os.path.join(sub, "c.bin"), b"w" * 25)
        novo = self.scanner.refresh_folder(sub)
        self.assertEqual(novo.tamanho, 75)
        self.assertEqual(self.storage.get_folder(sub).tamanho, 75)
        self.assertEqual(self.storage.get_folder(self.raiz).tamanho, 175)
        self.assertEqual(self.storage.get_folder(self.raiz).arquivos, 3)

    def test_refresh_folder_corrige_maior_arquivo_do_ancestral(self):
        escrever(os.path.join(self.raiz, "sub", "enorme.bin"), b"g" * 5000)
        self.scanner.stats(self.raiz)
        self.assertEqual(self.storage.get_folder(self.raiz).maior_nome, "enorme.bin")
        os.remove(os.path.join(self.raiz, "sub", "enorme.bin"))
        self.scanner.refresh_folder(os.path.join(self.raiz, "sub"))
        self.assertEqual(self.storage.get_folder(self.raiz).maior_nome, "a.bin")

    def test_refresh_folder_chama_o_progresso(self):
        self.scanner.stats(self.raiz)
        vistos = []
        self.scanner.refresh_folder(self.raiz, progresso=vistos.append)
        self.assertTrue(vistos)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_scanner_cache -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'storage'`.

- [ ] **Step 3: Write minimal implementation**

Reescrever `file_system.py` mantendo a API atual (`size`, `children`, `subfolders`, `clear_cache`, `parent_analysis_path`):

```python
"""Leitura do sistema de arquivos usada pela aplicacao."""
import os
import stat
import threading
import time
from typing import Dict, Iterable, List, Optional, Tuple

from proporcao_pastas.domain.formatting import formatar_tamanho, formatar_tipo_item
from proporcao_pastas.domain.models import FolderStats, ItemPasta
from proporcao_pastas.infrastructure.cache_storage import (
    MAX_ARQUIVOS_CACHE,
    CachedFile,
    CachedFolder,
)
from proporcao_pastas.infrastructure.system_roots import caminho_ignorado

IDADE_MAXIMA_CACHE_SEG = 7 * 24 * 3600


def _maior_str(nome: str, tamanho: int) -> str:
    return f"{nome} ({formatar_tamanho(tamanho)})" if nome else "—"


class FileSystemScanner:
    """Calcula tamanhos e metadados, com cache em memoria e, opcionalmente,
    cache persistente em disco."""

    def __init__(self, storage=None, idade_maxima: float = IDADE_MAXIMA_CACHE_SEG) -> None:
        self._stats_cache: Dict[str, FolderStats] = {}
        self._storage = storage
        self._idade_maxima = idade_maxima
        self._lock = threading.RLock()

    def clear_cache(self) -> None:
        with self._lock:
            self._stats_cache.clear()

    def ultima_atualizacao_global(self) -> Optional[float]:
        return self._storage.ultima_atualizacao_global() if self._storage else None

    # ---------- estatisticas ----------
    def stats(self, path: str, usar_cache: bool = True) -> FolderStats:
        if usar_cache:
            with self._lock:
                if path in self._stats_cache:
                    return self._stats_cache[path]
            if self._storage is not None:
                linha = self._storage.get_folder(path)
                if linha is not None:
                    resultado = FolderStats(
                        tamanho=linha.tamanho,
                        arquivos=linha.arquivos,
                        subpastas=linha.subpastas,
                        maior_arquivo_nome=linha.maior_nome,
                        maior_arquivo_tam=linha.maior_tam,
                        cache_updated_at=linha.cache_updated_at,
                    )
                    with self._lock:
                        self._stats_cache[path] = resultado
                    return resultado
        return self._varrer(path, usar_cache)

    def _varrer(self, path: str, usar_cache: bool) -> FolderStats:
        total = arquivos = subpastas = 0
        maior_nome, maior_tam = "", 0
        maior_direto_nome, maior_direto_tam = "", 0
        diretos: List[CachedFile] = []

        try:
            with os.scandir(path) as entries:
                for entry in entries:
                    try:
                        if entry.is_symlink() or caminho_ignorado(entry.path):
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            sub = self.stats(entry.path, usar_cache)
                            total += sub.tamanho
                            arquivos += sub.arquivos
                            subpastas += 1 + sub.subpastas
                            if sub.maior_arquivo_tam > maior_tam:
                                maior_tam = sub.maior_arquivo_tam
                                maior_nome = sub.maior_arquivo_nome
                        else:
                            st = entry.stat(follow_symlinks=False)
                            total += st.st_size
                            arquivos += 1
                            if st.st_size > maior_tam:
                                maior_tam, maior_nome = st.st_size, entry.name
                            if st.st_size > maior_direto_tam:
                                maior_direto_tam, maior_direto_nome = st.st_size, entry.name
                            diretos.append(CachedFile(
                                nome=entry.name,
                                tamanho=st.st_size,
                                modificado_em=st.st_mtime,
                                criado_em=getattr(st, "st_birthtime", st.st_ctime),
                                permissoes=stat.filemode(st.st_mode),
                            ))
                    except OSError:
                        continue
        except OSError:
            pass

        agora = time.time()
        resultado = FolderStats(
            tamanho=total,
            arquivos=arquivos,
            subpastas=subpastas,
            maior_arquivo_nome=maior_nome,
            maior_arquivo_tam=maior_tam,
            cache_updated_at=agora,
        )
        with self._lock:
            self._stats_cache[path] = resultado
        if self._storage is not None:
            self._gravar(path, resultado, diretos, maior_direto_nome, maior_direto_tam, agora)
        return resultado

    def _gravar(self, path, resultado, diretos, maior_direto_nome, maior_direto_tam, agora):
        diretos.sort(key=lambda a: -a.tamanho)
        guardados = diretos[:MAX_ARQUIVOS_CACHE]
        resto = diretos[MAX_ARQUIVOS_CACHE:]
        try:
            st = os.stat(path)
            mtime: Optional[float] = st.st_mtime
            ctime: Optional[float] = getattr(st, "st_birthtime", st.st_ctime)
            perm = stat.filemode(st.st_mode)
        except OSError:
            mtime, ctime, perm = None, None, "—"
        pai = os.path.dirname(path)
        self._storage.put_folder(
            CachedFolder(
                path=path,
                parent=pai if pai and pai != path else None,
                tamanho=resultado.tamanho,
                arquivos=resultado.arquivos,
                subpastas=resultado.subpastas,
                maior_nome=resultado.maior_arquivo_nome,
                maior_tam=resultado.maior_arquivo_tam,
                maior_direct_nome=maior_direto_nome,
                maior_direct_tam=maior_direto_tam,
                modificado_em=mtime,
                criado_em=ctime,
                permissoes=perm,
                cache_updated_at=agora,
                arquivos_truncados=len(resto),
                soma_truncados=sum(a.tamanho for a in resto),
            ),
            guardados,
        )

    def size(self, path: str) -> int:
        return self.stats(path).tamanho

    # ---------- validade do cache ----------
    def is_folder_outdated(self, path: str) -> bool:
        """Compara o mtime real da pasta e das subpastas em cache com o que foi
        gravado. Mudanca mais profunda que isso nao e detectada (ver README)."""
        if self._storage is None:
            return False
        linha = self._storage.get_folder(path)
        if linha is None:
            return True
        if time.time() - linha.cache_updated_at > self._idade_maxima:
            return True
        try:
            if linha.modificado_em is None or os.stat(path).st_mtime > linha.modificado_em:
                return True
        except OSError:
            return True
        for sub in self._storage.get_subfolders(path):
            try:
                if sub.modificado_em is None or os.stat(sub.path).st_mtime > sub.modificado_em:
                    return True
            except OSError:
                return True
        return False

    def refresh_folder(self, path: str, progresso=None) -> FolderStats:
        """Revarre so esta subarvore e corrige os ancestrais pela diferenca."""
        if progresso:
            progresso(path)
        if self._storage is None:
            self.clear_cache()
            return self.stats(path)

        antigo = self._storage.get_folder(path)
        self._storage.delete_subtree(path)
        with self._lock:
            prefixo = path.rstrip(os.sep) + os.sep
            for chave in [k for k in self._stats_cache if k == path or k.startswith(prefixo)]:
                del self._stats_cache[chave]
        novo = self.stats(path, usar_cache=False)
        if progresso:
            progresso(path)
        if antigo is not None:
            self._storage.aplicar_delta(
                path,
                novo.tamanho - antigo.tamanho,
                novo.arquivos - antigo.arquivos,
                novo.subpastas - antigo.subpastas,
            )
        return novo

    # ---------- conteudo ----------
    def children(self, path: str, keep: Iterable[str] = (), max_items: int = 8) -> List[ItemPasta]:
        self.stats(path)  # garante que a pasta esta medida e em cache
        if self._storage is not None and self._storage.get_folder(path) is not None:
            itens, extra_n, extra_soma = self._children_do_cache(path)
        else:
            itens, extra_n, extra_soma = self._children_do_disco(path), 0, 0
        return self._agrupar(itens, keep, max_items, extra_n, extra_soma)

    def _children_do_cache(self, path: str) -> Tuple[List[ItemPasta], int, int]:
        linha = self._storage.get_folder(path)
        itens: List[ItemPasta] = []
        for sub in self._storage.get_subfolders(path):
            itens.append(ItemPasta(
                nome=os.path.basename(sub.path) or sub.path,
                tamanho=sub.tamanho,
                eh_pasta=True,
                arquivos=sub.arquivos,
                subpastas=sub.subpastas,
                modificado_em=sub.modificado_em,
                criado_em=sub.criado_em,
                permissoes=sub.permissoes,
                tipo_detalhado="Pasta",
                maior_arquivo=_maior_str(sub.maior_nome, sub.maior_tam),
                cache_updated_at=sub.cache_updated_at,
            ))
        for arq in self._storage.get_files(path):
            itens.append(ItemPasta(
                nome=arq.nome,
                tamanho=arq.tamanho,
                eh_pasta=False,
                arquivos=1,
                subpastas=0,
                modificado_em=arq.modificado_em,
                criado_em=arq.criado_em,
                permissoes=arq.permissoes or "—",
                tipo_detalhado=formatar_tipo_item(arq.nome, False),
                maior_arquivo="—",
                cache_updated_at=linha.cache_updated_at,
            ))
        return itens, linha.arquivos_truncados, linha.soma_truncados

    def _children_do_disco(self, path: str) -> List[ItemPasta]:
        itens: List[ItemPasta] = []
        try:
            with os.scandir(path) as entries:
                for entry in entries:
                    try:
                        if entry.is_symlink() or caminho_ignorado(entry.path):
                            continue
                        st = entry.stat(follow_symlinks=False)
                        mtime = st.st_mtime
                        ctime = getattr(st, "st_birthtime", st.st_ctime)
                        perm = stat.filemode(st.st_mode)
                        if entry.is_dir(follow_symlinks=False):
                            sub = self.stats(entry.path)
                            itens.append(ItemPasta(
                                nome=entry.name, tamanho=sub.tamanho, eh_pasta=True,
                                arquivos=sub.arquivos, subpastas=sub.subpastas,
                                modificado_em=mtime, criado_em=ctime, permissoes=perm,
                                tipo_detalhado="Pasta",
                                maior_arquivo=_maior_str(sub.maior_arquivo_nome,
                                                         sub.maior_arquivo_tam),
                                cache_updated_at=sub.cache_updated_at,
                            ))
                        else:
                            itens.append(ItemPasta(
                                nome=entry.name, tamanho=st.st_size, eh_pasta=False,
                                arquivos=1, subpastas=0,
                                modificado_em=mtime, criado_em=ctime, permissoes=perm,
                                tipo_detalhado=formatar_tipo_item(entry.name, False),
                                maior_arquivo="—",
                            ))
                    except OSError:
                        continue
        except OSError:
            pass
        return itens

    @staticmethod
    def _agrupar(itens, keep, max_items, extra_n=0, extra_soma=0) -> List[ItemPasta]:
        keep = set(keep)
        itens = [item for item in itens if item.tamanho > 0]
        itens.sort(key=lambda item: -item.tamanho)
        if len(itens) <= max_items and not extra_n:
            return itens
        fixos, resto = [], []
        for indice, item in enumerate(itens):
            (fixos if indice < max_items - 1 or item.nome in keep else resto).append(item)
        total_resto = len(resto) + extra_n
        if total_resto:
            mtimes = [i.modificado_em for i in resto if i.modificado_em is not None]
            maior_resto = (
                f"{resto[0].nome} ({formatar_tamanho(resto[0].tamanho)})" if resto else "—"
            )
            fixos.append(ItemPasta(
                nome=f"Outros ({total_resto} itens)",
                tamanho=sum(i.tamanho for i in resto) + extra_soma,
                eh_pasta=None,
                arquivos=sum(i.arquivos for i in resto) + extra_n,
                subpastas=sum(i.subpastas + (1 if i.eh_pasta else 0) for i in resto),
                modificado_em=max(mtimes) if mtimes else None,
                criado_em=None,
                permissoes="—",
                tipo_detalhado="Agrupado",
                maior_arquivo=maior_resto,
            ))
        return fixos

    @staticmethod
    def subfolders(path: str) -> List[str]:
        try:
            with os.scandir(path) as entries:
                names = [
                    entry.name for entry in entries
                    if entry.is_dir(follow_symlinks=False)
                    and not entry.is_symlink()
                    and not caminho_ignorado(entry.path)
                ]
        except OSError:
            return []
        return sorted(names, key=str.lower)


def parent_analysis_path(path: str, root: str, include_root_parent: bool) -> Tuple[str, bool]:
    parent = os.path.dirname(path)
    has_parent = bool(parent and parent != path and (path != root or include_root_parent))
    return parent, has_parent
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest discover -s tests -t . -v`
Expected: PASS (46 testes).

- [ ] **Step 5: Verificar que a interface ainda abre**

Run: `python proporcao_pastas.py "$HOME"` (no Windows: `python proporcao_pastas.py "%USERPROFILE%"`)
Expected: janela abre, tabela preenche, nenhum erro em `proporcao_pastas/proporcao_pastas.log`. Fechar a janela.

- [ ] **Step 6: Commit**

```bash
git add proporcao_pastas/infrastructure/file_system.py tests/test_scanner_cache.py
git commit -m "feat: scanner le e grava no cache persistente"
```

---

### Task 7: Caso de uso expondo o estado do cache

**Files:**
- Modify: `proporcao_pastas/application/analyze_folder.py:9-38`
- Create: `tests/test_analyze_folder_cache.py`

**Interfaces:**
- Consumes: `FileSystemScanner.is_folder_outdated`, `refresh_folder`, `ultima_atualizacao_global` (Task 6).
- Produces: `FolderAnalysis(..., cache_updated_at: Optional[float] = None, global_cache_updated_at: Optional[float] = None, is_outdated: bool = False)`; `AnalyzeFolder.refresh(path, root, include_root_parent, keep=(), progresso=None) -> FolderAnalysis`.

- [ ] **Step 1: Write the failing test**

```python
"""Testes do caso de uso com dados de cache."""
import os
import tempfile
import unittest

from proporcao_pastas.application.analyze_folder import AnalyzeFolder
from proporcao_pastas.infrastructure.cache_storage import SqliteCacheStorage
from proporcao_pastas.infrastructure.file_system import FileSystemScanner


class TestAnalyzeFolderComCache(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.raiz = os.path.join(self.dir.name, "raiz")
        os.makedirs(os.path.join(self.raiz, "sub"))
        with open(os.path.join(self.raiz, "sub", "a.bin"), "wb") as f:
            f.write(b"x" * 100)
        self.storage = SqliteCacheStorage(os.path.join(self.dir.name, "cache.db"))
        self.scanner = FileSystemScanner(storage=self.storage)
        self.caso = AnalyzeFolder(self.scanner)

    def tearDown(self):
        self.storage.close()
        self.dir.cleanup()

    def test_execute_traz_dados_do_cache(self):
        analise = self.caso.execute(self.raiz, self.raiz, False)
        self.assertEqual(analise.total, 100)
        self.assertIsNotNone(analise.cache_updated_at)
        self.assertIsNotNone(analise.global_cache_updated_at)
        self.assertFalse(analise.is_outdated)

    def test_refresh_revarre_e_devolve_total_novo(self):
        self.caso.execute(self.raiz, self.raiz, False)
        with open(os.path.join(self.raiz, "sub", "b.bin"), "wb") as f:
            f.write(b"y" * 50)
        analise = self.caso.refresh(os.path.join(self.raiz, "sub"), self.raiz, True)
        self.assertEqual(analise.total, 150)
        self.assertFalse(analise.is_outdated)
        self.assertEqual(self.storage.get_folder(self.raiz).tamanho, 150)

    def test_refresh_repassa_o_progresso(self):
        self.caso.execute(self.raiz, self.raiz, False)
        vistos = []
        self.caso.refresh(self.raiz, self.raiz, False, progresso=vistos.append)
        self.assertTrue(vistos)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_analyze_folder_cache -v`
Expected: FAIL — `AttributeError: 'FolderAnalysis' object has no attribute 'cache_updated_at'`.

- [ ] **Step 3: Write minimal implementation**

```python
"""Orquestracao da analise de uma pasta."""
from dataclasses import dataclass, field
from typing import Iterable, List, Optional

from proporcao_pastas.domain.models import FolderStats, ItemPasta
from proporcao_pastas.infrastructure.file_system import FileSystemScanner, parent_analysis_path


@dataclass(frozen=True)
class FolderAnalysis:
    path: str
    total: int
    parent_total: Optional[int]
    items: List[ItemPasta]
    folder_stats: FolderStats = field(default_factory=FolderStats)
    cache_updated_at: Optional[float] = None
    global_cache_updated_at: Optional[float] = None
    is_outdated: bool = False


class AnalyzeFolder:
    def __init__(self, scanner: FileSystemScanner) -> None:
        self.scanner = scanner

    def execute(
        self,
        path: str,
        root: str,
        include_root_parent: bool,
        keep: Iterable[str] = (),
    ) -> FolderAnalysis:
        folder_stats = self.scanner.stats(path)
        return self._montar(path, root, include_root_parent, keep, folder_stats)

    def refresh(
        self,
        path: str,
        root: str,
        include_root_parent: bool,
        keep: Iterable[str] = (),
        progresso=None,
    ) -> FolderAnalysis:
        """Revarre a pasta e devolve a analise ja com o cache novo."""
        folder_stats = self.scanner.refresh_folder(path, progresso=progresso)
        return self._montar(path, root, include_root_parent, keep, folder_stats)

    def _montar(self, path, root, include_root_parent, keep, folder_stats) -> FolderAnalysis:
        parent, has_parent = parent_analysis_path(path, root, include_root_parent)
        parent_total = self.scanner.size(parent) if has_parent else None
        return FolderAnalysis(
            path=path,
            total=folder_stats.tamanho,
            parent_total=parent_total,
            items=self.scanner.children(path, keep),
            folder_stats=folder_stats,
            cache_updated_at=folder_stats.cache_updated_at,
            global_cache_updated_at=self.scanner.ultima_atualizacao_global(),
            is_outdated=self.scanner.is_folder_outdated(path),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest discover -s tests -t . -v`
Expected: PASS (49 testes).

- [ ] **Step 5: Commit**

```bash
git add proporcao_pastas/application/analyze_folder.py tests/test_analyze_folder_cache.py
git commit -m "feat: expoe estado do cache e atualizacao seletiva no caso de uso"
```

---

### Task 8: Interface — status do cache, botão e coluna

**Files:**
- Modify: `proporcao_pastas/presentation/tk_app.py` (construtor, barra de ferramentas, tabela, `mostrar`, `preencher_tabela`, `atualizar`)

**Interfaces:**
- Consumes: `FolderAnalysis.cache_updated_at/global_cache_updated_at/is_outdated` e `AnalyzeFolder.refresh` (Task 7); `formatar_status_cache`, `formatar_data` (Task 1); `SqliteCacheStorage`, `caminho_padrao_cache` (Task 4).
- Produces: `App.__init__(raiz, pai_na_raiz, master=None, storage=None)`; `App.atualizar_cache()`; rótulo `self.lbl_cache`; coluna `"cache"`.

- [ ] **Step 1: Ligar o storage no App**

Em `tk_app.py`, nos imports:

```python
from proporcao_pastas.domain.formatting import formatar_status_cache
from proporcao_pastas.infrastructure.cache_storage import SqliteCacheStorage, caminho_padrao_cache
```

No `__init__`, trocar a criação do scanner:

```python
    def __init__(self, raiz, pai_na_raiz, master=None, storage=None):
        self.pai_na_raiz = pai_na_raiz
        self.raiz = raiz
        self.storage = storage if storage is not None else SqliteCacheStorage(caminho_padrao_cache())
        self.scanner = FileSystemScanner(storage=self.storage)
        self.analyze_folder = AnalyzeFolder(self.scanner)
```

E fechar o banco ao sair, no fim do `__init__` (antes de `self.w.after(100, self.poll)`):

```python
        self.w.protocol("WM_DELETE_WINDOW", self.fechar)
```

Com o método:

```python
    def fechar(self):
        try:
            self.storage.close()
        finally:
            self.w.destroy()
```

- [ ] **Step 2: Trocar o botão e acrescentar o rótulo de status**

Na barra de ferramentas, substituir o botão "Atualizar":

```python
        ttk.Button(barra, text="Atualizar cache", command=self.atualizar_cache).pack(
            side="left", padx=2)
```

Depois de `self.caminho.pack(fill="x")`, acrescentar:

```python
        self.lbl_cache = tk.Label(txt, bg="white", fg="#666666", font=("Segoe UI", 9, "bold"),
                                  anchor="w", justify="left", wraplength=700, text="")
        self.lbl_cache.pack(fill="x")
```

- [ ] **Step 3: Acrescentar a coluna da tabela**

Trocar a tupla de colunas e acrescentar cabeçalho e largura (reduzindo `maior` para caber):

```python
        colunas = ("tam", "pct", "tipo", "itens", "maior", "modificado", "criado", "perm", "cache")
```

```python
        self.tab.heading("cache", text="Cache atualizado em", anchor="center")
```

```python
        self.tab.column("maior", width=130, minwidth=100, anchor="w", stretch=True)
        self.tab.column("cache", width=125, anchor="center", stretch=False)
```

- [ ] **Step 4: Preencher a coluna e o rótulo**

Em `preencher_tabela`, acrescentar antes do `self.tab.insert`:

```python
            cache_em = formatar_data(getattr(item, "cache_updated_at", None), segundos=True)
```

e incluir `cache_em` no fim da tupla `values=(...)`, depois de `perm`.

Em `mostrar`, trocar a assinatura e usar os campos novos. A fila passa a carregar a análise inteira:

```python
    def trabalho(self, path, tok, marcar, revarrer=False):
        if revarrer:
            resultado = self.analyze_folder.refresh(
                path, self.raiz, self.pai_na_raiz, marcar,
                progresso=lambda p: self.fila_status.put(f"Revarrendo {p}..."),
            )
        else:
            resultado = self.analyze_folder.execute(path, self.raiz, self.pai_na_raiz, marcar)
        self.fila.put((resultado, tok))
```

No `__init__`, junto de `self.fila = queue.Queue()`:

```python
        self.fila_status = queue.Queue()
```

Em `poll`, drenar as duas filas:

```python
    def poll(self):
        try:
            while True:
                self.status.config(text=self.fila_status.get_nowait(), fg=COR_TEXTO)
        except queue.Empty:
            pass
        try:
            while True:
                self.mostrar(*self.fila.get_nowait())
        except queue.Empty:
            pass
        finally:  # um erro em mostrar() nao pode parar as proximas atualizacoes
            self.w.after(100, self.poll)
```

E `mostrar` recebe a análise:

```python
    def mostrar(self, analise, tok):
        if tok != self.token:  # usuario ja clicou em outra pasta
            return
        path, total, total_pai = analise.path, analise.total, analise.parent_total
        lista, folder_stats = analise.items, analise.folder_stats
        self.lbl_cache.config(
            text=formatar_status_cache(
                analise.cache_updated_at, analise.global_cache_updated_at, analise.is_outdated
            ),
            fg="#B06000" if analise.is_outdated else "#1A7F37",
        )
        self.lista, self.total, self.sel_idx = lista, total, set()
```

(o restante do corpo de `mostrar` fica como está, já usando `path`, `total`, `total_pai`, `lista`, `folder_stats`)

- [ ] **Step 5: Trocar `atualizar` por `atualizar_cache`**

```python
    def atualizar_cache(self):
        """Revarre so a pasta selecionada e corrige os ancestrais."""
        sel = self.tree.selection()
        if sel and sel[0] in self.nos:
            self.analisar(self.nos[sel[0]], revarrer=True)
```

E `analisar` passa a repassar a flag:

```python
    def analisar(self, path, marcar=(), revarrer=False):
```

```python
        threading.Thread(target=self.trabalho,
                         args=(path, tok, self.marcar, revarrer), daemon=True).start()
```

- [ ] **Step 6: Rodar os testes e a interface**

Run: `python -m unittest discover -s tests -t . -v`
Expected: PASS (49 testes, nenhum quebrado).

Run: `python proporcao_pastas.py "$HOME"`
Expected: rótulo de cache visível abaixo do caminho; abrir uma pasta duas vezes — na segunda a resposta é imediata; botão "Atualizar cache" revarre e a data/hora muda; coluna "Cache atualizado em" preenchida. Nada em `proporcao_pastas.log`.

- [ ] **Step 7: Commit**

```bash
git add proporcao_pastas/presentation/tk_app.py
git commit -m "feat: mostra status do cache e atualiza cache da pasta selecionada"
```

---

### Task 9: Árvore multi-raiz e abertura sem diálogo

**Files:**
- Modify: `proporcao_pastas/presentation/tk_app.py` (`definir_raiz`, `trocar`, `selecionar`, `popular`)
- Modify: `proporcao_pastas/main.py:28-49`
- Create: `tests/test_multi_raiz.py`

**Interfaces:**
- Consumes: `list_system_roots` (Task 3); `parent_analysis_path` (Task 6).
- Produces: `App.definir_raizes(caminhos: List[str]) -> None` (mantém `definir_raiz(caminho)` como atalho para uma só); `App.raizes: List[str]`; `raiz_de(path: str, raizes: List[str]) -> str` em `file_system.py`.

**Decisão:** sem nó artificial "Este computador". Cada raiz é um nó de topo da árvore. `self.raiz` deixa de ser único: a raiz usada no cálculo de porcentagem do pai passa a ser a raiz que contém o caminho analisado.

- [ ] **Step 1: Write the failing test**

```python
"""Testes da escolha de raiz em modo multi-raiz."""
import unittest

from proporcao_pastas.infrastructure.file_system import parent_analysis_path, raiz_de


class TestRaizDe(unittest.TestCase):
    def test_escolhe_a_raiz_que_contem_o_caminho(self):
        raizes = ["/", "/Volumes/Backup"]
        self.assertEqual(raiz_de("/Volumes/Backup/fotos", raizes), "/Volumes/Backup")
        self.assertEqual(raiz_de("/Users/maria", raizes), "/")

    def test_prefere_a_raiz_mais_especifica(self):
        raizes = ["/", "/Volumes", "/Volumes/Backup"]
        self.assertEqual(raiz_de("/Volumes/Backup/x", raizes), "/Volumes/Backup")

    def test_caminho_fora_das_raizes_volta_ele_mesmo(self):
        self.assertEqual(raiz_de("/outro/lugar", ["/Volumes"]), "/outro/lugar")

    def test_raiz_nao_tem_pai_quando_nao_e_para_incluir(self):
        _, tem_pai = parent_analysis_path("/Volumes/Backup", "/Volumes/Backup", False)
        self.assertFalse(tem_pai)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_multi_raiz -v`
Expected: FAIL — `ImportError: cannot import name 'raiz_de'`.

- [ ] **Step 3: Write minimal implementation**

Em `file_system.py`, ao lado de `parent_analysis_path`:

```python
def raiz_de(path: str, raizes: List[str]) -> str:
    """Raiz mais especifica que contem o caminho; o proprio caminho se nenhuma contiver."""
    candidatas = [
        r for r in raizes
        if path == r or path.startswith(r.rstrip(os.sep) + os.sep)
    ]
    return max(candidatas, key=len) if candidatas else path
```

Em `tk_app.py`:

```python
    def definir_raizes(self, caminhos):
        self.raizes = list(caminhos)
        self.raiz = self.raizes[0]
        for i in self.tree.get_children():
            self.tree.delete(i)
        self.nos.clear()
        primeiro = None
        for caminho in self.raizes:
            iid = self.inserir("", caminho, os.path.basename(caminho.rstrip(os.sep)) or caminho)
            primeiro = primeiro or iid
        if primeiro:
            self.popular(primeiro)
            self.tree.item(primeiro, open=True)
            self.tree.selection_set(primeiro)

    def definir_raiz(self, caminho):
        self.definir_raizes([caminho])
```

E `analisar` passa a resolver a raiz do caminho antes de montar a análise — em `trabalho`, trocar `self.raiz` por `raiz_de(path, self.raizes)`:

```python
    def trabalho(self, path, tok, marcar, revarrer=False):
        raiz = raiz_de(path, self.raizes)
        if revarrer:
            resultado = self.analyze_folder.refresh(
                path, raiz, self.pai_na_raiz, marcar,
                progresso=lambda p: self.fila_status.put(f"Revarrendo {p}..."),
            )
        else:
            resultado = self.analyze_folder.execute(path, raiz, self.pai_na_raiz, marcar)
        self.fila.put((resultado, tok))
```

Importar `raiz_de` em `tk_app.py`:

```python
from proporcao_pastas.infrastructure.file_system import FileSystemScanner, raiz_de
```

Em `trocar`, manter o diálogo mas voltando para uma raiz só:

```python
    def trocar(self):
        p = filedialog.askdirectory(title="Escolha a pasta inicial", initialdir=self.raiz)
        if p:
            self.pai_na_raiz = False
            self.definir_raizes([os.path.normpath(p)])
```

Em `main.py`, abrir direto em modo multi-raiz quando não houver argumento:

```python
    from proporcao_pastas.presentation.tk_app import App
    from proporcao_pastas.infrastructure.system_roots import list_system_roots

    if arg:
        path, include_root_parent = os.path.expanduser(arg.strip('"')), True
        if is_windows and len(path) == 2 and path[1] == ":":
            path += "\\"
        if path:
            App(os.path.normpath(os.path.abspath(path)), include_root_parent).rodar()
        return

    raizes = list_system_roots()
    app = App(raizes[0], False)
    app.definir_raizes(raizes)
    app.rodar()
```

Com isso o caminho sem argumento não usa mais `tk.Tk()` nem `filedialog`, então as duas linhas `from tkinter import filedialog` e `import tkinter as tk` saem de `main.py` (`main.py:24-25`). O diálogo continua existindo na interface, pelo botão "Trocar pasta...", que importa `filedialog` em `tk_app.py`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest discover -s tests -t . -v`
Expected: PASS (53 testes).

- [ ] **Step 5: Verificar a interface sem argumento**

Run: `python proporcao_pastas.py`
Expected: abre sem pedir pasta; árvore mostra todas as unidades (Windows) ou `/` (macOS); clicar numa pasta analisa normalmente; "Trocar pasta..." continua funcionando. Nada em `proporcao_pastas.log`.

- [ ] **Step 6: Commit**

```bash
git add proporcao_pastas/infrastructure/file_system.py proporcao_pastas/presentation/tk_app.py proporcao_pastas/main.py tests/test_multi_raiz.py
git commit -m "feat: abre em modo multi-raiz sem pedir pasta inicial"
```

---

### Task 10: Varredura total opcional, com progresso

**Files:**
- Modify: `proporcao_pastas/presentation/tk_app.py` (barra de ferramentas + método novo)
- Modify: `proporcao_pastas/infrastructure/file_system.py` (método `mapear_raizes`)
- Create: `tests/test_mapear_raizes.py`

**Interfaces:**
- Consumes: `FileSystemScanner.stats`, `subfolders` (Task 6).
- Produces: `FileSystemScanner.mapear_raizes(raizes: List[str], progresso=None, cancelado=None) -> int` (retorna quantas pastas de primeiro nível foram varridas); botão "Mapear discos" em `tk_app`.

**Por que opcional:** calcular o tamanho de uma raiz exige recursão por toda a subárvore. Fazer isso na abertura deixaria a primeira execução inutilizável (ver "Divergências", item 2). Como ação explícita, com progresso e cancelamento, o custo fica visível e sob controle do usuário.

- [ ] **Step 1: Write the failing test**

```python
"""Testes da varredura total opcional."""
import os
import tempfile
import unittest

from proporcao_pastas.infrastructure.cache_storage import SqliteCacheStorage
from proporcao_pastas.infrastructure.file_system import FileSystemScanner


class TestMapearRaizes(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.raiz = os.path.join(self.dir.name, "raiz")
        for nome in ("a", "b", "c"):
            os.makedirs(os.path.join(self.raiz, nome))
            with open(os.path.join(self.raiz, nome, "f.bin"), "wb") as f:
                f.write(b"x" * 10)
        self.storage = SqliteCacheStorage(os.path.join(self.dir.name, "cache.db"))
        self.scanner = FileSystemScanner(storage=self.storage)

    def tearDown(self):
        self.storage.close()
        self.dir.cleanup()

    def test_mapeia_e_grava_todas_as_pastas(self):
        total = self.scanner.mapear_raizes([self.raiz])
        self.assertEqual(total, 3)
        self.assertEqual(self.storage.get_folder(self.raiz).tamanho, 30)
        self.assertIsNotNone(self.storage.get_folder(os.path.join(self.raiz, "a")))

    def test_informa_progresso(self):
        vistos = []
        self.scanner.mapear_raizes([self.raiz], progresso=lambda p, i, n: vistos.append((p, i, n)))
        self.assertEqual(len(vistos), 3)
        self.assertEqual(vistos[-1][1:], (3, 3))

    def test_respeita_cancelamento(self):
        vistos = []
        self.scanner.mapear_raizes(
            [self.raiz],
            progresso=lambda p, i, n: vistos.append(p),
            cancelado=lambda: len(vistos) >= 1,
        )
        self.assertEqual(len(vistos), 1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_mapear_raizes -v`
Expected: FAIL — `AttributeError: 'FileSystemScanner' object has no attribute 'mapear_raizes'`.

- [ ] **Step 3: Write minimal implementation**

Em `FileSystemScanner`, depois de `refresh_folder`:

```python
    def mapear_raizes(self, raizes: List[str], progresso=None, cancelado=None) -> int:
        """Varre as raizes inteiras, uma pasta de primeiro nivel por vez.

        Varredura completa e cara: so deve ser chamada por acao explicita do
        usuario, em thread separada, com progresso e cancelamento."""
        alvos = []
        for raiz in raizes:
            alvos.extend(os.path.join(raiz, nome) for nome in self.subfolders(raiz))
        total = len(alvos)
        feitos = 0
        for alvo in alvos:
            if cancelado and cancelado():
                break
            self.stats(alvo, usar_cache=False)
            feitos += 1
            if progresso:
                progresso(alvo, feitos, total)
        for raiz in raizes:
            if cancelado and cancelado():
                break
            # _varrer com usar_cache=True: le as entradas da raiz de novo, mas
            # reaproveita as subpastas ja medidas acima em vez de revarrer tudo.
            self._varrer(raiz, True)
        return feitos
```

- [ ] **Step 4: Ligar o botão na interface**

Na barra de ferramentas de `tk_app.py`, depois de "Atualizar cache":

```python
        self.btn_mapear = ttk.Button(barra, text="Mapear discos",
                                     command=self.mapear_discos)
        self.btn_mapear.pack(side="left", padx=2)
```

No `__init__`, junto das outras flags:

```python
        self.cancelar_mapeamento = False
```

E os métodos:

```python
    def mapear_discos(self):
        """Varredura completa das raizes, em thread, com progresso na barra."""
        if self.btn_mapear["text"] == "Cancelar mapeamento":
            self.cancelar_mapeamento = True
            return
        self.cancelar_mapeamento = False
        self.btn_mapear.config(text="Cancelar mapeamento")
        threading.Thread(target=self._mapear, daemon=True).start()

    def _mapear(self):
        def progresso(caminho, feitos, total):
            self.fila_status.put(f"Mapeando {feitos}/{total}: {caminho}")

        self.scanner.mapear_raizes(
            self.raizes, progresso=progresso, cancelado=lambda: self.cancelar_mapeamento
        )
        self.fila_status.put("Mapeamento concluído" if not self.cancelar_mapeamento
                             else "Mapeamento cancelado")
        self.w.after(0, lambda: self.btn_mapear.config(text="Mapear discos"))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m unittest discover -s tests -t . -v`
Expected: PASS (56 testes).

- [ ] **Step 6: Verificar na interface**

Run: `python proporcao_pastas.py "$HOME"`
Expected: "Mapear discos" mostra progresso na barra de status, o botão vira "Cancelar mapeamento", o cancelamento responde, e depois do mapeamento abrir pastas é imediato.

- [ ] **Step 7: Commit**

```bash
git add proporcao_pastas/infrastructure/file_system.py proporcao_pastas/presentation/tk_app.py tests/test_mapear_raizes.py
git commit -m "feat: adiciona varredura total opcional com progresso e cancelamento"
```

---

### Task 11: Documentação

**Files:**
- Modify: `README.md` (seções "O que faz", "Como funciona", "Limitações")

**Interfaces:**
- Consumes: comportamento das Tasks 1-10.
- Produces: nada em código.

- [ ] **Step 1: Documentar o cache no README**

Em "O que faz", acrescentar:

```markdown
- Cache persistente: o que já foi medido fica salvo entre execuções, então reabrir uma pasta é imediato.
- Mostra na tela a data e hora da última medição da pasta e avisa quando o cache está defasado.
- Botão "Atualizar cache" revarre apenas a pasta selecionada e corrige os totais das pastas pai.
- Botão "Mapear discos" varre tudo de uma vez (opcional, com progresso e cancelamento).
```

Em "Como funciona", acrescentar:

```markdown
- O cache fica em um banco SQLite (biblioteca padrão do Python), em
  `%LOCALAPPDATA%\ProporcaoPastas\cache.db` no Windows e
  `~/Library/Caches/ProporcaoPastas/cache.db` no macOS. Apagar esse arquivo
  limpa o cache.
- Cada pasta medida guarda tamanho, contagem de arquivos e subpastas, maior
  arquivo, metadados e a data/hora da medição. De cada pasta são guardados os
  50 maiores arquivos diretos, mais o total do que sobrou — o suficiente para
  reconstruir a tabela e o gráfico sem ler o disco.
- A varredura ignora links simbólicos e caminhos que duplicariam a contagem ou
  travariam a leitura (`WinSxS`, `System Volume Information` e `$Recycle.Bin` no
  Windows; `/System/Volumes/Data`, `/dev`, `/proc` e `/net` no macOS).
```

Em "Limitações", acrescentar:

```markdown
- O aviso de cache defasado compara a data de modificação da pasta e das
  subpastas diretas. Uma alteração mais profunda na árvore não é detectada: a
  pasta pode aparecer como atualizada estando defasada. O cache também é
  considerado defasado depois de 7 dias.
- Depois de "Atualizar cache" em uma subpasta, os totais das pastas pai são
  corrigidos pela diferença daquela subpasta; alterações feitas em pastas irmãs
  no mesmo período continuam invisíveis até que elas também sejam atualizadas.
- O banco de cache guarda caminhos e nomes de arquivos em texto plano no
  diretório de cache do usuário.
```

- [ ] **Step 2: Rodar a suíte inteira uma última vez**

Run: `python -m unittest discover -s tests -t . -v`
Expected: PASS (56 testes).

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: documenta cache persistente, local do banco e limitacoes"
```

---

## Ordem de execução e dependências

```
Task 1 (formatacao) ─┐
Task 2 (modelos) ────┼─> Task 6 (scanner) ─> Task 7 (caso de uso) ─> Task 8 (interface) ─> Task 9 (multi-raiz) ─> Task 10 (mapear) ─> Task 11 (docs)
Task 3 (raizes) ─────┤
Task 4 (storage) ────┴─> Task 5 (delta)
```

Tasks 1, 2, 3 e 4 são independentes e podem ser feitas em paralelo. Task 5 depende da 4. Task 6 depende de 2, 3, 4 e 5.
