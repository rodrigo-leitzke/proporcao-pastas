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
# a cada quantas pastas medidas a varredura total avisa o progresso: uma a uma
# encheria a fila da interface com milhoes de mensagens que ninguem le
PASTAS_POR_AVISO = 200


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
        # Serializa a varredura: uma analise ou um refresh por vez. A interface
        # cria uma thread por clique e nao cancela a anterior; sem isto uma
        # thread abandonada pode gravar por cima da correcao do refresh_folder
        # (perdendo o delta) ou antes dela (aplicando o delta duas vezes), e o
        # numero errado fica no banco. RLock, e nao Lock, porque refresh_folder
        # segura este lock e chama stats() dentro dele, e porque a recursao de
        # _varrer volta a pedi-lo na mesma thread.
        # Ordem dos locks: este e sempre o mais externo. Nada pede ele estando
        # com self._lock (cache em memoria) nem com o lock do storage, entao nao
        # ha como dois deles se cruzarem.
        self._lock_varredura = threading.RLock()

    def clear_cache(self) -> None:
        with self._lock:
            self._stats_cache.clear()

    def ultima_atualizacao_global(self) -> Optional[float]:
        return self._storage.ultima_atualizacao_global() if self._storage else None

    # ---------- estatisticas ----------
    def stats(self, path: str, usar_cache: bool = True) -> FolderStats:
        return self._medir(path, usar_cache)[0]

    def _do_cache(self, path: str) -> Optional[FolderStats]:
        """Le a pasta do cache em memoria ou do banco; None se nao estiver."""
        with self._lock:
            if path in self._stats_cache:
                return self._stats_cache[path]
        if self._storage is None:
            return None
        linha = self._storage.get_folder(path)
        if linha is None:
            return None
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

    def _medir(self, path: str, usar_cache: bool,
               cancelado=None, progresso=None) -> Tuple[FolderStats, bool]:
        """Mede a pasta e diz se a varredura foi interrompida no meio.

        O bool nao entra em FolderStats porque e detalhe da varredura, nao do
        dominio: serve para nao gravar um total truncado."""
        if usar_cache:
            pronto = self._do_cache(path)
            if pronto is not None:
                return pronto, False  # acerto de cache: nem pega o lock
        with self._lock_varredura:
            return self._varrer(path, usar_cache, cancelado, progresso)

    def _varrer(self, path: str, usar_cache: bool,
                cancelado=None, progresso=None) -> Tuple[FolderStats, bool]:
        """Mede a pasta lendo o disco. Precisa ser chamada com _lock_varredura."""
        total = arquivos = subpastas = 0
        maior_nome, maior_tam = "", 0
        maior_direto_nome, maior_direto_tam = "", 0
        diretos: List[CachedFile] = []
        listou = True        # False se o os.scandir da propria pasta falhou
        interrompida = False  # True se o cancelamento chegou aqui ou abaixo

        try:
            with os.scandir(path) as entries:
                for entry in entries:
                    if cancelado is not None and cancelado():
                        interrompida = True
                        break
                    try:
                        if entry.is_symlink() or caminho_ignorado(entry.path):
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            sub, sub_interrompida = self._medir(
                                entry.path, usar_cache, cancelado, progresso
                            )
                            interrompida = interrompida or sub_interrompida
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
            # Falha ao listar a pasta: ela conta como 0, como sempre contou,
            # mas esse 0 nao vai para o banco. A falha costuma ser passageira
            # (unidade removivel fora do ar, antivirus, ACL) e o os.stat ainda
            # funciona, entao o 0 gravado ficaria com modificado_em valido e o
            # is_folder_outdated nunca marcaria a linha: o 0 duraria 7 dias.
            listou = False

        agora = time.time()
        resultado = FolderStats(
            tamanho=total,
            arquivos=arquivos,
            subpastas=subpastas,
            maior_arquivo_nome=maior_nome,
            maior_arquivo_tam=maior_tam,
            cache_updated_at=agora,
        )
        if not interrompida:
            # total truncado nao entra nem no cache em memoria: a interface
            # mostraria o numero errado depois de um cancelamento
            with self._lock:
                self._stats_cache[path] = resultado
            if self._storage is not None and listou:
                self._gravar(path, resultado, diretos, maior_direto_nome,
                             maior_direto_tam, agora)
            if progresso is not None:
                progresso(path)
        return resultado, interrompida

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
        """Revarre so esta subarvore e corrige os ancestrais pela diferenca.

        Tudo sob _lock_varredura: ler o total antigo, apagar a subarvore,
        revarrer e somar o delta e uma sequencia que outra varredura no meio
        estragaria (ver o comentario do lock no __init__)."""
        with self._lock_varredura:
            return self._refresh_folder(path, progresso)

    def _refresh_folder(self, path: str, progresso=None) -> FolderStats:
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
        # Pasta que nao estava em cache conta como zero, nao como "sem correcao":
        # se algum ancestral esta em cache, _varrer ja gravou todos os descendentes
        # dele na epoca, logo uma pasta fora do cache abaixo dele e realmente nova.
        # Nesse caso o pai ganhou a propria pasta (1) mais toda a subarvore dela.
        # Se nenhum ancestral esta em cache, ancestrais() volta [] e nada muda.
        d_tam = novo.tamanho - (antigo.tamanho if antigo else 0)
        d_arq = novo.arquivos - (antigo.arquivos if antigo else 0)
        d_sub = novo.subpastas - (antigo.subpastas if antigo else 0) + (0 if antigo else 1)
        ancestrais_corrigidos = self._storage.aplicar_delta(path, d_tam, d_arq, d_sub)
        with self._lock:
            for ancestral in ancestrais_corrigidos:
                self._stats_cache.pop(ancestral, None)
        return novo

    def mapear_raizes(self, raizes: List[str], progresso=None, cancelado=None) -> int:
        """Varre as raizes inteiras, uma pasta de primeiro nivel por vez.

        Varredura completa e cara: so deve ser chamada por acao explicita do
        usuario, em thread separada, com progresso e cancelamento. O
        cancelamento desce ate dentro da recursao: uma pasta de primeiro nivel
        pode levar muitos minutos, e esperar o fim dela nao seria cancelar."""
        alvos = []
        for raiz in raizes:
            alvos.extend(os.path.join(raiz, nome) for nome in self.subfolders(raiz))
        total = len(alvos)
        feitos = 0
        medidas = [0]  # pastas medidas, so para espacar os avisos de progresso

        def passo(caminho):
            medidas[0] += 1
            if progresso and medidas[0] % PASTAS_POR_AVISO == 0:
                progresso(caminho, feitos, total)

        for alvo in alvos:
            if cancelado and cancelado():
                break
            _, interrompida = self._medir(alvo, False, cancelado, passo)
            if interrompida:  # cancelado no meio: nao conta como alvo concluido
                break
            feitos += 1
            if progresso:
                progresso(alvo, feitos, total)
        for raiz in raizes:
            if cancelado and cancelado():
                break
            # _varrer com usar_cache=True: le as entradas da raiz de novo, mas
            # reaproveita as subpastas ja medidas acima em vez de revarrer tudo.
            # Direto no _varrer, e nao no _medir, para nao parar num acerto de
            # cache da propria raiz e deixar o total dela velho.
            with self._lock_varredura:
                self._varrer(raiz, True, cancelado)
        return feitos

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


def raiz_de(path: str, raizes: List[str]) -> str:
    """Raiz mais especifica que contem o caminho; o proprio caminho se nenhuma contiver."""
    candidatas = [
        r for r in raizes
        if path == r or path.startswith(r.rstrip(os.sep) + os.sep)
    ]
    return max(candidatas, key=len) if candidatas else path
