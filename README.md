# Proporção de Pastas

Programa multiplataforma (Windows e macOS), feito em Python, que mostra quanto cada pasta ocupa em relação à pasta pai, em um clique. Foi desenvolvido como trabalho final da disciplina de Sistemas Operacionais (FURB), aplicando conceitos de gerência de arquivos e organização de diretórios.

## O que faz

- Identifica automaticamente o sistema operacional (`Windows` ou `macOS` / `Darwin`) ao iniciar.
- Árvore de pastas à esquerda, no estilo do Explorer/Finder, com carregamento sob demanda.
- Ao clicar em uma pasta, mostra o tamanho dela, a porcentagem em relação à pasta pai (com barra de uso), o total de arquivos/subpastas e o maior arquivo.
- Tabela detalhada com informações específicas de cada arquivo e subpasta:
  - **Tamanho** e **%** em relação à pasta atual.
  - **Tipo / Extensão** detalhada (ex.: `Pasta`, `Arq (.py)`, `Arq (.pdf)`).
  - **Conteúdo** interno acumulado (quantidade de arquivos e subpastas).
  - **Maior Arquivo** encontrado dentro de cada subpasta.
  - **Modificado em** e **Criado em** (datas de metadados do sistema de arquivos).
  - **Permissões** de acesso do Sistema Operacional (formato POSIX `drwxr-xr-x` / `-rw-r--r--`).
- Gráfico de pizza (rosca) com a divisão da pasta entre subpastas e arquivos; o excedente é agrupado em "Outros".
- Soma de itens: selecione vários itens na tabela (`Ctrl` no Windows / `Cmd` no macOS ou `Shift` + clique), fatias da pizza ou várias pastas irmãs na árvore para ver quanto representam da pasta (exemplo: 2 arquivos de 100 MB em uma pasta de 300 MB = 200 MB de 300 MB, 66,7%).
- Duplo clique em uma subpasta da tabela navega até ela.
- Botão para abrir a pasta selecionada diretamente no Explorer (Windows) ou no Finder (macOS).
- Integração opcional com o clique direito do Windows (menu de contexto) e do macOS (Ações Rápidas do Finder).

## Requisitos

- Windows 10/11 ou macOS
- Python 3.8 ou superior com `tkinter` (nenhuma biblioteca externa é necessária)
  - *Nota para macOS com Homebrew:* caso o Python do Homebrew não tenha o `tkinter`, instale com `brew install python-tk`.

## Como usar

No Windows:
```bash
python proporcao_pastas.py
python proporcao_pastas.py "C:\Users\seu_usuario\Documents"
```

No macOS:
```bash
python3 proporcao_pastas.py
python3 proporcao_pastas.py "/Users/seu_usuario/Documents"
```

Para adicionar ou remover do menu de clique direito das pastas (somente para o usuário atual, sem administrador):

```bash
# Windows (python) ou macOS (python3)
python proporcao_pastas.py --instalar
python proporcao_pastas.py --remover
```

- **Windows 10/11:** adiciona a opção "Ver proporção de pastas" ao clicar com o botão direito em uma pasta (no Windows 11, aparece em "Mostrar mais opções").
- **macOS:** cria uma Ação Rápida em `~/Library/Services` chamada "Ver proporção de pastas" (acessível no Finder clicando com o botão direito em uma pasta → *Ações Rápidas* ou *Serviços*).

## Como funciona

- O tamanho de cada pasta é calculado por recursão sobre a estrutura em árvore do sistema de arquivos (`os.scandir`).
- Os tamanhos ficam em cache: ao calcular a pasta pai, o tamanho de todas as subpastas já fica guardado.
- O cálculo roda em uma thread separada, então a interface não trava em pastas grandes.
- Links simbólicos são ignorados, para não contar o mesmo conteúdo duas vezes; pastas sem permissão de leitura contam como 0.

## Organização do código

O projeto é dividido em camadas, mantendo `proporcao_pastas.py` como ponto de
entrada compatível:

- `proporcao_pastas/domain`: modelos e regras sem dependência de interface ou
  sistema operacional.
- `proporcao_pastas/application`: casos de uso, como a análise de uma pasta.
- `proporcao_pastas/infrastructure`: leitura do sistema de arquivos e
  integração com o menu de contexto do Windows e macOS.
- `proporcao_pastas/presentation`: interface Tkinter e gerenciamento dos
  eventos da tela.

Essa separação permite testar o cálculo e a leitura de pastas sem iniciar a
interface gráfica e deixa a apresentação dependente dos casos de uso, não do
detalhe de como o sistema de arquivos é consultado.

## Limitações

- O tamanho exibido é o tamanho lógico dos arquivos, não o espaço ocupado em disco. Arquivos do OneDrive/iCloud disponíveis só online contam com o tamanho cheio.
- A primeira leitura de pastas muito grandes pode demorar.
