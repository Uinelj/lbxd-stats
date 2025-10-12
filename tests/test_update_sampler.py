from update_sampler import UpdateSampler
import logging

from logging import getLogger

log = logging.getLogger(__name__)


def test_update_sampler():
    us = UpdateSampler()
    us._build_df()
