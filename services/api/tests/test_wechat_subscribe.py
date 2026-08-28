import json
from typing import cast

import pytest
from redis.asyncio import Redis

from app.core.config import Settings
from app.providers.wechat_subscribe import (
    WechatSubscribeNotConfiguredError,
    WechatSubscribeProvider,
)


def provider(field_maps: dict[str, dict[str, str]]) -> WechatSubscribeProvider:
    settings = Settings(
        _env_file=None,
        wechat_template_field_map_json=json.dumps(field_maps),
    )
    return WechatSubscribeProvider(settings, cast(Redis, object()))


def test_template_data_formats_teacher_new_appointment() -> None:
    subscribe = provider(
        {
            "teacher_new_appointment": {
                "appointment_no": "character_string15",
                "course_name": "thing41",
                "starts_at": "time43",
                "teacher_name": "thing42",
                "student_name": "name8",
            }
        }
    )

    result = subscribe.template_data(
        "teacher_new_appointment",
        {
            "appointment_no": "A20260825023000ABCDEF123456",
            "course_name": "少儿钢琴基础课程超长名称需要安全截断",
            "starts_at": "2026-08-25T02:30:00+00:00",
            "teacher_name": "王老师王老师王老师王老师王老师王老师",
            "student_name": "小明123456789",
        },
    )

    assert result == {
        "character_string15": {"value": "A20260825023000ABCDEF123456"},
        "thing41": {"value": "少儿钢琴基础课程超长名称需要安全截断"[:20]},
        "time43": {"value": "2026年8月25日 10:30"},
        "thing42": {"value": "王老师王老师王老师王老师王老师王老师"[:20]},
        "name8": {"value": "小明"},
    }


def test_template_data_formats_next_day_reminder() -> None:
    subscribe = provider(
        {
            "appointment_next_day_reminder": {
                "course_name": "thing1",
                "starts_at": "character_string2",
                "teacher_name": "thing7",
                "note": "thing6",
            }
        }
    )

    result = subscribe.template_data(
        "appointment_next_day_reminder",
        {
            "course_name": "钢琴课",
            "starts_at": "2026-08-25T02:30:00Z",
            "teacher_name": "王老师",
            "note": "请提前安排时间",
        },
    )

    assert result == {
        "thing1": {"value": "钢琴课"},
        "character_string2": {"value": "2026-08-25 10:30"},
        "thing7": {"value": "王老师"},
        "thing6": {"value": "请提前安排时间"},
    }


def test_template_data_rejects_missing_or_invalid_fields() -> None:
    subscribe = provider(
        {
            "appointment_next_day_reminder": {
                "starts_at": "character_string2",
                "note": "thing6",
            }
        }
    )

    with pytest.raises(WechatSubscribeNotConfiguredError):
        subscribe.template_data(
            "appointment_next_day_reminder",
            {"starts_at": "not-a-time", "note": "请提前安排时间"},
        )

    with pytest.raises(WechatSubscribeNotConfiguredError):
        subscribe.template_data(
            "appointment_next_day_reminder",
            {"starts_at": "2026-08-25T02:30:00+00:00"},
        )
