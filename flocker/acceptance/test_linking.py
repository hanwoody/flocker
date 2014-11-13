# Copyright Hybrid Logic Ltd.  See LICENSE file for details.

"""
Tests for linking containers.
"""
from telnetlib import Telnet
from time import sleep

# TODO add this to setup.py, do the whole @require Elasticsearch
from elasticsearch import Elasticsearch

from twisted.python.filepath import FilePath
from twisted.trial.unittest import TestCase

from flocker.node._docker import BASE_NAMESPACE, PortMap, Unit, Volume
from flocker.testtools import loop_until

from .testtools import (assert_expected_deployment, flocker_deploy, get_nodes,
                        require_flocker_cli)

ELASTICSEARCH_INTERNAL_PORT = 9200
ELASTICSEARCH_EXTERNAL_PORT = 9200

ELASTICSEARCH_APPLICATION = u"elasticsearch"
ELASTICSEARCH_IMAGE = u"clusterhq/elasticsearch"
ELASTICSEARCH_VOLUME_MOUNTPOINT = u'/var/lib/elasticsearch'

ELASTICSEARCH_UNIT = Unit(
    name=ELASTICSEARCH_APPLICATION,
    container_name=BASE_NAMESPACE + ELASTICSEARCH_APPLICATION,
    activation_state=u'active',
    container_image=ELASTICSEARCH_IMAGE + u':latest',
    ports=frozenset([
        PortMap(internal_port=ELASTICSEARCH_INTERNAL_PORT,
                external_port=ELASTICSEARCH_EXTERNAL_PORT),
        ]),
    volumes=frozenset([
        Volume(node_path=FilePath(b'/tmp'),
               container_path=FilePath(ELASTICSEARCH_VOLUME_MOUNTPOINT)),
        ]),
)

LOGSTASH_INTERNAL_PORT = 5000
LOGSTASH_EXTERNAL_PORT = 5000

LOGSTASH_LOCAL_PORT = 9200
LOGSTASH_REMOTE_PORT = 9200

LOGSTASH_APPLICATION = u"logstash"
LOGSTASH_IMAGE = u"clusterhq/logstash"

LOGSTASH_UNIT = Unit(
    name=LOGSTASH_APPLICATION,
    container_name=BASE_NAMESPACE + LOGSTASH_APPLICATION,
    activation_state=u'active',
    container_image=LOGSTASH_IMAGE + u':latest',
    ports=frozenset([
        PortMap(internal_port=LOGSTASH_INTERNAL_PORT,
                external_port=LOGSTASH_INTERNAL_PORT),
        ]),
    volumes=frozenset([]),
)

KIBANA_INTERNAL_PORT = 8080
KIBANA_EXTERNAL_PORT = 80

KIBANA_APPLICATION = u"kibana"
KIBANA_IMAGE = u"clusterhq/kibana"

KIBANA_UNIT = Unit(
    name=KIBANA_APPLICATION,
    container_name=BASE_NAMESPACE + KIBANA_APPLICATION,
    activation_state=u'active',
    container_image=KIBANA_IMAGE + u':latest',
    ports=frozenset([
        PortMap(internal_port=KIBANA_INTERNAL_PORT,
                external_port=KIBANA_EXTERNAL_PORT),
        ]),
    volumes=frozenset([]),
)


class LinkingTests(TestCase):
    """
    Tests for linking containers.

    Similar to:
    http://doc-dev.clusterhq.com/gettingstarted/examples/linking.html

    # TODO Link to this file from linking.rst

    # TODO proper docstring
    # This has the flaw of not actually testing Kibana. It does connect the
    # linking feature - between elasticsearch and logstash, and the kibana
    # thing needs to be set up right (this test verifies that it is running)
    """
    @require_flocker_cli
    def setUp(self):
        """
        TODO
        """
        getting_nodes = get_nodes(num_nodes=2)

        def deploy_elk(node_ips):
            self.node_1, self.node_2 = node_ips

            elk_deployment = {
                u"version": 1,
                u"nodes": {
                    self.node_1: [
                        ELASTICSEARCH_APPLICATION, LOGSTASH_APPLICATION,
                        KIBANA_APPLICATION,
                    ],
                    self.node_2: [],
                },
            }

            self.elk_application = {
                u"version": 1,
                u"applications": {
                    ELASTICSEARCH_APPLICATION: {
                        u"image": ELASTICSEARCH_IMAGE,
                        u"ports": [{
                            u"internal": ELASTICSEARCH_INTERNAL_PORT,
                            u"external": ELASTICSEARCH_EXTERNAL_PORT,
                        }],
                        u"volume": {
                            u"mountpoint": ELASTICSEARCH_VOLUME_MOUNTPOINT,
                        },
                    },
                    LOGSTASH_APPLICATION: {
                        u"image": LOGSTASH_IMAGE,
                        u"ports": [{
                            u"internal": LOGSTASH_INTERNAL_PORT,
                            u"external": LOGSTASH_EXTERNAL_PORT,
                        }],
                        u"links": [{
                            u"local_port": LOGSTASH_LOCAL_PORT,
                            u"remote_port": LOGSTASH_REMOTE_PORT,
                            u"alias": u"es",
                        }],
                    },
                    KIBANA_APPLICATION: {
                        u"image": KIBANA_IMAGE,
                        u"ports": [{
                            u"internal": KIBANA_INTERNAL_PORT,
                            u"external": KIBANA_EXTERNAL_PORT,
                        }],
                    },
                },
            }

            flocker_deploy(self, elk_deployment, self.elk_application)

        deploying_elk = getting_nodes.addCallback(deploy_elk)

        # TODO move these waits to into the test
        def wait_for_es(ignored):
            # TODO use neater lambda like below (separate out?)
            es = Elasticsearch(
                hosts=[{"host": self.node_1,
                        "port": ELASTICSEARCH_EXTERNAL_PORT}], max_retries=20)
            waiting_for_ping = loop_until(lambda: es.ping())
            return waiting_for_ping

        waiting_for_es = deploying_elk.addCallback(wait_for_es)

        def wait_for_logstash(ignored):
            from socket import error
            def get_telnet():
                try:
                    Telnet(host=self.node_1, port=LOGSTASH_EXTERNAL_PORT)
                    return True
                except error:
                    return False
            waiting_for_telnet = loop_until(get_telnet)
            return waiting_for_telnet

        waiting_for_es.addCallback(wait_for_logstash)
        return waiting_for_es

    def test_deploy(self):
        """
        # TODO
        """
        d = assert_expected_deployment(self, {
            self.node_1: set([ELASTICSEARCH_UNIT, LOGSTASH_UNIT, KIBANA_UNIT]),
            self.node_2: set([]),
        })

        return d

    def test_linking(self):
        """
        Containers can be linked to using network ports.
        """
        def get_log_messages(es):
            """
            Takes elasticsearch instance, returns log messages.
            """
            search_results = es.search()
            return set([hit[u'_source'][u'message'] for hit in
                search_results[u'hits'][u'hits']])

        es = Elasticsearch(hosts=[{"host": self.node_1,
            "port": ELASTICSEARCH_EXTERNAL_PORT}], max_retries=20)

        self.assertEqual(set([]), get_log_messages(es))

        # Read until "Connected to 172.16.255.241"?
        telnet = Telnet(host=self.node_1, port=LOGSTASH_EXTERNAL_PORT)
        messages = set([
            str({"firstname": "Joe", "lastname": "Bloggs"}),
            str({"firstname": "Fred", "lastname": "Bloggs"}),
        ])
        for message in messages:
            telnet.write(message + "\n")
        # TODO quit the telnet connection?
        # TODO force elasticsearch index? else wait in loop
        # until what?
        sleep(20)

        self.assertEqual(messages, get_log_messages(es))

        elk_deployment_moved = {
            u"version": 1,
            u"nodes": {
                self.node_1: [LOGSTASH_APPLICATION, KIBANA_APPLICATION],
                self.node_2: [ELASTICSEARCH_APPLICATION],
            },
        }

        flocker_deploy(self, elk_deployment_moved, self.elk_application)

        es_node_2 = Elasticsearch(hosts=[{"host": self.node_2,
            "port": ELASTICSEARCH_EXTERNAL_PORT}], max_retries=20)

        asserting_es_moved = assert_expected_deployment(self, {
            self.node_1: set([LOGSTASH_UNIT, KIBANA_UNIT]),
            self.node_2: set([ELASTICSEARCH_UNIT]),
        })

        es_node_2 = Elasticsearch(
            hosts=[{"host": self.node_2,
                    "port": ELASTICSEARCH_EXTERNAL_PORT}], max_retries=20)

        waiting_for_es = asserting_es_moved.addCallback(
            lambda _: loop_until(lambda: es_node_2.ping())
        )
        return waiting_for_es
        # waiting_for_es.addCallback(
        #     lambda _: self.assertEqual(messages, get_log_messages(es_node_2)))
        # return asserting_es_moved
