# Proporção de Pastas

Programa para Windows, feito em Python, que mostra quanto cada pasta ocupa em relação à pasta pai, em um clique. Foi desenvolvido como trabalho final da disciplina de Sistemas Operacionais (FURB), aplicando conceitos de gerência de arquivos e organização de diretórios.

## O que faz

- Árvore de pastas à esquerda, no estilo do Explorer, com carregamento sob demanda.
- Ao clicar em uma pasta, mostra o tamanho dela e a porcentagem em relação à pasta pai, com barra de uso.
- Gráfico de pizza (rosca) com a divisão da pasta entre subpastas e arquivos; o excedente é agrupado em "Outros".
- Soma de itens: selecione vários itens na tabela (Ctrl ou Shift + clique), fatias da pizza ou várias pastas irmãs na árvore para ver quanto representam da pasta (exemplo: 2 arquivos de 100 MB em uma pasta de 300 MB = 200 MB de 300 MB, 66,7%).
- Duplo clique em uma subpasta da tabela navega até ela.
- Integração opcional com o clique direito do Windows.

## Requisitos

- Windows 10 ou 11
- Python 3.8 ou superior (já inclui tkinter; nenhuma biblioteca externa é necessária)

## Como usar

```
python proporcao_pastas.py
python proporcao_pastas.py "C:\Users\seu_usuario\Documents"
```

Para adicionar ao menu de clique direito das pastas (somente para o usuário atual, sem administrador):

```
python proporcao_pastas.py --instalar
python proporcao_pastas.py --remover
```

No Windows 11 a opção aparece em "Mostrar mais opções".

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
  integração com o registro do Windows.
- `proporcao_pastas/presentation`: interface Tkinter e gerenciamento dos
  eventos da tela.

Essa separação permite testar o cálculo e a leitura de pastas sem iniciar a
interface gráfica e deixa a apresentação dependente dos casos de uso, não do
detalhe de como o sistema de arquivos é consultado.

## Limitações

- O tamanho exibido é o tamanho lógico dos arquivos, não o espaço ocupado em disco. Arquivos do OneDrive disponíveis só online contam com o tamanho cheio.
- A primeira leitura de pastas muito grandes pode demorar.
