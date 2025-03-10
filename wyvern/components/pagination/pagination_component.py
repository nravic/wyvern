# -*- coding: utf-8 -*-
import logging
from typing import Generic, List

from pydantic.generics import GenericModel

from wyvern.components.component import Component
from wyvern.components.pagination.pagination_fields import PaginationFields
from wyvern.exceptions import PaginationError
from wyvern.wyvern_typing import T

logger = logging.getLogger(__name__)


class PaginationRequest(GenericModel, Generic[T]):
    pagination_fields: PaginationFields
    entities: List[T]


class PaginationComponent(Component[PaginationRequest[T], List[T]]):
    def __init__(self):
        super().__init__(name="PaginationComponent")

    async def execute(self, input: PaginationRequest[T], **kwargs) -> List[T]:
        user_page = input.pagination_fields.user_page
        candidate_page = input.pagination_fields.candidate_page
        candidate_page_size = input.pagination_fields.candidate_page_size
        user_page_size = input.pagination_fields.user_page_size

        ranking_page = user_page - (
            candidate_page * candidate_page_size / user_page_size
        )

        start_index = int(ranking_page * user_page_size)
        end_index = min(int((ranking_page + 1) * user_page_size), len(input.entities))

        # TODO (suchintan): Add test case, this can happen if candidate page > user page
        if ranking_page < 0:
            message = (
                f"Ranking page {ranking_page} is less than 0. Is the user_page correct?. "
                f"pagination_fields={input.pagination_fields}"
            )
            logger.error(message)
            raise PaginationError(message)

        # TODO (suchintan): I wonder if we can have this kind of validation live in the FastApi layer
        # TODO (suchintan): Add test case
        if candidate_page < 0 or user_page < 0:
            message = (
                f"User page {user_page} or candidate page {candidate_page} is less than 0, "
                f"pagination_fields={input.pagination_fields}"
            )
            logger.error(message)
            raise PaginationError(message)

        # TODO (suchintan): Add test case
        if candidate_page_size > 1000 or candidate_page_size < 0:
            message = (
                f"Candidate page size {candidate_page_size} is greater than 1000 or less than 0, "
                f"pagination_fields={input.pagination_fields}"
            )
            logger.error(message)
            raise PaginationError(message)

        # TODO (suchintan): Add test case
        if len(input.entities) > 1000:
            message = (
                f"Number of entities {len(input.entities)} is greater than 1000, "
                f"pagination_fields={input.pagination_fields}"
            )
            logger.error(message)
            raise PaginationError(message)

        # TODO (suchintan): Add test case
        if user_page_size > 100 or user_page_size < 0:
            message = (
                f"User page size {user_page_size} is greater than 100 or less than 0, "
                f"pagination_fields={input.pagination_fields}"
            )
            logger.error(message)
            raise PaginationError(message)

        if user_page_size > candidate_page_size:
            message = (
                f"User page size {user_page_size} is greater than candidate page size {candidate_page_size}, "
                f"pagination_fields={input.pagination_fields}"
            )
            logger.error(message)
            raise PaginationError(message)

        # TODO (suchintan): Add test case
        if end_index > len(input.entities):
            message = (
                f"Computed End index {end_index} is greater than the number of entities {len(input.entities)}, "
                f"pagination_fields={input.pagination_fields}"
            )
            logger.error(message)
            raise PaginationError(message)

        # This should NEVER happen, but add a case here
        if end_index <= start_index:
            message = (
                f"Computed end_index={end_index} is less than or equal to the start_index={start_index} "
                f"number_of_entities={len(input.entities)}, "
                f"pagination_fields={input.pagination_fields}"
            )
            logger.error(message)
            raise PaginationError(message)

        # TODO (suchintan): Add test case
        return input.entities[start_index:end_index]
