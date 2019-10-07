import argparse
import os
import yaml
import psycopg2
from codecs import open
import logging


def logger():
    """
    Setup basic logging for console.

    Usage:
        Initialize the logger by adding the code at the top of your script:
        ``logger = logger()``

    TODO: add log file export
    """
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(levelname)-8s %(message)s',
                        datefmt='%a, %d %b %Y %H:%M:%S')
    logger = logging.getLogger(__name__)
    return logger


logger = logger()


def psycopg_connection_string(docker_compose_path="docker-compose.yml"):
    """
    Postgres connection string for psycopg2.

    Args:
      full docker-compose path file

    Returns:
        Returns the psycopg required connection string: 'PG:host= port= user= dbname= password='
    """

    config = yaml.load(open(docker_compose_path), Loader=yaml.SafeLoader)
    env = config["services"]["importer"]["environment"]

    pg_config = 'host={} port={} user={} dbname={} password={}'.format(
            env['DATABASE_HOST'],
            os.getenv('DATABASE_PORT', env['DATABASE_PORT']),
            env['DATABASE_USER'],
            env['DATABASE_NAME'],
            env['DATABASE_PASSWORD']
        )
    # logger.info("pg_string obtained from {}".format(docker_compose_path))
    return pg_config


def execute_sql(docker_compose_path, sql, docker_port=0):
    """
    Execute a sql query with psycopg2.

    Args:
        1. pg_str: connection string using helper function psycopg_connection_string, returning:``host= port= user= dbname= password=``
        2. sql: SQL string in triple quotes::

            ```CREATE TABLE foo (bar text)```

    Returns:
        Executed sql with conn.cursor().execute(sql)
    """

    db_config = psycopg_connection_string(docker_compose_path)

    with psycopg2.connect(db_config) as conn:
        logger.info('connected to database')
        with conn.cursor() as cursor:
            logger.info('start exectuting sql query')
            with open(sql, 'r',  encoding='utf-8-sig') as sql_text:
                statements = sql_text.read().split(';')
                #print(statements)
                for statement in statements:
                    if statement != '':
                        logger.info("Executing: {}".format(statement))
                        cursor.execute(statement)
            conn.commit()


def parser():
    """Parser function to run arguments from the command line
    and to add description to sphinx."""

    parser = argparse.ArgumentParser(description="""
    Get multiple layers as a geojson file from a WFS service.
    command line example::

      python run_sql.py postcode_with_areas.sql ../docker-compose.yml

    """)  # noqa

    parser.add_argument(
        "-d", "--docker_postgres",
        type=str,
        default=None,
        help="Set the location of docker-compose path, for example ../docker-compose.yml")  # noqa
    parser.add_argument(
        "-s","--sql_query",
        type=str,
        help="sql query")
    return parser


def main():
    args = parser().parse_args()
    logger.info('Using %s', args)
    execute_sql(args.docker_postgres, args.sql_query)


if __name__ == '__main__':
    main()
