"""
WebSocket Connection management
"""
import asyncio
import json
from pprint import pformat
from typing import Callable

from odmantic import ObjectId
from pydantic import BaseModel
from starlette.websockets import WebSocket
from loguru import logger

from dice_be.models.games import PlayerData
from dice_be.models.users import User


class ConnectionManager:
    """
    Connection manager is responsible for handling all client connections in a single game
    """

    def __init__(self):
        self.connections: dict[ObjectId, WebSocket] = {}

    def __getitem__(self, client: User) -> WebSocket:
        return self.connections.__getitem__(client.id)

    def add_connection(self, client: User, connection: WebSocket):
        """
        Registered a new client, assumes the connection is already accepted
        """
        self.connections[client.id] = connection

    async def disconnect(self, client: User):
        """
        Explicitly disconnect a client
        """
        await self.connections[client.id].close()

    def remove_connection(self, client: User):
        """
        Unregisters a client, by the time this is called - nothing is sent on the websocket,
        which is assumed to be already closed
        """
        del self.connections[client.id]

    async def send(
        self, client: User | PlayerData | ObjectId, data: str | dict | BaseModel
    ):
        if isinstance(data, dict):
            data = json.dumps(data)
        elif isinstance(data, BaseModel):
            data = data.json()

        if isinstance(client, (User, PlayerData)):
            client = client.id

        try:
            logger.debug(f'Sending text to {client}')
            await self.connections[client].send_text(data)
        except KeyError as e:
            raise LookupError(f'Client {client} is not connected') from e

    async def broadcast(self, data: str | dict | BaseModel, *, exclude: User = None):
        """
        Broadcast a message to all clients
        """
        exclude_ids = {exclude.id} if exclude else {}

        logger.debug(
            f'Broadcasting {pformat(data)}{f", excluding {exclude.name}" if exclude else ""}'
        )

        await asyncio.gather(
            *(
                self.send(client_id, data)
                for client_id, _ in self.connections.items()
                if client_id not in exclude_ids
            ),
            return_exceptions=False,
        )

    async def personal_broadcast(
        self,
        data_factory: Callable[[PlayerData], str],
        player_mapping: dict[ObjectId, PlayerData],
    ):
        """
        Broadcast a personal message to all clients. The message is generated by passing a PlayerData object
        to the data_factory function. player_mapping dictionary is used to convert connected clients to PlayerData
        """

        logger.debug(f'Broadcasting personal messages')

        await asyncio.gather(
            *(
                self.send(client_id, data_factory(player_mapping[client_id]))
                for client_id, _ in self.connections.items()
            ),
            return_exceptions=False,
        )
