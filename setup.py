#!/usr/bin/env python3
import os
from pathlib import Path

def create_data_dir():
    """Cria diretório de dados se não existir"""
    base_dir = Path(".") / "data"
    
    if not base_dir.exists():
        base_dir.mkdir(parents=True, exist_ok=True)
        print(f"✅ Diretório criado: {base_dir}")
    
    # Verificar permissões
    try:
        test_file = base_dir / "test.txt"
        test_file.write_text("test")
        test_file.unlink()
        print("✅ Permissões de escrita OK")
    except Exception as e:
        print(f"❌ Erro de permissão: {e}")
        # Tentar criar em diretório alternativo
        alt_dir = Path("/tmp") / "financeiro_data"
        if not alt_dir.exists():
            alt_dir.mkdir(parents=True, exist_ok=True)
        print(f"✅ Usando diretório alternativo: {alt_dir}")

if __name__ == "__main__":
    create_data_dir()