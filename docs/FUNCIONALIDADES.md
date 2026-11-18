# O que o Proporção de Pastas faz

Documento de referência para quem vai usar, apresentar ou mexer no projeto.
Para instalar e executar, veja [COMO_RODAR.md](COMO_RODAR.md).

- [O problema que ele resolve](#o-problema-que-ele-resolve)
- [A tela](#a-tela)
- [Os quatro botões](#os-quatro-botões)
- [As colunas da tabela](#as-colunas-da-tabela)
- [Somar itens](#somar-itens)
- [O cache persistente](#o-cache-persistente)
- [Como o tamanho é calculado](#como-o-tamanho-é-calculado)
- [Organização do código](#organização-do-código)
- [Conceitos de Sistemas Operacionais aplicados](#conceitos-de-sistemas-operacionais-aplicados)

---

## O problema que ele resolve

O Explorer e o Finder mostram o tamanho de uma pasta, mas não respondem a
pergunta que importa quando o disco está cheio: **qual pasta está ocupando o
espaço, e quanto ela representa dentro da pasta que a contém?**

O programa responde isso em um clique: tamanho da pasta, porcentagem em relação
à pasta pai, e como o espaço dela se divide entre subpastas e arquivos.

## A tela

A janela tem dois painéis:

**Esquerda — árvore de pastas.** No estilo do Explorer/Finder, com carregamento
sob demanda: as subpastas de um nível só são lidas quando você expande aquele
nível. No Windows a árvore começa com todas as unidades (`C:\`, `D:\`, ...); no
macOS, com a raiz `/`.

**Direita — detalhes da pasta selecionada:**

1. **Nome e caminho** da pasta.
2. **Status do cache**, logo abaixo do caminho: `✅ Cache atualizado, última vez
   atualizado: 18/11/2026 14:07:09` ou `⚠️ Cache desatualizado, ...`. Quando a
   pasta nunca foi medida, aparece `Pasta ainda não está em cache`.
3. **Linha de uso**: `1,20 GB de 8,40 GB da pasta pai (14,3%)` com uma barra de
   proporção, mais o resumo de arquivos, subpastas e o maior arquivo.
4. **Gráfico de pizza** (rosca) com a divisão do espaço entre as subpastas e os
   arquivos diretos. São mostradas as 7 maiores fatias; o resto é agrupado em
   uma fatia "Outros", para o gráfico não virar confete.
5. **Tabela** com uma linha por subpasta e por arquivo direto, detalhada abaixo.

A linha de uso mostra `Tamanho total: ...`, sem porcentagem, quando não há pasta
pai medida — por exemplo em uma raiz de disco, ou quando a pasta pai é uma raiz
que ainda não está no cache (medir uma raiz inteira só para calcular a
porcentagem custaria minutos de varredura).

## Os quatro botões

| Botão | O que faz |
| --- | --- |
| **Atualizar cache** | Mede de novo **apenas a pasta selecionada** e a subárvore dela, e corrige os totais das pastas pai pela diferença. É a ação para usar quando você mexeu em uma pasta e quer o número novo. |
| **Mapear discos** | Varre **tudo**, de uma vez, com progresso na barra de status e botão de cancelar. Opcional e demorado; depois dele a navegação fica instantânea em qualquer pasta. Pula o que já está medido e em dia, então pode ser cancelado e retomado. |
| **Trocar pasta...** | Abre um seletor e passa a usar a pasta escolhida como raiz da árvore. |
| **Abrir no Explorer / Abrir no Finder** | Abre a pasta selecionada no gerenciador de arquivos do sistema. |

Pedir a análise de uma pasta enquanto o "Mapear discos" está rodando
**interrompe o mapeamento**: a sua pasta tem prioridade, e o mapeamento continua
de onde parou no próximo clique em "Mapear discos".

## As colunas da tabela

| Coluna | Conteúdo |
| --- | --- |
| **Nome** | Nome do arquivo ou da subpasta (ou `Outros (N itens)` no agrupamento). |
| **Tamanho** | Tamanho formatado em B, KB, MB, GB ou TB. |
| **%** | Participação do item no total da pasta atual. |
| **Tipo / Ext.** | `Pasta`, `Arq (.pdf)`, `Arquivo (s/ ext)` ou `Agrupado`. |
| **Conteúdo** | Para subpastas, quantos arquivos e subpastas existem dentro, de forma acumulada (`142 arq, 18 sub`). |
| **Maior Arquivo** | O maior arquivo encontrado dentro daquela subpasta, com o tamanho. |
| **Modificado em** | Data de modificação registrada pelo sistema de arquivos. |
| **Criado em** | Data de criação (`st_birthtime` no macOS, `st_ctime` nos outros). |
| **Permissões** | Permissões no formato POSIX: `drwxr-xr-x`, `-rw-r--r--`. |
| **Cache atualizado em** | Quando aquele item foi medido e guardado no cache. |

Duplo clique em uma subpasta da tabela navega até ela na árvore.

## Somar itens

Selecione vários itens para ver quanto eles representam juntos:

- na tabela, com `Ctrl` (Windows) ou `Cmd` (macOS), ou `Shift` + clique para um intervalo;
- clicando nas fatias da pizza, que liga e desliga a seleção do item;
- na árvore, selecionando várias pastas irmãs — o programa mostra a pasta pai
  com as escolhidas destacadas.

Exemplo: dois arquivos de 100 MB em uma pasta de 300 MB aparecem como
`200 MB de 300 MB (66,7%)`.

## O cache persistente

Medir uma pasta exige percorrer toda a subárvore dela, e isso é caro. Por isso o
resultado é guardado em um banco **SQLite** (biblioteca padrão do Python), e
reabrir o programa não recomeça do zero.

**O que é guardado de cada pasta medida:** tamanho, contagem acumulada de
arquivos e de subpastas, o maior arquivo da subárvore, o maior arquivo direto,
metadados (modificação, criação, permissões) e a data/hora da medição. Dos
arquivos diretos são guardados os **50 maiores**, mais o total do que sobrou —
o suficiente para reconstruir a tabela e o gráfico sem tocar no disco.

**Onde fica:** `%LOCALAPPDATA%\ProporcaoPastas\cache.db` no Windows,
`~/Library/Caches/ProporcaoPastas/cache.db` no macOS. Apagar o arquivo zera o
cache.

**Quando o programa considera o cache defasado:** quando a data de modificação
da pasta ou de uma subpasta direta é mais nova que a registrada, ou quando a
medição tem mais de 7 dias. Uma mudança mais profunda na árvore não é detectada
— esse e os outros limites estão na seção "Limitações" do
[README](../README.md).

**Correção por diferença.** Ao usar "Atualizar cache" em uma subpasta, o
programa não revarre o disco todo: ele calcula a diferença entre a medição nova
e a antiga e aplica essa diferença nas pastas pai, subindo até a raiz. É o que
torna a atualização de uma pasta funda uma operação rápida.

**Abertura sem varredura.** Ao abrir sem informar uma pasta, nenhum disco é
varrido sozinho: a raiz só é medida de imediato se já estiver no cache. Sem
cache, o programa abre parado esperando você escolher uma pasta, usar "Atualizar
cache" ou "Mapear discos".

## Como o tamanho é calculado

- Recursão sobre a árvore de diretórios com `os.scandir`, somando o tamanho dos
  arquivos de cada nível.
- O cálculo roda em uma **thread separada**, então a interface não congela em
  pastas grandes; o resultado volta para a tela por uma fila.
- **Links simbólicos são ignorados**, para o mesmo conteúdo não ser contado duas
  vezes.
- Pastas sem permissão de leitura contam como 0 e **não** são gravadas no cache,
  porque a falha costuma ser passageira (unidade removível fora do ar,
  antivírus, ACL) e um zero gravado duraria dias.
- Caminhos que duplicariam a contagem ou travariam a leitura são pulados:
  `WinSxS`, `System Volume Information`, `$Recycle.Bin`, `pagefile.sys`,
  `hiberfil.sys` e `swapfile.sys` no Windows; `/System/Volumes/Data`, `/dev`,
  `/proc`, `/net` e `/Volumes/Recovery` no macOS.

## Organização do código

Quatro camadas, com `proporcao_pastas.py` na raiz como ponto de entrada:

```
proporcao_pastas/
├── domain/           modelos e formatação, sem dependência de SO ou de tela
│   ├── models.py         FolderStats, ItemPasta
│   └── formatting.py     tamanhos, datas, tipos, status do cache
├── application/      casos de uso
│   └── analyze_folder.py AnalyzeFolder.execute() e .refresh()
├── infrastructure/   sistema operacional e persistência
│   ├── file_system.py        FileSystemScanner (medição e cache em memória)
│   ├── cache_storage.py      SqliteCacheStorage (banco do cache)
│   ├── system_roots.py       raízes de disco e caminhos ignorados
│   ├── windows_context_menu.py
│   └── macos_context_menu.py
└── presentation/     interface Tkinter
    └── tk_app.py
```

A regra de dependência é de fora para dentro: `domain` não importa nada das
outras camadas, `infrastructure` não importa `presentation`. É isso que permite
testar medição, cache e formatação sem abrir janela — a suíte tem 99 testes e
roda em menos de três segundos.

## Conceitos de Sistemas Operacionais aplicados

Para a apresentação da disciplina, o que o projeto exercita na prática:

- **Gerência de arquivos e diretórios**: travessia da árvore de diretórios,
  diferença entre arquivo e diretório, tamanho lógico versus espaço em disco.
- **Metadados de inode**: tamanho, datas de modificação e criação, bits de
  permissão lidos de `os.stat` e formatados como `drwxr-xr-x`.
- **Links simbólicos e reparse points**: por que precisam ser detectados e
  ignorados para o mesmo conteúdo não ser contado duas vezes.
- **Permissões e erros de acesso**: pastas protegidas do sistema levantam
  `OSError`, e o programa trata isso sem interromper a varredura.
- **Concorrência**: a medição roda em thread separada da interface, com fila
  para devolver resultados e um lock que serializa as varreduras para que duas
  não corrompam o total gravado.
- **Diferenças entre sistemas de arquivos**: unidades separadas no Windows
  (`C:\`, `D:\`) contra uma raiz única no macOS, hardlinks do `WinSxS`,
  firmlinks do APFS em `/System/Volumes/Data`.
