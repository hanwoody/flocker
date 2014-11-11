# Copyright Hybrid Logic Ltd.  See LICENSE file for details.

"""
Tests for running and managing PostgreSQL with Flocker.
"""
from twisted.python.filepath import FilePath
from twisted.trial.unittest import TestCase

from flocker.node._docker import BASE_NAMESPACE, PortMap, Unit, Volume

from .testtools import (assert_expected_deployment, flocker_deploy, get_nodes,
                        require_flocker_cli)

# TODO add to setup.py
# TODO require_posgres etc like mongo
# I had to do brew install postgresql first
# add to the licensing google doc
from psycopg2 import connect

POSTGRES_INTERNAL_PORT = 5432
POSTGRES_EXTERNAL_PORT = 5432

POSTGRES_APPLICATION = u"postgres-volume-example"
POSTGRES_IMAGE = u"postgres"
POSTGRES_VOLUME_MOUNTPOINT = u'/var/lib/postgresql/data'

POSTGRES_UNIT = Unit(
    name=POSTGRES_APPLICATION,
    container_name=BASE_NAMESPACE + POSTGRES_APPLICATION,
    activation_state=u'active',
    container_image=POSTGRES_IMAGE + u':latest',
    ports=frozenset([
        PortMap(internal_port=POSTGRES_INTERNAL_PORT,
                external_port=POSTGRES_EXTERNAL_PORT),
        ]),
    volumes=frozenset([
        Volume(node_path=FilePath(b'/tmp'),
               container_path=FilePath(POSTGRES_VOLUME_MOUNTPOINT)),
        ]),
)


class PostgresTests(TestCase):
    """
    Tests for running and managing PostgreSQL with Flocker.

    Similar to:
    http://doc-dev.clusterhq.com/gettingstarted/examples/postgres.html
    """
    @require_flocker_cli
    def setUp(self):
        """
        Deploy PostgreSQL to a node.
        """
        getting_nodes = get_nodes(num_nodes=2)

        def deploy_postgres(node_ips):
            self.node_1, self.node_2 = node_ips

            postgres_deployment = {
                u"version": 1,
                u"nodes": {
                    self.node_1: [POSTGRES_APPLICATION],
                    self.node_2: [],
                },
            }

            self.postgres_application = {
                u"version": 1,
                u"applications": {
                    POSTGRES_APPLICATION: {
                        u"image": POSTGRES_IMAGE,
                        u"ports": [{
                            u"internal": POSTGRES_INTERNAL_PORT,
                            u"external": POSTGRES_EXTERNAL_PORT,
                    }],
                    "volume": {
                        # The location within the container where the data
                        # volume will be mounted; see:
                        # https://github.com/docker-library/postgres/blob/
                        # docker/Dockerfile.template
                        "mountpoint": POSTGRES_VOLUME_MOUNTPOINT,
                      },
                    },
                },
            }

            flocker_deploy(self, postgres_deployment,
                           self.postgres_application)

        getting_nodes.addCallback(deploy_postgres)
        return getting_nodes

    def test_deploy(self):
        """
        Verify that Docker reports that PostgreSQL is running on one node and
        not another.
        """
        d = assert_expected_deployment(self, {
            self.node_1: set([POSTGRES_UNIT]),
            self.node_2: set([]),
        })

        return d

    def _get_postgres_client(self, host, user, port, database=None):
        """
        Returns a ``Deferred`` which fires with a ``MongoClient`` when one has been
        created.

        See http://api.mongodb.org/python/current/api/pymongo/mongo_client.html#
            pymongo.mongo_client.MongoClient
        for more parameter information.

        :param bytes host: Hostname or IP address of the instance to connect to.
        :param int port: Port number on which to connect.

        The tutorial says "If you get a connection refused error try again after a
        few seconds; the application might take some time to fully start up."
        and so here we wait until the client can be created.

        # TODO document this properly
        # TODO use **kwargs?
        """
        from flocker.testtools import loop_until
        def create_mongo_client():
            from psycopg2 import OperationalError
            try:
                if database is None:
                    return connect(host=host, user=user, port=port)
                else:
                    return connect(host=host, user=user, port=port,
                        database=database)
            except OperationalError:
                return False

        d = loop_until(create_mongo_client)
        return d

    def test_postgres(self):
        """
        PostgreSQL and its data can be deployed and moved with Flocker. In
        particular, if PostgreSQL is deployed to a node, and data added to it,
        and then the application is moved to another node, the data remains
        available.
        """
        # SQL injection is not a real concern here, and it seems impossible
        # to pass some these variables via psycopg2 so string concatenation
        # is used.
        database = b'flockertest'
        table = b'testtable'
        user = b'postgres'
        column = b'testcolumn'
        data = 3

        connecting_to_application = self._get_postgres_client(host=self.node_1,
            user=user, port=POSTGRES_EXTERNAL_PORT)

        def create_database(connection_to_application):
            connection_to_application.autocommit = True
            with connection_to_application.cursor() as application_cursor:
                application_cursor.execute("CREATE DATABASE " + database + ";")

        connecting_to_application.addCallback(create_database)

        getting_database = connecting_to_application.addCallback(
            lambda _: self._get_postgres_client(host=self.node_1, user=user,
                port=POSTGRES_EXTERNAL_PORT, database=database)
        )

        def insert_data(connection_to_db):
            with connection_to_db as db_connection_node_1:
                with db_connection_node_1.cursor() as db_node_1_cursor:
                    db_node_1_cursor.execute("CREATE TABLE " + table + " (" +
                        column + " int);")
                    db_node_1_cursor.execute("INSERT INTO " + table + " (" +
                        column + ") VALUES (%(data)s);", {'data': data})
                    db_node_1_cursor.execute("SELECT * FROM " + table + ";")
                    db_connection_node_1.commit()
                    self.assertEqual(db_node_1_cursor.fetchone()[0], data)

        inserting_data = getting_database.addCallback(insert_data)

        def move_postgres(ignored):
            postgres_deployment_moved = {
                u"version": 1,
                u"nodes": {
                    self.node_1: [],
                    self.node_2: [POSTGRES_APPLICATION],
                },
            }

            flocker_deploy(self, postgres_deployment_moved,
                           self.postgres_application)

            verifying_deployment = assert_expected_deployment(self, {
                self.node_1: set([]),
                self.node_2: set([POSTGRES_UNIT]),
            })

            return verifying_deployment

        moving_postgres = inserting_data.addCallback(move_postgres)

        getting_database_node_2 = moving_postgres.addCallback(
            lambda _: self._get_postgres_client(host=self.node_2, user=user,
                port=POSTGRES_EXTERNAL_PORT, database=database)
        )

        def verify_data_moves(connection_to_db):
            with connection_to_db as db_connection_node_2:
                with db_connection_node_2.cursor() as db_node_2_cursor:
                    db_node_2_cursor.execute("SELECT * FROM " + table + ";")
                    self.assertEqual(db_node_2_cursor.fetchone()[0], data)

        verifying_data_moves = getting_database_node_2.addCallback(
            verify_data_moves)
        return verifying_data_moves
