import argparse
import pandas as pd
import yaml
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def parse_args():
    p = argparse.ArgumentParser(description="Load a CSV into a SQL table (create if missing).")
    p.add_argument("--conn_id", type=str, default='exiobase')
    p.add_argument("--connections_path", type=str, required=True)
    p.add_argument("--source_csv", type=str, required=True)
    p.add_argument("--table_name", type=str, required=True)
    p.add_argument("--schema", type=str, default="public")
    p.add_argument("--chunksize", type=int, default=5000)
    return p.parse_args()


def get_csv_data(path: str) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False)


def table_exists(engine: Engine, schema: str, table_name: str) -> bool:
    exists_sql = text("""
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = :schema
              AND table_name = :table
        );
    """)
    with engine.connect() as c:
        return bool(c.execute(exists_sql, {"schema": schema, "table": table_name}).scalar())


def create_table_from_df(engine: Engine, df: pd.DataFrame, table_name: str, schema: str):
    df.head(0).to_sql(table_name, engine, schema=schema, if_exists="fail", index=False)


def insert_sql(engine: Engine, df: pd.DataFrame, table_name: str, schema: str, chunksize: int):
    if not table_exists(engine, schema, table_name):
        create_table_from_df(engine, df, table_name, schema)

    df.to_sql(
        table_name,
        engine,
        schema=schema,
        if_exists="append",
        index=False,
        chunksize=chunksize,
        method="multi",
    )


def get_connection(conn_id, connections_path):
    with open(connections_path, "r") as f:
        cfg = yaml.safe_load(f)

    conn_cfg = cfg["connections"][conn_id]

    db_type = conn_cfg["type"]
    host = conn_cfg["host"]
    database = conn_cfg["database"]
    user = conn_cfg["user"]
    password = conn_cfg["password"]
    port = conn_cfg["port"]

    if db_type == "postgres":
        url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"
    elif db_type == "mssql":
        url = (
            f"mssql+pyodbc://{user}:{password}@{host}:{port}/{database}"
            "?driver=ODBC+Driver+18+for+SQL+Server"
        )
    else:
        raise ValueError("Unsupported database type")

    return create_engine(url)


def main():
    args = parse_args()

    engine = get_connection(args.conn_id, args.connections_path)
    df = get_csv_data(args.source_csv)

    insert_sql(
        engine,
        df,
        table_name=args.table_name,
        schema=args.schema,
        chunksize=args.chunksize
    )

    print(f"Loaded {len(df):,} rows into {args.schema}.{args.table_name}")


if __name__ == "__main__":
    main()
