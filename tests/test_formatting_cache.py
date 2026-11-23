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
