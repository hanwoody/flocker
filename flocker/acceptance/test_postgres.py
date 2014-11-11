# Copyright Hybrid Logic Ltd.  See LICENSE file for details.

"""
Tests for running and managing PostgreSQL with Flocker.
"""
from twisted.python.filepath import FilePath
from twisted.trial.unittest import TestCase

from flocker.node._docker import BASE_NAMESPACE, PortMap, Unit, Volume

from .testtools import (assert_expected_deployment, flocker_deploy, get_nodes,
                        require_flocker_cli)

# TODO relative imports and add to setup.py and require_posgres etc like mongo
# I had to do brew install postgresql first
# add to the licensing google doc
import psycopg2

internal_port = 5432
external_port = 5432

POSTGRES_UNIT = Unit(
    name=u"postgres-volume-example",
    container_name=BASE_NAMESPACE + u"postgres-volume-example",
    activation_state=u'active',
    container_image=u"postgres" + u':latest',
    ports=frozenset([
        PortMap(internal_port=internal_port,
                external_port=external_port)
        ]),
    volumes=frozenset([
        Volume(node_path=FilePath(b'/tmp'),
           container_path=FilePath(u'/var/lib/postgresql/data')),
        ]),
)

class PostgresTests(TestCase):
    """
    Tests for running and managing PostgreSQL with Flocker.

    Similar to:
    http://doc-dev.clusterhq.com/gettingstarted/examples/postgres.html

    # TODO Link to this file from postgres.rst
    """
    @require_flocker_cli
    def setUp(self):
        getting_nodes = get_nodes(num_nodes=2)

        def deploy(node_ips):
            self.node_1, self.node_2 = node_ips

            postgres_deployment = {
                u"version": 1,
                u"nodes": {
                    self.node_1: [u"postgres-volume-example"],
                    self.node_2: [],
                },
            }

            self.postgres_application = {
                u"version": 1,
                u"applications": {
                  u"postgres-volume-example": {
                    u"image": u"postgres",
                    u"ports": [{
                        u"internal": internal_port,
                        u"external": external_port,
                    }],
                    "volume": {
                      # The location within the container where the data
                      # volume will be mounted; see:
                      # https://github.com/docker-library/postgres/blob/docker/
                      # Dockerfile.template
                      "mountpoint": "/var/lib/postgresql/data",
                      },
                    },
                },
            }

            flocker_deploy(self, postgres_deployment, self.postgres_application)

        getting_nodes.addCallback(deploy)
        return getting_nodes

    def test_deploy(self):
        # TODO docstrings
        d = assert_expected_deployment(self, {
            self.node_1: set([POSTGRES_UNIT]),
            self.node_2: set([]),
        })

        return d

    def test_postgres(self):
        """
        PostgreSQL and its data can be deployed and moved with FLocker.
        """

            # psql postgres --host 172.16.255.250 --port 5432 --username postgres
        from time import sleep
        # TODO get rid of this sleep
        sleep(5)

        # TODO bytes or unicode (for this and filepaths?)
        conn = psycopg2.connect(host=self.node_1, user=u'postgres', port=external_port)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("CREATE DATABASE flockertest;")
        cur.close()
        conn.close()


        conn = psycopg2.connect(host=self.node_1, user=u'postgres', port=external_port, database='flockertest')
        cur = conn.cursor()
        # TODO use named arguments
        cur.execute("CREATE TABLE testtable (testcolumn int);")
        cur.execute("INSERT INTO testtable (testcolumn) VALUES (3);")
        cur.execute("SELECT * FROM testtable;")
        conn.commit()
        self.assertEqual(cur.fetchone(), (3,))

        cur.close()
        conn.close()

        postgres_deployment_moved = {
            u"version": 1,
            u"nodes": {
                self.node_1: [],
                self.node_2: [u"postgres-volume-example"],
            },
        }

        flocker_deploy(self, postgres_deployment_moved, self.postgres_application)
        # TODO call this conn_2 or similar
        # TODO get rid of this sleep
        sleep(5)
        conn = psycopg2.connect(host=self.node_2, user=u'postgres', port=external_port, database='flockertest')
        cur = conn.cursor()
        cur.execute("SELECT * FROM testtable;")
        # conn.commit()
        self.assertEqual(cur.fetchone(), (3,))
        cur.close()
        conn.close()
