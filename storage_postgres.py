"""Small DB-API compatibility layer for the repository's fixed parameterized SQL."""
class StorageError(RuntimeError):
    pass

class Result:
    def __init__(self,cursor,lastrowid=None):self.cursor=cursor;self.lastrowid=lastrowid
    @property
    def rowcount(self):return self.cursor.rowcount
    def fetchone(self):return self.cursor.fetchone()
    def fetchall(self):return self.cursor.fetchall()

class PostgresConnection:
    def __init__(self,url):self.url=url;self.connection=None
    def __enter__(self):
        import psycopg
        try:self.connection=psycopg.connect(self.url,connect_timeout=10)
        except psycopg.Error:raise StorageError('Externá PostgreSQL databáza nie je dostupná; overte secrets, TLS a sieť. Pri chybe sa neprepína na lokálny disk.') from None
        return self
    def __exit__(self,kind,error,tb):
        try:
            if kind:self.connection.rollback()
            else:self.connection.commit()
        finally:self.connection.close()
    def sql(self,sql):
        return sql.replace('?', '%s').replace('id INTEGER PRIMARY KEY','id BIGSERIAL PRIMARY KEY').replace('expires REAL','expires DOUBLE PRECISION').replace('lease REAL','lease DOUBLE PRECISION')
    def execute(self,sql,params=()):
        if sql=='BEGIN IMMEDIATE':return Result(self.connection.execute('SELECT pg_advisory_xact_lock(73104827)'))
        returning=sql.startswith('INSERT INTO campaigns(')
        import psycopg
        try:cursor=self.connection.execute(self.sql(sql)+(' RETURNING id' if returning else ''),params)
        except psycopg.Error:raise StorageError('Databázová operácia zlyhala; dáta sa nepresúvajú do lokálnej náhrady.') from None
        return Result(cursor,cursor.fetchone()[0] if returning else None)
    def executemany(self,sql,params):
        cursor=self.connection.cursor();cursor.executemany(self.sql(sql),params);return Result(cursor)
