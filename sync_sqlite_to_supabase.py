import os
import json
import sqlite3
from dotenv import load_dotenv
from supabase import create_client

def main():
    print("=== Sincronizador: SQLite -> Supabase ===")
    
    # Carrega as configurações do arquivo .env
    if not os.path.exists(".env"):
        print("Erro: Arquivo .env não encontrado.")
        return
        
    load_dotenv()
    
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    # Verifica se as chaves reais foram fornecidas
    if not supabase_url or not supabase_key or "your_supabase_project_url" in supabase_url or "your_supabase_service_role" in supabase_key:
        print("Erro: As chaves do Supabase em seu arquivo .env ainda não foram configuradas.")
        print("Por favor, preencha SUPABASE_URL e SUPABASE_KEY com suas credenciais do Supabase.")
        return
        
    sqlite_path = "jordan_belfort.db"
    if not os.path.exists(sqlite_path):
        print(f"Aviso: Banco de dados SQLite local '{sqlite_path}' não encontrado. Nada para migrar.")
        return
        
    print(f"Conectando ao Supabase em: {supabase_url}")
    try:
        supabase = create_client(supabase_url, supabase_key)
        print("Conexão com Supabase estabelecida.")
    except Exception as e:
        print(f"Erro ao conectar ao Supabase: {e}")
        return

    # Conecta ao SQLite
    print(f"Conectando ao SQLite local: {sqlite_path}")
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1. Configs
    print("\n--- Migrando Configurações ---")
    try:
        rows = cursor.execute("SELECT key, value FROM config").fetchall()
        print(f"Encontradas {len(rows)} configurações no SQLite.")
        for row in rows:
            key = row["key"]
            val_str = row["value"]
            try:
                value = json.loads(val_str)
            except Exception:
                value = val_str
            
            supabase.table("config").upsert({"key": key, "value": value}).execute()
            print(f" -> Config '{key}' sincronizada.")
        print("Configurações migradas com sucesso.")
    except Exception as e:
        print(f"Erro ao migrar configurações: {e}")

    # 2. Signals
    print("\n--- Migrando Sinais (Signals) ---")
    try:
        rows = cursor.execute("SELECT * FROM signals").fetchall()
        print(f"Encontrados {len(rows)} sinais no SQLite.")
        for row in rows:
            data = dict(row)
            # Converte campos de JSON do SQLite para objetos Python
            for field in ["technical_indicators", "market_structure", "social_sentiment", "on_chain_flow"]:
                if data.get(field):
                    try:
                        data[field] = json.loads(data[field])
                    except Exception:
                        pass
            # Remove campos gerados pelo banco de dados se necessário, mas aqui podemos incluir o ID original
            # para manter referências de chaves estrangeiras
            supabase.table("signals").upsert(data).execute()
        print(f"{len(rows)} sinais migrados com sucesso.")
    except Exception as e:
        print(f"Erro ao migrar sinais: {e}")

    # 3. Decisions
    print("\n--- Migrando Decisões (Decisions) ---")
    try:
        rows = cursor.execute("SELECT * FROM decisions").fetchall()
        print(f"Encontradas {len(rows)} decisões no SQLite.")
        for row in rows:
            data = dict(row)
            supabase.table("decisions").upsert(data).execute()
        print(f"{len(rows)} decisões migradas com sucesso.")
    except Exception as e:
        print(f"Erro ao migrar decisões: {e}")

    # 4. Trades
    print("\n--- Migrando Trades ---")
    try:
        rows = cursor.execute("SELECT * FROM trades").fetchall()
        print(f"Encontrados {len(rows)} trades no SQLite.")
        for row in rows:
            data = dict(row)
            supabase.table("trades").upsert(data).execute()
        print(f"{len(rows)} trades migrados com sucesso.")
    except Exception as e:
        print(f"Erro ao migrar trades: {e}")

    # 5. Audit Logs
    print("\n--- Migrando Histórico / Logs de Auditoria ---")
    try:
        rows = cursor.execute("SELECT * FROM audit_logs").fetchall()
        print(f"Encontrados {len(rows)} logs no SQLite.")
        for row in rows:
            data = dict(row)
            if data.get("details"):
                try:
                    data["details"] = json.loads(data["details"])
                except Exception:
                    pass
            supabase.table("audit_logs").upsert(data).execute()
        print(f"{len(rows)} logs migrados com sucesso.")
    except Exception as e:
        print(f"Erro ao migrar logs: {e}")

    conn.close()
    print("\nSincronização concluída!")

if __name__ == "__main__":
    main()
