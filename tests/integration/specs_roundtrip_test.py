from __future__ import annotations

from godotllminteraction.specifications.v4_7_0.spec import Specification4_7


def test_specification_round_trips_extension_api_json(extension_api_json: dict) -> None:
    spec = Specification4_7(**extension_api_json)

    dumped = spec.model_dump(mode="json", exclude_unset=True)

    assert dumped == extension_api_json
