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

class PostgresTests(TestCase):
    """
    Tests for running and managing PostgreSQL with Flocker.

    Similar to:
    http://doc-dev.clusterhq.com/gettingstarted/examples/postgres.html

    # TODO Link to this file from postgres.rst
    """
    @require_flocker_cli
    def test_postgres(self):
        """
        PostgreSQL and its data can be deployed and moved with FLocker.
        """
        getting_nodes = get_nodes(num_nodes=2)

        def deploy(node_ips):
            node_1, node_2 = node_ips

            postgres_deployment = {
                u"version": 1,
                u"nodes": {
                    node_1: [u"postgres-volume-example"],
                    node_2: [],
                },
            }

            internal_port = 5432
            external_port = 5432

            postgres_application = {
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

            flocker_deploy(self, postgres_deployment, postgres_application)

            ports = frozenset([
                PortMap(internal_port=internal_port,
                        external_port=external_port)
            ])

            volumes = frozenset([
                Volume(node_path=FilePath(b'/tmp'),
                       container_path=FilePath(u'/var/lib/postgresql/data')),
            ])

            unit = Unit(
                name=u"postgres-volume-example",
                container_name=BASE_NAMESPACE + u"postgres-volume-example",
                activation_state=u'active',
                container_image=u"postgres" + u':latest',
                ports=ports,
                volumes=volumes,
            )
            # psql postgres --host 172.16.255.250 --port 5432 --username postgres
            conn = psycopg2.connect("host=172.16.255.250 user=postgres port=5432")
            cur = conn.cursor()
            cur.execute("CREATE DATABASE flockertest;")
            import pdb; pdb.set_trace()
            # TODO put these in cleanup

            cur.close()
            conn.close()

            d = assert_expected_deployment(self, {
                node_1: set([unit]),
                node_2: set([]),
            })

            return d

        getting_nodes.addCallback(deploy)
        return getting_nodes
