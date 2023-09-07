import uuid
from enum import IntEnum

from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound

from .db import engine


class InvalidToken(Exception):
    """指定されたtokenが不正だったときに投げるエラー"""


# サーバーで生成するオブジェクトは strict を使う
class SafeUser(BaseModel, strict=True):
    """token を含まないUser"""

    id: int
    name: str
    leader_card_id: int


def create_user(name: str, leader_card_id: int) -> str:
    """Create new user and returns their token"""
    # UUID4は天文学的な確率だけど衝突する確率があるので、気にするならリトライする必要がある。
    # サーバーでリトライしない場合は、クライアントかユーザー（手動）にリトライさせることになる。
    # ユーザーによるリトライは一般的には良くないけれども、確率が非常に低ければ許容できる場合もある。
    token = str(uuid.uuid4())
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "INSERT INTO `user` (name, token, leader_card_id)"
                " VALUES (:name, :token, :leader_card_id)"
            ),
            {"name": name, "token": token, "leader_card_id": leader_card_id},
        )
        print(f"create_user(): {result.lastrowid=}")  # DB側で生成されたPRIMARY KEYを参照できる
    return token


def _get_user_by_token(conn, token: str) -> SafeUser | None:
    result = conn.execute(
        text("SELECT `id`, `name`, `leader_card_id` FROM `user` WHERE `token`=:token"),
        {"token": token},
    )
    try:
        row = result.one()
    except NoResultFound:
        return None
    return SafeUser.model_validate(row, from_attributes=True)


def get_user_by_token(token: str) -> SafeUser | None:
    with engine.begin() as conn:
        return _get_user_by_token(conn, token)


def update_user(token: str, name: str, leader_card_id: int) -> None:
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken("Invalid token")

        # Now, update the user's information
        conn.execute(
            text(
                "UPDATE `user` SET `name` = :name, `leader_card_id` = :leader_card_id "
                "WHERE `token` = :token"
            ),
            {"name": name, "leader_card_id": leader_card_id, "token": token},
        )

        print("User information updated successfully")


# IntEnum の使い方の例
class LiveDifficulty(IntEnum):
    """難易度"""

    normal = 1
    hard = 2


class JoinRoomResult(IntEnum):
    OK = 1
    RoomFull = 2
    Disbanded = 3
    OtherError = 4


class WaitRoomStatus(IntEnum):
    Waiting = 1
    LiveStart = 2
    Dissolution = 3


def create_room(token: str, live_id: int, difficulty: LiveDifficulty):
    """部屋を作ってroom_idを返します"""
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken
        result = conn.execute(
            text(
                "INSERT INTO `room` (live_id, host_id) VALUES (:live_id, :host_id)"
            ),
            {"live_id": live_id, "host_id": user.id},
        )

        room_id = result.lastrowid
        
        conn.execute(
            text(
                "INSERT INTO `room_member` (room_id, member_id, diff) VALUES (:room_id, :member_id, :diff)"
            ),
            {"room_id": room_id, "member_id": user.id, "diff": difficulty.value},
        )

        print(f"Room created with ID: {room_id}")

        return room_id


def get_rooms_by_live_id(live_id: int):
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "SELECT `room_id`, `live_id`, (SELECT COUNT(*) FROM `room_member` WHERE `room_member`.`room_id` = `room`.`room_id`) AS `joined_user_count`, `capacity` AS `max_user_count` FROM `room` WHERE `live_id` = :live_id"
            ),
            {"live_id": live_id},
        )
        rooms = result.fetchall()
        room_list = [
            {
                "room_id": room[0],
                "live_id": room[1],
                "joined_user_count": room[2],
                "max_user_count": room[3],
            }
            for room in rooms
        ]

        return room_list


def get_result_by_room_id(token: str, room_id: int, difficulty: int):
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        result = conn.execute(
            text(
                "SELECT `capacity`, `is_disbanded`, (SELECT COUNT(*) FROM `room_member` WHERE `room_member`.`room_id` = `room`.`room_id`) AS `joined_user_count` FROM `room` WHERE `room_id` = :room_id"
            ),
            {"room_id": room_id},
        )
        room_data = result.fetchone()

        if room_data and not room_data[1] and room_data[0] is not None and room_data[0] > room_data[2]:
            # 条件が満たされている場合、room_member テーブルに挿入を行う
            with engine.begin() as conn2:
                conn2.execute(
                    text(
                        "INSERT INTO `room_member` (`room_id`, `member_id`, `diff`) VALUES (:room_id, :member_id, :diff)"
                    ),
                    {"room_id": room_id, "member_id": user.id, "diff": difficulty},
                )

        room_status = {
            "max_user_count": room_data[0],
            "is_disbanded": room_data[1],
            "joined_user_count": room_data[2],
        }
        return room_status

