"""Smoke tests proving the project skeleton and tooling are wired correctly."""

from app import config


def test_data_paths_point_inside_backend_data_dir():
    assert config.FAQ_PATH.parent == config.DATA_DIR
    assert config.EVALUATION_PATH.parent == config.DATA_DIR


def test_message_length_limits_match_sts():
    assert (config.MIN_MESSAGE_LENGTH, config.MAX_MESSAGE_LENGTH) == (1, 500)
