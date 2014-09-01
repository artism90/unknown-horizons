# ###################################################
# Copyright (C) 2008-2014 The Unknown Horizons Team
# team@unknown-horizons.org
# This file is part of Unknown Horizons.

# Unknown Horizons is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the
# Free Software Foundation, Inc.,
# 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
# ###################################################

import logging
from collections import defaultdict, deque

from horizons.util.python.singleton import Singleton

class MessageBus(object):
	"""The MessageBus class is used to send Message instances from a sender to
	one or multiple recipients."""
	__metaclass__ = Singleton

	log = logging.getLogger("messaging.messagebus")

	def __init__(self):
		# Register {MessageType: [list of receiver callbacks]}
		self.global_receivers = defaultdict(list)
		# Register for messages from a specific object
		# {(MessageType, instance): [list of receiver callbacks]}
		self.local_receivers = defaultdict(list)

	def subscribe_globally(self, messagetype, callback):
		"""Register for a certain message type.
		@param callback: Callback methode, needs to take 1 parameter: the message"""
		self.global_receivers[messagetype].append(callback)

	def subscribe_locally(self, messagetype, instance, callback):
		"""Register for a certain message type from a specific instance.
		@param callback: Callback methode, needs to take 1 parameter: the message"""
		pair = (messagetype, instance)
		self.local_receivers[pair].append(callback)

	def unsubscribe_globally(self, messagetype, callback):
		assert callback in self.global_receivers[messagetype]
		self.global_receivers[messagetype].remove(callback)

	def unsubscribe_locally(self, messagetype, instance, callback):
		pair = (messagetype, instance)
		assert callback in self.local_receivers[pair]
		self.local_receivers[pair].remove(callback)

	def discard_globally(self, messagetype, callback):
		if callback in self.global_receivers[messagetype]:
			self.unsubscribe_globally(messagetype, callback)

	def discard_locally(self, messagetype, instance, callback):
		pair = (messagetype, instance)
		if pair in self.local_receivers and callback in self.local_receivers[pair]:
			self.unsubscribe_locally(messagetype, instance, callback)

	def broadcast(self, message):
		"""Send a message to the bus and broadcast it to all recipients"""
		messagetype = message.__class__
		for callback in self.global_receivers[messagetype]:
			# Execute the callback
			callback(message)

		pair = (messagetype, message.sender)
		for callback in self.local_receivers[pair]:
			# Execute the callback
			callback(message)

	def reset(self):
		"""Reset to initial state. Drops all subscriptions"""
		# there shouldn't be anything left now, warn if there is
		for messagetype, cb_list in self.global_receivers.iteritems():
			if cb_list:
				self.log.debug("MessageBus: leftover global receivers {cb} for {messagetype}".format(cb=[str(i) for i in cb_list], messagetype=messagetype))
		for messagetype, cb_list in self.local_receivers.iteritems():
			if cb_list:
				self.log.debug("MessageBus: leftover local receivers {cb} for {messagetype}".format(cb=[str(i) for i in cb_list], messagetype=messagetype))

		# suicide, next instance will be created on demand
		self.__class__.destroy_instance()


class QueuingMessageBus(MessageBus):
	"""The QueuingMessageBus class is used to send Message instances from a sender to
	one or multiple recipients, with the additional property that messages will
	be saved to a queue if no callback is subscribed at the time they are sent."""
	
	def __init__(self):
		MessageBus.__init__(self)
		# Queue up messages if there is no registered subscriber
		self.message_queue = defaultdict(deque)
	
	def subscribe_globally(self, messagetype, callback):
		MessageBus.subscribe_globally(self, messagetype, callback)
		
		while len(self.message_queue[messagetype]):
			self.broadcast(self.message_queue[messagetype].popleft())

	def subscribe_locally(self, messagetype, instance, callback):
		MessageBus.subscribe_locally(self, messagetype, instance, callback)
		
		for message in self.message_queue[messagetype]:
			if (message, message.sender) == (messagetype, instance):
				self.broadcast(message)
				self.message_queue[messagetype].remove(message)

	def broadcast(self, message):
		messagetype = message.__class__
		pair = (messagetype, message.sender)
		
		# check if the message will go anywhere, if not, then queue it
		if not len(self.global_receivers[messagetype]) and not len(self.local_receivers[pair]):
			self.message_queue[messagetype].append(message)
		else:
			MessageBus.broadcast(self, message)

	def clear(self, messagetype):
		self.message_queue[messagetype].clear()

	def queue_len(self, messagetype):
		return len(self.message_queue[messagetype])


class SimpleMessageBus(object):
	"""Manages registration and calling of callbacks when events (strings) occur.

	Example:

		bus = SimpleMessageBus(('foo', 'bar'))
		bus.subscribe('foo', cb)

		bus.broadcast('foo')  # cb will be called
	"""

	def __init__(self, message_types):
		self._message_types = message_types
		self._callbacks = defaultdict(list)

	def subscribe(self, type, callback):
		if type not in self._message_types:
			raise TypeError("Unsupported type")
		if callback in self._callbacks[type]:
			raise Exception("Callback %s already subscribed to %s" % (callback, type))

		self._callbacks[type].append(callback)

	def unsubscribe(self, type, callback):
		self._callbacks[type].remove(callback)

	def discard(self, type, callback):
		if callback in self._callbacks[type]:
			self._callbacks[type].remove(callback)

	def broadcast(self, type, *args, **kwargs):
		if type not in self._message_types:
			return

		for cb in self._callbacks[type]:
			cb(*args, **kwargs)
