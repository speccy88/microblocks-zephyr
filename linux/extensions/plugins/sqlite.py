"""Parameterized, bounded SQLite operations in the isolated extension worker."""
# SPDX-License-Identifier: MIT
import math
import os
import re
import sqlite3
import stat
import time
from ..api import ExtensionError,arguments,bounded_json,text


class Extension:
    def __init__(self,settings,context):
        if set(settings)-{'database','max_rows','max_columns','max_cell_bytes','max_ms'}:raise ExtensionError('configuration','Unknown SQLite setting')
        name=settings.get('database','programs.sqlite3')
        if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\.sqlite3',name):raise ExtensionError('configuration','SQLite requires a simple configured database filename')
        self.path=context.state/name
        if self.path.exists() or self.path.is_symlink():
            s=self.path.lstat()
            if not stat.S_ISREG(s.st_mode) or s.st_uid!=os.geteuid() or s.st_nlink!=1 or s.st_mode&0o077:raise ExtensionError('configuration','SQLite database must be a private user-owned regular file')
        else:
            fd=os.open(self.path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600);os.close(fd)
        self.rows=settings.get('max_rows',32);self.columns=settings.get('max_columns',16);self.cell=settings.get('max_cell_bytes',1024);self.milliseconds=settings.get('max_ms',500)
        for value,high in [(self.rows,64),(self.columns,32),(self.cell,4096),(self.milliseconds,2000)]:
            if type(value) is not int or not 1<=value<=high:raise ExtensionError('configuration','SQLite result/deadline bounds are invalid')
        self.connection=sqlite3.connect(self.path,timeout=.1,isolation_level=None)
        self.connection.enable_load_extension(False)
        for category,value in [(sqlite3.SQLITE_LIMIT_LENGTH,65536),(sqlite3.SQLITE_LIMIT_SQL_LENGTH,4096),
            (sqlite3.SQLITE_LIMIT_COLUMN,self.columns),(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER,64),
            (sqlite3.SQLITE_LIMIT_ATTACHED,0),(sqlite3.SQLITE_LIMIT_EXPR_DEPTH,64),(sqlite3.SQLITE_LIMIT_COMPOUND_SELECT,16)]:
            self.connection.setlimit(category,value)
        self.own_transaction=False
        self.connection.set_authorizer(self.authorize)
        self.operations={'execute':self.execute,'query':self.execute}

    def authorize(self,action,arg1,arg2,db,source):
        denied={sqlite3.SQLITE_ATTACH,sqlite3.SQLITE_DETACH,sqlite3.SQLITE_PRAGMA}
        if action in denied or action in (sqlite3.SQLITE_TRANSACTION,sqlite3.SQLITE_SAVEPOINT) and not self.own_transaction:return sqlite3.SQLITE_DENY
        if action==sqlite3.SQLITE_FUNCTION and str(arg2).casefold() in ('load_extension','readfile','writefile'):return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    def transaction(self,operation):
        self.own_transaction=True
        try:operation()
        finally:self.own_transaction=False

    def execute(self,args):
        arguments(args,{'sql','parameters','limit'},{'sql'})
        sql=text(args['sql'],4096,'SQL')
        parameters=args.get('parameters',[])
        if not isinstance(parameters,(list,dict)) or len(parameters)>64:raise ExtensionError('arguments','SQL parameters must be a list or named object with at most 64 bindings')
        for value in parameters.values() if isinstance(parameters,dict) else parameters:
            if type(value) not in (str,int,float,bool,type(None)) or isinstance(value,float) and not math.isfinite(value):raise ExtensionError('arguments','SQL bindings must be finite scalars')
            if isinstance(value,str):text(value,2048,'SQL binding')
            if type(value) is int and not -(1<<63)<=value<(1<<63):raise ExtensionError('arguments','SQL integer binding is outside SQLite range')
        limit=args.get('limit',self.rows)
        if type(limit) is not int or not 1<=limit<=self.rows:raise ExtensionError('arguments','SQL row limit is outside the configured bound')
        deadline=time.monotonic()+self.milliseconds/1000
        self.connection.set_progress_handler(lambda:int(time.monotonic()>deadline),1000)
        before=self.connection.total_changes
        try:
            self.transaction(lambda:self.connection.execute('BEGIN'))
            cursor=self.connection.execute(sql,parameters)
            columns=[c[0] for c in cursor.description] if cursor.description else []
            if len(columns)>self.columns:raise ExtensionError('result_limit','SQL returned too many columns')
            rows=cursor.fetchmany(limit+1) if columns else []
            truncated=len(rows)>limit;rows=rows[:limit]
            for row in rows:
                for value in row:
                    if isinstance(value,(str,bytes)) and len(value.encode() if isinstance(value,str) else value)>self.cell:raise ExtensionError('result_limit','SQL cell exceeds its configured size')
                    if isinstance(value,bytes):raise ExtensionError('result_type','SQLite BLOB values require an explicit text/hex conversion in SQL')
            result={'columns':columns,'rows':rows,'truncated':truncated,'changes':self.connection.total_changes-before,'last_row_id':cursor.lastrowid}
            bounded_json({'ok':True,'value':result}) # failure rolls back before committing
            self.transaction(self.connection.commit)
            return result
        except (sqlite3.Error,ExtensionError) as error:
            self.transaction(self.connection.rollback)
            if isinstance(error,ExtensionError):raise
            raise ExtensionError('sql_error','SQLite rejected the statement: '+str(error)[:240]) from None
        finally:self.connection.set_progress_handler(None,0)

    def close(self):self.connection.close()
