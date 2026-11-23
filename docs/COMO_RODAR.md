# Como rodar o Proporção de Pastas

Guia de instalação e execução no Windows e no macOS. O programa usa **apenas a
biblioteca padrão do Python** — não há `pip install`, não há ambiente virtual
obrigatório, não há dependência externa nenhuma.

- [Windows](#windows)
- [macOS](#macos)
- [Rodar os testes](#rodar-os-testes)
- [Onde fica o cache](#onde-fica-o-cache)
- [Problemas comuns](#problemas-comuns)

---

## Windows

### 1. Instalar o Python

Precisa ser **Python 3.8 ou superior**. Baixe em [python.org/downloads](https://www.python.org/downloads/)
e, no instalador, marque **"Add python.exe to PATH"**.

Confira no PowerShell ou no Prompt de Comando:

```bat
python --version
```

Se o comando não for encontrado, tente `py --version` e use `py` no lugar de
`python` nos comandos seguintes.

O `tkinter` (a interface gráfica) vem junto com o instalador oficial. Para
confirmar:

```bat
python -c "import tkinter; print('tkinter ok')"
```

### 2. Baixar o projeto

```bat
git clone https://github.com/rodrigo-leitzke/proporcao-pastas.git
cd proporcao-pastas
```

Sem o Git, baixe o ZIP pelo GitHub ("Code" → "Download ZIP") e extraia.

### 3. Rodar

```bat
python proporcao_pastas.py
```

Abre com todas as unidades do sistema (`C:\`, `D:\`, ...) na árvore da esquerda.
Na primeira execução o programa abre **parado**: nada é medido até você escolher
uma pasta, porque varrer um disco inteiro leva de minutos a dezenas de minutos.

Para abrir direto em uma pasta:

```bat
python proporcao_pastas.py "C:\Users\seu_usuario\Documents"
```

### 4. Opcional: menu do clique direito

```bat
python proporcao_pastas.py --instalar
```

Adiciona "Ver proporção de pastas" ao clicar com o botão direito em uma pasta
(no Windows 11 a opção aparece em **Mostrar mais opções**). Vale só para o
usuário atual e não pede administrador. Para remover:

```bat
python proporcao_pastas.py --remover
```

O atalho do menu usa `pythonw.exe` quando ele existe, para abrir sem a janela
preta do console atrás do programa.

---

## macOS

### 1. Instalar o Python com tkinter

O macOS vem com uma versão antiga do Python. Instale uma atual pelo
[python.org](https://www.python.org/downloads/macos/) (o instalador oficial já
inclui o `tkinter`) ou pelo Homebrew:

```bash
brew install python python-tk
```

> **Atenção:** o Python do Homebrew **não** inclui `tkinter` por padrão. Sem o
> pacote `python-tk` o programa falha com `ModuleNotFoundError: No module named
> 'tkinter'`.

Confira:

```bash
python3 --version
python3 -c "import tkinter; print('tkinter ok')"
```

### 2. Baixar o projeto

```bash
git clone https://github.com/rodrigo-leitzke/proporcao-pastas.git
cd proporcao-pastas
```

### 3. Rodar

```bash
python3 proporcao_pastas.py
```

Abre com a raiz do sistema (`/`) na árvore. Como no Windows, a primeira execução
abre parada até você escolher uma pasta.

Para abrir direto em uma pasta:

```bash
python3 proporcao_pastas.py "/Users/seu_usuario/Documents"
```

### 4. Opcional: Ação Rápida do Finder

```bash
python3 proporcao_pastas.py --instalar
```

Cria uma Ação Rápida em `~/Library/Services` chamada "Ver proporção de pastas",
acessível clicando com o botão direito em uma pasta no Finder, em **Ações
Rápidas** ou **Serviços**. Para remover:

```bash
python3 proporcao_pastas.py --remover
```

### Permissões do macOS

Ao medir pastas como `~/Documents`, `~/Desktop` ou `~/Downloads`, o macOS pode
pedir autorização de acesso. Se as pastas aparecerem com tamanho 0, autorize o
Terminal (ou o Python) em **Ajustes do Sistema → Privacidade e Segurança →
Acesso total ao disco**.

---

## Rodar os testes

A suíte usa só o `unittest` da biblioteca padrão e não abre janela nenhuma:

```bash
# Windows
python -m unittest discover -s tests -t . -v

# macOS
python3 -m unittest discover -s tests -t . -v
```

Os testes criam diretórios e bancos temporários; nada é gravado no seu cache
real nem na sua pasta pessoal.

---

## Onde fica o cache

| Sistema | Caminho |
| --- | --- |
| Windows | `%LOCALAPPDATA%\ProporcaoPastas\cache.db` |
| macOS | `~/Library/Caches/ProporcaoPastas/cache.db` |

É um banco SQLite comum. **Apagar o arquivo zera o cache** — nada mais é
perdido, o programa volta a medir conforme você navega. Se o arquivo estiver
corrompido ou tiver sido gravado por uma versão antiga do programa, ele é
descartado e recriado automaticamente, com um aviso na barra de status.

---

## Problemas comuns

**`ModuleNotFoundError: No module named 'tkinter'`**
Falta o pacote da interface gráfica. No macOS com Homebrew: `brew install
python-tk`. No Linux (não é plataforma suportada, mas funciona para os testes):
`sudo apt install python3-tk`.

**Dei duplo clique e nada aconteceu**
Rode pelo terminal para ver o erro. Se o programa foi aberto por `pythonw` (pelo
menu de contexto), não há console: o erro fica no arquivo
`proporcao_pastas/presentation/proporcao_pastas.log`.

**A primeira medição de uma pasta grande demora**
É esperado: o tamanho de uma pasta exige percorrer toda a subárvore dela. Depois
disso o resultado fica no cache e reabrir é imediato. Para medir tudo de uma vez,
use **Mapear discos**, que mostra progresso e pode ser cancelado.

**"Mapear discos" parece não cancelar na hora**
Ele para em alguns instantes, no meio da pasta em que estiver. O que já foi
medido fica no cache, e apertar "Mapear discos" de novo continua de onde parou.

**Pedi uma pasta enquanto o mapeamento rodava e ele parou**
É intencional: a sua pasta tem prioridade. O mapeamento é interrompido para não
deixar o painel esperando, e continua de onde parou quando você apertar "Mapear
discos" novamente.

**Os números não batem com o Explorer/Finder**
O programa mostra o tamanho lógico dos arquivos, não o espaço ocupado em disco.
Arquivos do OneDrive ou iCloud disponíveis só online contam com o tamanho cheio.
Veja a seção "Limitações" do [README](../README.md).
