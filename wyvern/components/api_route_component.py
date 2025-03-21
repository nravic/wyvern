# -*- coding: utf-8 -*-
from collections import deque
from typing import Deque, List, Tuple, Type

from ddtrace import tracer

from wyvern import request_context
from wyvern.components.component import Component
from wyvern.entities.identifier import Identifier
from wyvern.entities.identifier_entities import WyvernDataModel, WyvernEntity
from wyvern.redis import wyvern_redis
from wyvern.wyvern_typing import REQUEST_SCHEMA, RESPONSE_SCHEMA


class APIRouteComponent(Component[REQUEST_SCHEMA, RESPONSE_SCHEMA]):
    # this is the api version
    API_VERSION: str = "v1"

    # this is the path for the API route
    PATH: str
    # this is the class of request schema represented by pydantic BaseModel
    REQUEST_SCHEMA_CLASS: Type[REQUEST_SCHEMA]
    # this is the class of response schema represented by pydantic BaseModel
    RESPONSE_SCHEMA_CLASS: Type[RESPONSE_SCHEMA]

    async def warm_up(self, input: REQUEST_SCHEMA) -> None:
        # TODO shu: hydrate
        await self.hydrate(input)
        return

    @tracer.wrap(name="APIRouteComponent.hydrate")
    async def hydrate(self, input: REQUEST_SCHEMA) -> None:
        """
        Wyvern APIRouteComponent recursively hydrate the request input data with Wyvern Index data

        TODO: this function could be moved to a global place
        """
        if not isinstance(input, WyvernDataModel):
            return
        # use BFS to go through the input pydantic model
        # hydrate the data for each WyvernEntity that is encountered layer by layer if there are nested WyvernEntity
        identifiers: List[Identifier] = input.get_all_identifiers(cached=False)
        queue: Deque[WyvernDataModel] = deque([input])
        while identifiers and queue:
            identifiers, queue = await self._bfs_hydrate(identifiers, queue)

    async def _bfs_hydrate(
        self,
        identifiers: List[Identifier],
        queue: Deque[WyvernDataModel],
    ) -> Tuple[List[Identifier], Deque[WyvernDataModel]]:
        current_request = request_context.ensure_current_request()

        # load all the entities from Wyvern Index to self.entity_store
        index_keys = [identifier.index_key() for identifier in identifiers]

        # we're doing an in place update for the entity_store here to save redundant iterations
        # and improve the performance of the code
        await wyvern_redis.mget_update_in_place(index_keys, current_request)

        next_level_queue: Deque[WyvernDataModel] = deque([])
        next_level_identifiers: List[Identifier] = []
        while queue:
            current_obj = queue.popleft()
            # go through all the fields of the current object, and add WyvernDataModel to the queue
            for field in current_obj.__fields__:
                value = getattr(current_obj, field)
                if isinstance(value, WyvernDataModel):
                    queue.append(value)
                if isinstance(value, List):
                    # if the field is a list, we need to check each item in the list
                    # to make sure WyvernDataModel items are enqueued
                    for item in value:
                        if isinstance(item, WyvernDataModel):
                            queue.append(item)

            if isinstance(current_obj, WyvernEntity):
                # if the current node is a WyvernEntity,
                # we need to hydrate the data if the entity exists in the index
                # get the entity from wyvern index
                index_key = current_obj.identifier.index_key()
                entity = current_request.entity_store.get(index_key)

                # load the data into the entity
                if entity:
                    current_obj.load_fields(entity)

            # generate the next level queue
            for (
                id_field_name,
                entity_field_name,
            ) in current_obj.nested_hydration().items():
                id_field_value = getattr(current_obj, id_field_name)
                if not id_field_value:
                    continue
                entity_class: Type[WyvernEntity] = current_obj.__fields__[
                    entity_field_name
                ].type_
                entity_obj = entity_class(**{id_field_name: id_field_value})
                setattr(
                    current_obj,
                    entity_field_name,
                    entity_obj,
                )
                next_level_identifiers.append(entity_obj.identifier)
                next_level_queue.append(getattr(current_obj, entity_field_name))
        return next_level_identifiers, next_level_queue
