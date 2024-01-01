# Copyright 2023 Ole Kliemann
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
import pytest
import tempfile
from mreventloop import emits, slot, forwards, connect, EventLoop, setEventLoop, has_event_loop, emits_bilaterally, Client, Server
import logging

logger = logging.getLogger(__name__)

@has_event_loop('event_loop')
@emits('events', [ 'product' ])
class ProducerPub:
  def __init__(self):
    self.counter = 0

  @slot
  def produceA(self):
    self.counter += 1
    logger.debug(f'producing: {self.counter}')
    self.events.product(str(self.counter))

  @slot
  def produceB(self, x, y):
    self.counter += (x + y)
    logger.debug(f'producing: {self.counter}')
    self.events.product(str(self.counter))

@has_event_loop('event_loop')
@emits_bilaterally('events', [ 'request_produce_a', 'request_produce_b' ])
class ConsumerSub:
  def __init__(self):
    self.content = []

  @slot
  def onProduct(self, product):
    self.content.append(product)

  @slot
  async def requestProduceA(self):
    await self.events.request_produce_a()

  @slot
  async def requestProduceB(self, x, y):
    await self.events.request_produce_b(x, y)

@pytest.mark.asyncio
async def test_client_server_pub_sub():
  with tempfile.NamedTemporaryFile(
      prefix = 'socket',
      suffix = '.ipc',
      delete = True
  ) as socket_file:
    producer = ProducerPub()
    consumer = ConsumerSub()
    client = Client(
      f'ipc://{socket_file.name}',
      [ 'produce_a', 'produce_b' ],
      [ 'product' ]
    )
    server = Server(
      f'ipc://{socket_file.name}',
      [ 'produce_a', 'produce_b' ],
      [ 'product' ]
    )

    connect(server, 'produce_a', producer, 'produceA')
    connect(server, 'produce_b', producer, 'produceB')
    connect(producer, 'product', server.publish, 'product')
    connect(consumer, 'request_produce_a', client.request, 'produce_a')
    connect(consumer, 'request_produce_b', client.request, 'produce_b')
    connect(client, 'product', consumer, 'onProduct')

    async with server, client, producer.event_loop, consumer.event_loop:
      coros = []
      coros.append(consumer.requestProduceA())
      coros.append(consumer.requestProduceA())
      coros.append(consumer.requestProduceA())
      coros.append(consumer.requestProduceB(0, 0))
      coros.append(consumer.requestProduceB(2, 1))
      coros.append(consumer.requestProduceA())
      await asyncio.gather(*coros)
      for i in range(0, 100):
        if len(consumer.content) == 6:
          break
        await asyncio.sleep(0.01)
      print('done')

    assert consumer.content == [ '1', '2', '3', '3', '6', '7' ]
