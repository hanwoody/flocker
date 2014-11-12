# Copyright Hybrid Logic Ltd.  See LICENSE file for details.

"""
Tests for linking containers.
"""
from twisted.python.filepath import FilePath
from twisted.trial.unittest import TestCase

from flocker.node._docker import BASE_NAMESPACE, PortMap, Unit, Volume

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
    def test_linking(self):
        """
        Containers can be linked to using network ports.
        """
        elk_application = {
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

        getting_nodes = get_nodes(num_nodes=2)

        def deploy(node_ips):
            node_1, node_2 = node_ips
            elk_deployment = {
                u"version": 1,
                u"nodes": {
                    node_1: [ELASTICSEARCH_APPLICATION, LOGSTASH_APPLICATION,
                        KIBANA_APPLICATION],
                    node_2: [],
                },
            }

            # TODO pip install python-logstash
            # pip install elasticsearch
            # TODO try telnetlib
            flocker_deploy(self, elk_deployment, elk_application)
            from datetime import datetime
            from elasticsearch import Elasticsearch

            # by default we connect to localhost:9200

            es = Elasticsearch(hosts=[{"host": node_1, "port": ELASTICSEARCH_EXTERNAL_PORT}])
            from time import sleep
            # TODO Remove this sleep, it waits until ES is ready to be searched
            # and telnet doesn't give a connection refused
            sleep(30)
            nothing = es.search(doc_type=u'logs')
            # {u'hits': {u'hits': [], u'total': 0, u'max_score': 0.0}, u'_shards': {u'successful': 0, u'failed': 0, u'total': 0}, u'took': 3, u'timed_out': False}
            # assert that total is 0?
            import telnetlib

            tn = telnetlib.Telnet(host=node_1, port=LOGSTASH_EXTERNAL_PORT)
            tn.write(str({"firstname": "Joe", "lastname": "Bloggs"}) + "\n")
            tn.write(str({"firstname": "Fred", "lastname": "Bloggs"}) + "\n")
            tn.write("exit\n")
            something = es.search(doc_type=u'logs')
            # {u'hits': {u'hits': [{u'_score': 1.0, u'_type': u'logs', u'_id': u'QRTWmnsRSZWudCkoer4Dgg', u'_source': {u'host': u'172.16.255.1:52597', u'message': u"{'lastname': 'Bloggs', 'firstname': 'Fred'}", u'@version': u'1', u'@timestamp': u'2014-11-12T10:57:04.263Z'}, u'_index': u'logstash-2014.11.12'}, {u'_score': 1.0, u'_type': u'logs', u'_id': u'scrWmNelQsmBHM9YHF5bHw', u'_source': {u'host': u'172.16.255.1:52597', u'message': u"{'lastname': 'Bloggs', 'firstname': 'Joe'}", u'@version': u'1', u'@timestamp': u'2014-11-12T10:56:58.900Z'}, u'_index': u'logstash-2014.11.12'}], u'total': 2, u'max_score': 1.0}, u'_shards': {u'successful': 5, u'failed': 0, u'total': 5}, u'took': 83, u'timed_out': False}

            # d = assert_expected_deployment(self, {
            #     node_1: set([ELASTICSEARCH_UNIT, LOGSTASH_UNIT, KIBANA_UNIT]),
            #     node_2: set([]),
            # })
            #
            # return d
            # check that there is nothing in kibana
            # telnet to add some sample data to Logstash
            # check that there is some data in kibana
            # elk-deployment-moved.yml
            # flocker-deploy elk-deployment-moved.yml elk-application.yml
            # check that it is on the new host
            # check that there is some data in kibana

        getting_nodes.addCallback(deploy)
        return getting_nodes
