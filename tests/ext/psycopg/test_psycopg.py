import psycopg
import psycopg.sql
import psycopg_pool

import pytest
import testing.postgresql

from aws_xray_sdk.core import patch
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core.context import Context

patch(('psycopg',))


@pytest.fixture(autouse=True)
def construct_ctx():
    """
    Clean up context storage on each test run and begin a segment
    so that later subsegment can be attached. After each test run
    it cleans up context storage again.
    """
    xray_recorder.configure(service='test', sampling=False, context=Context())
    xray_recorder.clear_trace_entities()
    xray_recorder.begin_segment('name')
    yield
    xray_recorder.clear_trace_entities()


def test_execute_dsn_kwargs():
    q = 'SELECT 1'
    with testing.postgresql.Postgresql() as postgresql:
        url = postgresql.url()
        dsn = postgresql.dsn()
        conn = psycopg.connect(dbname=dsn['database'],
                                user=dsn['user'],
                                password='',
                                host=dsn['host'],
                                port=dsn['port'])
        cur = conn.cursor()
        cur.execute(q)

    subsegment = xray_recorder.current_segment().subsegments[0]
    assert subsegment.name == 'execute'
    sql = subsegment.sql
    assert sql['database_type'] == 'PostgreSQL'
    assert sql['user'] == dsn['user']
    assert sql['url'] == url
    assert sql['database_version']


def test_execute_dsn_string():
    q = 'SELECT 1'
    with testing.postgresql.Postgresql() as postgresql:
        url = postgresql.url()
        dsn = postgresql.dsn()
        conn = psycopg.connect('dbname=' + dsn['database'] +
                                ' password=mypassword' +
                                ' host=' + dsn['host'] +
                                ' port=' + str(dsn['port']) +
                                ' user=' + dsn['user'])
        cur = conn.cursor()
        cur.execute(q)

    subsegment = xray_recorder.current_segment().subsegments[0]
    assert subsegment.name == 'execute'
    sql = subsegment.sql
    assert sql['database_type'] == 'PostgreSQL'
    assert sql['user'] == dsn['user']
    assert sql['url'] == url
    assert sql['database_version']


def test_execute_in_pool():
    q = 'SELECT 1'
    with testing.postgresql.Postgresql() as postgresql:
        url = postgresql.url()
        dsn = postgresql.dsn()
        pool = psycopg_pool.ConnectionPool('dbname=' + dsn['database'] +
                                            ' password=mypassword' +
                                            ' host=' + dsn['host'] +
                                            ' port=' + str(dsn['port']) +
                                            ' user=' + dsn['user'],
                                            min_size=1,
                                            max_size=1)
        with pool.connection() as conn:
            cur = conn.cursor()
            cur.execute(q)

    subsegment = xray_recorder.current_segment().subsegments[0]
    assert subsegment.name == 'execute'
    sql = subsegment.sql
    assert sql['database_type'] == 'PostgreSQL'
    assert sql['user'] == dsn['user']
    assert sql['url'] == url
    assert sql['database_version']


def test_execute_bad_query():
    q = 'SELECT blarg'
    with testing.postgresql.Postgresql() as postgresql:
        url = postgresql.url()
        dsn = postgresql.dsn()
        conn = psycopg.connect(dbname=dsn['database'],
                                user=dsn['user'],
                                password='',
                                host=dsn['host'],
                                port=dsn['port'])
        cur = conn.cursor()
        try:
            cur.execute(q)
        except Exception:
            pass

    subsegment = xray_recorder.current_segment().subsegments[0]
    assert subsegment.name == 'execute'
    sql = subsegment.sql
    assert sql['database_type'] == 'PostgreSQL'
    assert sql['user'] == dsn['user']
    assert sql['url'] == url
    assert sql['database_version']

    exception = subsegment.cause['exceptions'][0]
    assert exception.type == 'UndefinedColumn'

def test_query_as_string():
    with testing.postgresql.Postgresql() as postgresql:
        url = postgresql.url()
        dsn = postgresql.dsn()
        conn = psycopg.connect('dbname=' + dsn['database'] +
                                ' password=mypassword' +
                                ' host=' + dsn['host'] +
                                ' port=' + str(dsn['port']) +
                                ' user=' + dsn['user'])
        test_sql = psycopg.sql.Identifier('test')
        assert test_sql.as_string(conn)
        assert test_sql.as_string(conn.cursor())
