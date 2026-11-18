# Proporção de Pastas

Programa multiplataforma (Windows e macOS), feito em Python, que mostra quanto cada pasta ocupa em relação à pasta pai, em um clique. Foi desenvolvido como trabalho final da disciplina de Sistemas Operacionais (FURB), aplicando conceitos de gerência de arquivos e organização de diretórios.

## Documentação

- [Como rodar no Windows e no macOS](docs/COMO_RODAR.md) — instalação passo a passo, testes, cache e problemas comuns.
- [O que o programa faz](docs/FUNCIONALIDADES.md) — a tela, os botões, as colunas, como o cache funciona e a organização do código.

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
  - **Cache atualizado em**: data e hora em que aquele item foi medido e guardado no cache.
- Gráfico de pizza (rosca) com a divisão da pasta entre subpastas e arquivos; o excedente é agrupado em "Outros".
- Soma de itens: selecione vários itens na tabela (`Ctrl` no Windows / `Cmd` no macOS ou `Shift` + clique), fatias da pizza ou várias pastas irmãs na árvore para ver quanto representam da pasta (exemplo: 2 arquivos de 100 MB em uma pasta de 300 MB = 200 MB de 300 MB, 66,7%).
- Duplo clique em uma subpasta da tabela navega até ela.
- Botão para abrir a pasta selecionada diretamente no Explorer (Windows) ou no Finder (macOS).
- Integração opcional com o clique direito do Windows (menu de contexto) e do macOS (Ações Rápidas do Finder).
- Cache persistente: o que já foi medido fica salvo entre execuções, então reabrir uma pasta é imediato.
- Mostra na tela a data e hora da última medição da pasta e avisa quando o cache está defasado.
- Botão "Atualizar cache" revarre apenas a pasta selecionada e corrige os totais das pastas pai.
- Botão "Mapear discos" varre tudo de uma vez (opcional, com progresso e cancelamento). Pula o que já está medido e em dia, então pode ser cancelado e retomado.

## Requisitos

- Windows 10/11 ou macOS
- Python 3.8 ou superior com `tkinter` (nenhuma biblioteca externa é necessária)
  - *Nota para macOS com Homebrew:* caso o Python do Homebrew não tenha o `tkinter`, instale com `brew install python-tk`.

## Como usar

Instalação detalhada, verificação do `tkinter` e solução de problemas estão em
[docs/COMO_RODAR.md](docs/COMO_RODAR.md).

No Windows:
```bash
python proporcao_pastas.py                              # abre em todas as unidades do sistema
python proporcao_pastas.py "C:\Users\seu_usuario\Documents"  # abre direto nessa pasta
```

No macOS:
```bash
python3 proporcao_pastas.py                            # abre sem pedir pasta inicial
python3 proporcao_pastas.py "/Users/seu_usuario/Documents"  # abre direto nessa pasta
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
- O cálculo roda em uma thread separada, então a interface não trava em pastas grandes.
- Ao abrir sem informar uma pasta, nenhum disco é varrido sozinho: a raiz só é
  medida na abertura se já estiver em cache (leitura imediata). Sem cache, o
  programa abre parado, esperando você escolher uma pasta na árvore, usar
  "Atualizar cache" ou "Mapear discos" — varrer um disco inteiro leva minutos.
- Pedir a análise de uma pasta enquanto o "Mapear discos" está rodando
  interrompe o mapeamento: a pasta escolhida tem prioridade, e o mapeamento
  continua de onde parou no próximo clique no botão.
- A porcentagem em relação à pasta pai exige medir a pasta pai. Quando o pai é
  uma raiz de disco que ainda não está em cache, a análise mostra só o tamanho
  total, em vez de varrer o disco inteiro sem o usuário ter pedido; a
  porcentagem passa a aparecer depois que a raiz entra no cache.
- Links simbólicos são ignorados, para não contar o mesmo conteúdo duas vezes; pastas sem permissão de leitura contam como 0.
- O cache fica em um banco SQLite (biblioteca padrão do Python), em
  `%LOCALAPPDATA%\ProporcaoPastas\cache.db` no Windows e
  `~/Library/Caches/ProporcaoPastas/cache.db` no macOS. Apagar esse arquivo
  limpa o cache.
- Cada pasta medida guarda tamanho, contagem de arquivos e subpastas, maior
  arquivo, metadados e a data/hora da medição. De cada pasta são guardados os
  50 maiores arquivos diretos, mais o total do que sobrou — o suficiente para
  reconstruir a tabela e o gráfico sem ler o disco.
- A varredura ignora links simbólicos e caminhos que duplicariam a contagem ou
  travariam a leitura (`WinSxS`, `System Volume Information`, `$Recycle.Bin`,
  `pagefile.sys`, `hiberfil.sys` e `swapfile.sys` no Windows; `/System/Volumes/Data`,
  `/dev`, `/proc`, `/net` e `/Volumes/Recovery` no macOS).

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
- O aviso de cache defasado compara a data de modificação da pasta e das
  subpastas diretas. Uma alteração mais profunda na árvore não é detectada: a
  pasta pode aparecer como atualizada estando defasada. O cache também é
  considerado defasado depois de 7 dias.
- Depois de "Atualizar cache" em uma subpasta, os totais das pastas pai são
  corrigidos pela diferença daquela subpasta; alterações feitas em pastas irmãs
  no mesmo período continuam invisíveis até que elas também sejam atualizadas.
- O "Atualizar cache" apaga a subpasta do cache antes de medi-la de novo. Se o
  programa for encerrado exatamente entre os dois passos, as pastas pai ficam
  contando uma subárvore cujas linhas já não existem, e o total delas aparece
  maior que o real; atualizar aquela subpasta de novo corrige.
- Uma pasta que não pôde ser lida (sem permissão, unidade fora do ar) conta como
  0 e não entra no cache nem na contagem de subpastas da pasta pai, para que o
  número não fique errado quando ela for medida depois. Enquanto isso, o total
  da pasta pai não inclui o conteúdo dela.
- O banco de cache guarda caminhos e nomes de arquivos em texto plano no
  diretório de cache do usuário.
- O "Maior Arquivo" de uma pasta é o maior entre os arquivos dela e os das
  subpastas que já foram medidas. Se uma subpasta nunca foi aberta nem mapeada,
  ela não entra nessa comparação, então o valor exibido pode ser menor que o
  real até que a subpasta seja medida.
